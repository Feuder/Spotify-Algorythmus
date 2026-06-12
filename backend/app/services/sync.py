from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.lastfm import LastFmClient
from app.integrations.musicdata import MusicDataResolver
from app.integrations.spotify import SpotifyClient
from app.models import Artist, Device, ListeningEvent, ListeningSession, Track
from app.services.listening import estimate_skip
from app.services.profiles import assign_unclassified_sessions


def _artist(db: Session, payload: dict) -> Artist:
    spotify_id = payload.get("id")
    artist = (
        db.scalar(select(Artist).where(Artist.spotify_id == spotify_id)) if spotify_id else None
    )
    if artist is None:
        artist = Artist(spotify_id=spotify_id, name=payload.get("name", "Unbekannt"))
        db.add(artist)
        db.flush()
    return artist


def upsert_spotify_track(
    db: Session, payload: dict, *, is_saved: bool = False, is_discovery: bool = False
) -> Track:
    spotify_id = payload.get("id")
    track = db.scalar(select(Track).where(Track.spotify_id == spotify_id)) if spotify_id else None
    if track is None:
        track = Track(spotify_id=spotify_id, name=payload.get("name", "Unbekannt"))
        db.add(track)
    track.uri = payload.get("uri")
    track.album_name = payload.get("album", {}).get("name")
    track.duration_ms = payload.get("duration_ms") or 0
    images = payload.get("album", {}).get("images", [])
    track.image_url = images[0].get("url") if images else track.image_url
    track.popularity = payload.get("popularity")
    track.isrc = payload.get("external_ids", {}).get("isrc")
    track.is_saved = track.is_saved or is_saved
    track.is_discovery = track.is_discovery or is_discovery
    track.artists = [_artist(db, artist) for artist in payload.get("artists", [])]
    db.flush()
    return track


def _active_session(db: Session, played_at: datetime) -> ListeningSession:
    session = db.scalar(
        select(ListeningSession).order_by(ListeningSession.started_at.desc()).limit(1)
    )
    ended_at = session.ended_at if session else None
    if ended_at and ended_at.tzinfo is None:
        ended_at = ended_at.replace(tzinfo=UTC)
    if session is None or (ended_at and played_at - ended_at > timedelta(minutes=30)):
        session = ListeningSession(started_at=played_at, ended_at=played_at)
        db.add(session)
        db.flush()
    session.ended_at = max(ended_at or played_at, played_at)
    return session


def sync_spotify(db: Session) -> dict:
    client = SpotifyClient(db)
    recently = client.paged_items("/me/player/recently-played", limit=50, max_pages=1, max_items=50)
    top_tracks = client.paged_items(
        "/me/top/tracks", limit=50, time_range="medium_term", max_pages=1, max_items=50
    )
    saved_items = client.paged_items("/me/tracks", limit=50, max_pages=20, max_items=1000)
    devices_payload = client.request("GET", "/me/player/devices").json().get("devices", [])

    imported_events = 0
    for item in recently:
        played_at = datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))
        track = upsert_spotify_track(db, item["track"])
        exists = db.scalar(
            select(ListeningEvent).where(
                ListeningEvent.track_id == track.id,
                ListeningEvent.played_at == played_at,
            )
        )
        if exists:
            continue
        session = _active_session(db, played_at)
        db.add(
            ListeningEvent(
                track_id=track.id,
                session_id=session.id,
                played_at=played_at,
                estimated_skip=None,
            )
        )
        imported_events += 1

    for payload in top_tracks:
        upsert_spotify_track(db, payload)
    for item in saved_items:
        upsert_spotify_track(db, item.get("item") or item.get("track") or item, is_saved=True)
    for payload in devices_payload:
        device = db.scalar(select(Device).where(Device.spotify_id == payload["id"]))
        if device is None:
            device = Device(spotify_id=payload["id"], name=payload.get("name", "Spotify"))
            db.add(device)
        device.device_type = payload.get("type")
        device.is_active = bool(payload.get("is_active"))
        device.last_seen_at = datetime.now(UTC)
    db.commit()
    sessions_assigned = assign_unclassified_sessions(db)
    return {
        "events_imported": imported_events,
        "top_tracks_seen": len(top_tracks),
        "saved_tracks_seen": len(saved_items),
        "devices_seen": len(devices_payload),
        "sessions_assigned": sessions_assigned,
    }


def poll_current_playback(db: Session) -> dict:
    client = SpotifyClient(db)
    response = client.request("GET", "/me/player/currently-playing")
    if response.status_code == 204 or not response.content:
        return {"playing": False}
    payload = response.json()
    track_payload = payload.get("item")
    if not track_payload:
        return {"playing": False}
    track = upsert_spotify_track(db, track_payload)
    progress = payload.get("progress_ms")
    previous = db.scalar(select(ListeningEvent).order_by(ListeningEvent.played_at.desc()).limit(1))
    if previous and previous.track_id != track.id and previous.progress_ms is not None:
        previous.estimated_skip = estimate_skip(previous.progress_ms, previous.track.duration_ms)
    db.commit()
    return {
        "playing": bool(payload.get("is_playing")),
        "track_id": track.id,
        "progress_ms": progress,
    }


def discover_tracks(db: Session, limit: int = 30) -> dict:
    spotify = SpotifyClient(db)
    lastfm = LastFmClient()
    seeds = list(
        db.scalars(
            select(Track)
            .where(Track.is_discovery.is_(False))
            .order_by(Track.updated_at.desc())
            .limit(5)
        ).all()
    )
    created = 0
    for seed in seeds:
        if not seed.artists:
            continue
        candidates = lastfm.similar_tracks(seed.artists[0].name, seed.name, limit=10)
        for candidate in candidates:
            if created >= limit:
                break
            artist_name = candidate.get("artist", {}).get("name")
            name = candidate.get("name")
            if not artist_name or not name:
                continue
            result = spotify.request(
                "GET",
                "/search",
                params={"q": f'track:"{name}" artist:"{artist_name}"', "type": "track", "limit": 1},
            ).json()
            items = result.get("tracks", {}).get("items", [])
            if items:
                before = db.scalar(select(Track).where(Track.spotify_id == items[0].get("id")))
                upsert_spotify_track(db, items[0], is_discovery=True)
                created += int(before is None)
    db.commit()
    return {"seeds": len(seeds), "discovery_tracks_created": created}


def enrich_features(db: Session, limit: int = 100) -> dict:
    resolver = MusicDataResolver()
    tracks = list(
        db.scalars(
            select(Track)
            .where((Track.bpm.is_(None)) | (Track.camelot_key.is_(None)))
            .order_by(Track.updated_at.desc())
            .limit(limit)
        ).all()
    )
    updated = 0
    for track in tracks:
        if not track.artists:
            continue
        match = resolver.resolve(track.artists[0].name, track.name)
        if match.confidence > (track.feature_confidence or 0):
            track.bpm = match.bpm or track.bpm
            track.musical_key = match.musical_key or track.musical_key
            track.camelot_key = match.camelot_key or track.camelot_key
            track.genres = match.genres or track.genres
            track.energy = match.energy or track.energy
            track.feature_source = match.source
            track.feature_confidence = match.confidence
            track.features_checked_at = match.checked_at
            updated += 1
    db.commit()
    return {"checked": len(tracks), "updated": updated}


def source_probe(db: Session, limit: int = 100) -> dict:
    result = enrich_features(db, limit)
    tracks = list(db.scalars(select(Track).order_by(Track.updated_at.desc()).limit(limit)).all())
    sources: dict[str, int] = {}
    for track in tracks:
        sources[track.feature_source.value] = sources.get(track.feature_source.value, 0) + 1
    matched = sum(1 for track in tracks if (track.feature_confidence or 0) > 0)
    return {
        **result,
        "representative_tracks": len(tracks),
        "matched_tracks": matched,
        "match_rate": round(matched / len(tracks) * 100, 1) if tracks else 0,
        "sources": sources,
        "selection_rule": "Hoechste Match-Konfidenz pro Track",
    }
