from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from math import exp

from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    ListeningEvent,
    ListeningSession,
    PlaylistRun,
    PlaylistRunTrack,
    Profile,
    RunStatus,
    Track,
)
from app.schemas import RecommendationIntent
from app.services.camelot import camelot_compatibility

ALGORITHM_VERSION = "v1.0"


@dataclass(slots=True)
class ScoredTrack:
    track: Track
    score: float
    reasons: list[str]
    details: dict[str, float]


def duration_minutes(tracks: list[Track]) -> float:
    return sum(track.duration_ms for track in tracks) / 60_000


def recency_score(last_played_at: datetime | None, now: datetime | None = None) -> float:
    if last_played_at is None:
        return 0.45
    current = now or datetime.now(UTC)
    if last_played_at.tzinfo is None:
        last_played_at = last_played_at.replace(tzinfo=UTC)
    days = max(0.0, (current - last_played_at).total_seconds() / 86_400)
    return exp(-days / 45)


def context_score(track: Track, intent: RecommendationIntent) -> float:
    score = 0.55
    if intent.bpm_min is not None and track.bpm is not None and track.bpm < intent.bpm_min:
        return 0.1
    if intent.bpm_max is not None and track.bpm is not None and track.bpm > intent.bpm_max:
        return 0.1
    if (
        intent.energy_min is not None
        and track.energy is not None
        and track.energy < intent.energy_min
    ):
        return 0.1
    if (
        intent.energy_max is not None
        and track.energy is not None
        and track.energy > intent.energy_max
    ):
        return 0.1
    if intent.genres and set(map(str.lower, track.genres)) & set(map(str.lower, intent.genres)):
        score += 0.35
    artist_names = {artist.name.lower() for artist in track.artists}
    if intent.artists and artist_names & set(map(str.lower, intent.artists)):
        score += 0.35
    return min(score, 1.0)


def score_track(
    track: Track,
    intent: RecommendationIntent,
    play_count: int,
    skip_rate: float,
    last_played_at: datetime | None,
) -> ScoredTrack:
    preference = min(1.0, 0.35 + play_count / 12) * (1 - min(skip_rate, 0.9))
    recent = recency_score(last_played_at)
    context = context_score(track, intent)
    discovery = 0.85 if track.is_discovery else 0.45
    feature_confidence = track.feature_confidence if track.feature_confidence is not None else 0.45
    score = (
        preference * 0.32
        + recent * 0.18
        + context * 0.28
        + discovery * 0.14
        + feature_confidence * 0.08
    )
    reasons = []
    if context >= 0.8:
        reasons.append("Passt gut zu deinen Kriterien")
    if preference >= 0.7:
        reasons.append("Persoenlicher Favorit mit gutem Hoerverhalten")
    if track.is_discovery:
        reasons.append("Neue Entdeckung aus aehnlichen Tracks")
    if track.bpm is None or track.camelot_key is None:
        reasons.append("Musikmerkmale teilweise unbekannt")
    return ScoredTrack(
        track=track,
        score=round(score, 5),
        reasons=reasons or ["Ausgewogene Empfehlung"],
        details={
            "preference": round(preference, 4),
            "recency": round(recent, 4),
            "context": round(context, 4),
            "discovery": round(discovery, 4),
            "feature_confidence": round(feature_confidence, 4),
        },
    )


def transition_cost(previous: Track, current: Track, artist_counts: Counter[str]) -> float:
    bpm_cost = (
        0.35
        if previous.bpm is None or current.bpm is None
        else min(abs(previous.bpm - current.bpm) / 45, 1)
    )
    key_cost = 1 - camelot_compatibility(previous.camelot_key, current.camelot_key)
    genre_cost = 0.35 if set(previous.genres) & set(current.genres) else 0.7
    repeated_artist = any(artist_counts[artist.id] >= 1 for artist in current.artists)
    return bpm_cost * 0.35 + key_cost * 0.35 + genre_cost * 0.2 + repeated_artist * 0.1


def order_tracks(scored: list[ScoredTrack]) -> list[ScoredTrack]:
    if not scored:
        return []
    remaining = sorted(scored, key=lambda item: item.score, reverse=True)
    ordered = [remaining.pop(0)]
    artist_counts: Counter[str] = Counter(artist.id for artist in ordered[0].track.artists)
    while remaining:
        previous = ordered[-1].track
        next_item = min(
            remaining,
            key=lambda item: (
                transition_cost(previous, item.track, artist_counts) - item.score * 0.25
            ),
        )
        ordered.append(next_item)
        remaining.remove(next_item)
        artist_counts.update(artist.id for artist in next_item.track.artists)
    return ordered


def _event_stats(db: Session) -> dict[str, tuple[int, float, datetime | None]]:
    rows = db.execute(
        select(
            ListeningEvent.track_id,
            func.count(ListeningEvent.id),
            func.avg(cast(ListeningEvent.estimated_skip, Integer)),
            func.max(ListeningEvent.played_at),
        )
        .join(ListeningSession, ListeningEvent.session_id == ListeningSession.id)
        .join(Profile, ListeningSession.profile_id == Profile.id)
        .where(Profile.is_primary.is_(True))
        .group_by(ListeningEvent.track_id)
    ).all()
    return {row[0]: (int(row[1] or 0), float(row[2] or 0), row[3]) for row in rows}


def build_playlist(db: Session, intent: RecommendationIntent) -> PlaylistRun:
    excluded_names = {name.lower() for name in intent.excluded_tracks}
    excluded_artists = {name.lower() for name in intent.excluded_artists}
    tracks = list(
        db.scalars(select(Track).options(selectinload(Track.artists)).order_by(Track.name)).all()
    )
    stats = _event_stats(db)
    eligible: list[ScoredTrack] = []
    for track in tracks:
        artist_names = {artist.name.lower() for artist in track.artists}
        if track.name.lower() in excluded_names or artist_names & excluded_artists:
            continue
        play_count, skip_rate, last_played = stats.get(track.id, (0, 0.0, None))
        eligible.append(score_track(track, intent, play_count, skip_rate, last_played))

    target_ms = intent.duration_minutes * 60_000
    discoveries = sorted(
        (item for item in eligible if item.track.is_discovery),
        key=lambda item: item.score,
        reverse=True,
    )
    known = sorted(
        (item for item in eligible if not item.track.is_discovery),
        key=lambda item: item.score,
        reverse=True,
    )
    selected: list[ScoredTrack] = []
    total_ms = 0
    discovery_index = 0
    known_index = 0
    selected_discovery = 0
    while total_ms < target_ms and (discovery_index < len(discoveries) or known_index < len(known)):
        next_size = len(selected) + 1
        target_discovery_count = round(next_size * intent.discovery_percent / 100)
        should_choose_discovery = selected_discovery < target_discovery_count
        if should_choose_discovery and discovery_index < len(discoveries):
            item = discoveries[discovery_index]
            discovery_index += 1
            selected_discovery += 1
        elif known_index < len(known):
            item = known[known_index]
            known_index += 1
        elif discovery_index < len(discoveries):
            item = discoveries[discovery_index]
            discovery_index += 1
            selected_discovery += 1
        else:
            break
        selected.append(item)
        total_ms += item.track.duration_ms
    selected = order_tracks(selected)
    actual_discovery = (
        sum(1 for item in selected if item.track.is_discovery) / len(selected) * 100
        if selected
        else 0
    )

    run = PlaylistRun(
        context=intent.context,
        requested_duration_minutes=intent.duration_minutes,
        actual_duration_ms=total_ms,
        requested_discovery_percent=intent.discovery_percent,
        actual_discovery_percent=round(actual_discovery, 2),
        intent=intent.model_dump(mode="json"),
        algorithm_version=ALGORITHM_VERSION,
        status=RunStatus.completed,
    )
    for position, item in enumerate(selected, start=1):
        run.tracks.append(
            PlaylistRunTrack(
                track_id=item.track.id,
                position=position,
                score=item.score,
                reasons=item.reasons,
                score_details=item.details,
            )
        )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run
