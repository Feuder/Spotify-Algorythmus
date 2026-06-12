from datetime import UTC, datetime, timedelta

from app.models import Artist, ListeningEvent, Track
from app.schemas import RecommendationIntent
from app.services.camelot import camelot_compatibility, to_camelot
from app.services.listening import EventSignal, estimate_skip, sessionize
from app.services.profiles import guest_profile_assignment
from app.services.recommender import build_playlist, duration_minutes


def test_camelot_mapping_and_compatibility() -> None:
    assert to_camelot("Am") == "8A"
    assert camelot_compatibility("8A", "8A") == 1.0
    assert camelot_compatibility("8A", "8B") == 0.9
    assert camelot_compatibility("8A", "9A") == 0.85
    assert camelot_compatibility(None, "9A") == 0.45


def test_skip_detection_marks_only_clear_cases() -> None:
    assert estimate_skip(20_000, 200_000) is True
    assert estimate_skip(190_000, 200_000) is False
    assert estimate_skip(100_000, 200_000) is None
    assert estimate_skip(None, 200_000) is None


def test_sessionization_uses_thirty_minute_gap() -> None:
    start = datetime.now(UTC)
    events = [
        EventSignal(start, 200_000, track_id="a"),
        EventSignal(start + timedelta(minutes=20), 200_000, track_id="b"),
        EventSignal(start + timedelta(minutes=55), 200_000, track_id="c"),
    ]
    sessions = sessionize(events)
    assert [len(session) for session in sessions] == [2, 1]


def test_guest_assignment_requires_baseline_tracks_and_confidence() -> None:
    early = guest_profile_assignment(
        primary_history_size=20,
        suspicious_track_count=5,
        genre_distance=1,
        skip_pattern_distance=1,
        guest_profile_id="guest",
    )
    assert early.profile_id is None
    assigned = guest_profile_assignment(
        primary_history_size=100,
        suspicious_track_count=3,
        genre_distance=0.9,
        skip_pattern_distance=0.8,
        guest_profile_id="guest",
    )
    assert assigned.profile_id == "guest"
    assert assigned.confidence >= 0.90


def test_playlist_respects_exclusions_discovery_and_duration(db) -> None:
    artist = Artist(name="Test Artist")
    db.add(artist)
    tracks = []
    for index in range(12):
        track = Track(
            spotify_id=f"track-{index}",
            uri=f"spotify:track:{index}",
            name=f"Track {index}",
            duration_ms=180_000,
            bpm=110 + index,
            camelot_key=f"{(index % 12) + 1}A",
            energy=0.6,
            genres=["indie"],
            feature_confidence=0.9,
            is_discovery=index >= 8,
            artists=[artist],
        )
        db.add(track)
        tracks.append(track)
    db.flush()
    db.add(
        ListeningEvent(
            track_id=tracks[0].id,
            played_at=datetime.now(UTC),
            estimated_skip=False,
        )
    )
    db.commit()

    run = build_playlist(
        db,
        RecommendationIntent(
            duration_minutes=30,
            discovery_percent=30,
            excluded_tracks=["Track 1"],
        ),
    )
    names = [item.track.name for item in run.tracks]
    assert "Track 1" not in names
    assert 27 <= duration_minutes([item.track for item in run.tracks]) <= 33
    assert 20 <= run.actual_discovery_percent <= 40
    assert all(item.reasons and item.score_details for item in run.tracks)
