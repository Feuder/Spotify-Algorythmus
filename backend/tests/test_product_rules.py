from datetime import UTC, datetime

from app.integrations.musicdata import FeatureMatch
from app.models import (
    Artist,
    FeatureSource,
    ListeningEvent,
    ListeningSession,
    PlaylistRun,
    PlaylistRunTrack,
    Profile,
    RunStatus,
    Track,
)
from app.schemas import RecommendationIntent
from app.seed import demo_popularity
from app.services.publishing import publish_run
from app.services.recommender import build_playlist
from app.services.sync import enrich_features


def test_demo_popularity_stays_in_spotify_range() -> None:
    assert demo_popularity(0) == 45
    assert demo_popularity(119) == 100


def test_profile_correction_changes_following_preference_score(db) -> None:
    primary = Profile(name="Hauptprofil", is_primary=True)
    guest = Profile(name="Gast")
    artist = Artist(name="Artist")
    track = Track(
        spotify_id="profile-track",
        uri="spotify:track:profile",
        name="Profile Track",
        duration_ms=180_000,
        feature_confidence=0.8,
        artists=[artist],
    )
    session = ListeningSession(
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        profile=primary,
    )
    db.add_all([primary, guest, track, session])
    db.flush()
    for minute in range(6):
        db.add(
            ListeningEvent(
                track_id=track.id,
                session_id=session.id,
                played_at=datetime.now(UTC).replace(minute=minute),
                estimated_skip=False,
            )
        )
    db.commit()

    before = build_playlist(db, RecommendationIntent(duration_minutes=15))
    before_preference = before.tracks[0].score_details["preference"]
    session.profile = guest
    session.manually_corrected = True
    db.commit()
    after = build_playlist(db, RecommendationIntent(duration_minutes=15))
    after_preference = after.tracks[0].score_details["preference"]

    assert before_preference > after_preference


def test_publish_reuses_existing_playlist_from_same_day(db, monkeypatch) -> None:
    track = Track(
        spotify_id="publish-track",
        uri="spotify:track:publish",
        name="Publish Track",
        duration_ms=180_000,
    )
    prior = PlaylistRun(
        requested_duration_minutes=15,
        status=RunStatus.published,
        spotify_playlist_id="same-day-playlist",
        spotify_playlist_url="https://example.test/playlist",
        tracks=[PlaylistRunTrack(track=track, position=1, score=1, reasons=[], score_details={})],
    )
    current = PlaylistRun(
        requested_duration_minutes=15,
        status=RunStatus.completed,
        tracks=[PlaylistRunTrack(track=track, position=1, score=1, reasons=[], score_details={})],
    )
    db.add_all([prior, current])
    db.commit()

    calls = {"created": 0, "replaced": None}

    class FakeSpotify:
        def __init__(self, _db):
            pass

        def create_private_playlist(self, name, description):
            calls["created"] += 1
            return {"id": "new"}

        def replace_playlist_items(self, playlist_id, uris):
            calls["replaced"] = (playlist_id, uris)

    monkeypatch.setattr("app.services.publishing.SpotifyClient", FakeSpotify)
    published = publish_run(db, current.id)

    assert calls["created"] == 0
    assert calls["replaced"] == ("same-day-playlist", ["spotify:track:publish"])
    assert published.spotify_playlist_id == "same-day-playlist"


def test_lower_confidence_source_does_not_overwrite_existing_features(db, monkeypatch) -> None:
    artist = Artist(name="Reliable Artist")
    track = Track(
        spotify_id="reliable-track",
        name="Reliable Track",
        duration_ms=180_000,
        bpm=120,
        camelot_key=None,
        feature_source=FeatureSource.manual,
        feature_confidence=1.0,
        artists=[artist],
    )
    db.add(track)
    db.commit()

    class LowConfidenceResolver:
        def resolve(self, artist, track):
            return FeatureMatch(
                bpm=90,
                musical_key="Gm",
                source=FeatureSource.acousticbrainz,
                confidence=0.5,
            )

    monkeypatch.setattr("app.services.sync.MusicDataResolver", LowConfidenceResolver)
    result = enrich_features(db, 100)

    assert result["updated"] == 0
    assert track.bpm == 120
    assert track.feature_source == FeatureSource.manual
