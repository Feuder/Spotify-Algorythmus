from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Artist,
    FeatureSource,
    ListeningEvent,
    ListeningSession,
    PlaylistRun,
    Profile,
    Track,
)
from app.schemas import RecommendationIntent
from app.services.recommender import build_playlist

DEMO_TRACKS = [
    ("Midnight Signals", "Lumen Field", 122, "8A", 0.72, ["indie electronic"], False),
    ("Paper Satellites", "North Arcade", 118, "8B", 0.66, ["indie pop"], False),
    ("Soft Static", "Lumen Field", 116, "9A", 0.57, ["downtempo"], False),
    ("Brighter Than Dust", "Velvet Hours", 126, "9B", 0.81, ["alternative dance"], False),
    ("Slow Meridian", "Iris Avenue", 104, "10A", 0.43, ["dream pop"], False),
    ("Parallel Lines", "North Arcade", 124, "10B", 0.78, ["indie electronic"], False),
    ("Amber Current", "Coastline Theory", 120, "11A", 0.69, ["electropop"], True),
    ("Quiet Geometry", "Hollow Forms", 110, "11B", 0.48, ["ambient pop"], True),
    ("Afterimage", "Velvet Hours", 128, "12A", 0.84, ["alternative dance"], True),
    ("Open Window", "Iris Avenue", 112, "12B", 0.55, ["dream pop"], True),
    ("Night Bus", "Coastline Theory", 119, None, 0.62, ["indie electronic"], True),
    ("Silver Thread", "Hollow Forms", None, "7A", None, ["ambient pop"], True),
]


def demo_catalog() -> list[tuple[str, str, int | None, str | None, float | None, list[str], bool]]:
    catalog = list(DEMO_TRACKS)
    prefixes = [
        "Velvet",
        "Northern",
        "Open",
        "Quiet",
        "Amber",
        "Silver",
        "Parallel",
        "After",
        "Electric",
        "Soft",
        "Coastal",
        "Midnight",
    ]
    suffixes = [
        "Current",
        "Signals",
        "Geometry",
        "Horizon",
        "Letters",
        "Motion",
        "Bloom",
        "Static",
        "Avenue",
        "Meridian",
    ]
    artists = [
        "Lumen Field",
        "North Arcade",
        "Velvet Hours",
        "Iris Avenue",
        "Coastline Theory",
        "Hollow Forms",
        "Amber Assembly",
        "Night Transit",
    ]
    genres = [
        ["indie electronic"],
        ["dream pop"],
        ["alternative dance"],
        ["downtempo"],
        ["electropop"],
    ]
    for index in range(len(catalog), 120):
        generated_name = (
            f"{prefixes[index % len(prefixes)]} {suffixes[(index * 3) % len(suffixes)]} {index + 1}"
        )
        catalog.append(
            (
                generated_name,
                artists[index % len(artists)],
                82 + (index * 7) % 76,
                f"{(index % 12) + 1}{'A' if index % 2 == 0 else 'B'}",
                round(min(0.94, 0.35 + (index % 60) / 100), 2),
                genres[index % len(genres)],
                index % 5 == 0,
            )
        )
    return catalog


def demo_popularity(index: int) -> int:
    return min(100, 45 + index)


def seed() -> None:
    if not get_settings().demo_mode:
        return
    with SessionLocal() as db:
        primary = db.scalar(select(Profile).where(Profile.is_primary.is_(True)))
        if primary is None:
            primary = Profile(
                name="Hauptprofil", is_primary=True, preferred_genres=["indie electronic"]
            )
            db.add(primary)
        guest = db.scalar(select(Profile).where(Profile.is_primary.is_(False)))
        if guest is None:
            db.add(Profile(name="Gast", preferred_genres=["alternative dance"]))
        db.flush()
        tracks: list[Track] = []
        for index, (name, artist_name, bpm, camelot, energy, genres, discovery) in enumerate(
            demo_catalog()
        ):
            duration_ms = 185_000 + (index % 12) * 8_000
            existing = db.scalar(select(Track).where(Track.spotify_id == f"demo-{index}"))
            if existing:
                existing.duration_ms = duration_ms
                existing.popularity = demo_popularity(index)
                tracks.append(existing)
                continue
            artist = db.scalar(select(Artist).where(Artist.name == artist_name))
            if artist is None:
                artist = Artist(name=artist_name, genres=genres)
                db.add(artist)
                db.flush()
            track = Track(
                spotify_id=f"demo-{index}",
                uri=f"spotify:track:demo-{index}",
                name=name,
                album_name="Resonanz Demo Library",
                duration_ms=duration_ms,
                popularity=demo_popularity(index),
                genres=genres,
                bpm=bpm,
                camelot_key=camelot,
                energy=energy,
                feature_source=FeatureSource.demo,
                feature_confidence=0.9 if bpm and camelot else 0.35,
                features_checked_at=datetime.now(UTC),
                is_saved=not discovery,
                is_discovery=discovery,
                artists=[artist],
            )
            db.add(track)
            tracks.append(track)
        db.flush()
        if (db.scalar(select(func.count(ListeningEvent.id))) or 0) == 0:
            session = ListeningSession(
                started_at=datetime.now(UTC) - timedelta(hours=2),
                ended_at=datetime.now(UTC) - timedelta(minutes=12),
                profile_id=primary.id,
                profile_confidence=1.0,
                assignment_reason="Demo-Hauptprofil",
            )
            db.add(session)
            for index, track in enumerate(tracks[:8]):
                db.add(
                    ListeningEvent(
                        track_id=track.id,
                        session=session,
                        played_at=session.started_at + timedelta(minutes=index * 14),
                        progress_ms=track.duration_ms,
                        estimated_skip=False if index != 5 else True,
                        repeated=False,
                    )
                )
        db.commit()
        if (db.scalar(select(func.count(PlaylistRun.id))) or 0) == 0:
            build_playlist(
                db,
                RecommendationIntent(context="fokus", duration_minutes=45, discovery_percent=25),
            )


if __name__ == "__main__":
    seed()
