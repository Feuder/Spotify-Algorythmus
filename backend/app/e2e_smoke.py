import json
from datetime import UTC, datetime

from sqlalchemy import select

import app.services.publishing as publishing_module
import app.services.sync as sync_module
from app.db import SessionLocal
from app.integrations.musicdata import FeatureMatch
from app.models import FeatureSource, RunStatus, Track
from app.schemas import RecommendationIntent
from app.seed import seed
from app.services.publishing import publish_run
from app.services.recommender import build_playlist
from app.services.sync import discover_tracks, enrich_features, sync_spotify


def fake_track(track_id: str, name: str, artist: str) -> dict:
    return {
        "id": track_id,
        "uri": f"spotify:track:{track_id}",
        "name": name,
        "duration_ms": 210_000,
        "artists": [{"id": f"artist-{track_id}", "name": artist}],
        "album": {"name": "E2E Album", "images": []},
        "external_ids": {},
    }


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def json(self) -> dict:
        return self.payload


class FakeSyncSpotify:
    def __init__(self, db) -> None:
        self.db = db

    def paged_items(self, path: str, **params) -> list[dict]:
        synced = fake_track("e2e-synced", "E2E Synced", "E2E Artist")
        if path == "/me/player/recently-played":
            return [{"played_at": datetime.now(UTC).isoformat(), "track": synced}]
        if path == "/me/top/tracks":
            return [synced]
        if path == "/me/tracks":
            return [{"item": synced}]
        return []

    def request(self, method: str, path: str, **kwargs) -> FakeResponse:
        if path == "/me/player/devices":
            return FakeResponse(
                {"devices": [{"id": "e2e-device", "name": "E2E Device", "is_active": True}]}
            )
        if path == "/search":
            return FakeResponse(
                {"tracks": {"items": [fake_track("e2e-discovery", "E2E Discovery", "New Artist")]}}
            )
        return FakeResponse({})


class FakeLastFm:
    def similar_tracks(self, artist: str, track: str, limit: int = 20) -> list[dict]:
        return [{"name": "E2E Discovery", "artist": {"name": "New Artist"}}]


class FakeMusicData:
    def resolve(self, artist: str, track: str) -> FeatureMatch:
        return FeatureMatch(
            bpm=123,
            musical_key="Gm",
            genres=["e2e"],
            energy=0.7,
            source=FeatureSource.getsongbpm,
            confidence=0.95,
        )


class FakePublishSpotify:
    published: tuple[str, list[str]] | None = None

    def __init__(self, db) -> None:
        self.db = db

    def create_private_playlist(self, name: str, description: str) -> dict:
        return {
            "id": "e2e-private-playlist",
            "external_urls": {"spotify": "https://example.test/e2e"},
        }

    def replace_playlist_items(self, playlist_id: str, uris: list[str]) -> None:
        self.published = (playlist_id, uris)


def main() -> None:
    seed()
    sync_module.SpotifyClient = FakeSyncSpotify
    sync_module.LastFmClient = FakeLastFm
    sync_module.MusicDataResolver = FakeMusicData
    publishing_module.SpotifyClient = FakePublishSpotify
    with SessionLocal() as db:
        sync_result = sync_spotify(db)
        discovery_result = discover_tracks(db, 10)
        feature_result = enrich_features(db, 100)
        run = build_playlist(
            db,
            RecommendationIntent(
                context="fokus",
                duration_minutes=300,
                discovery_percent=20,
                excluded_tracks=["Midnight Signals"],
            ),
        )
        published = publish_run(db, run.id)
        names = {item.track.name for item in run.tracks}
        minutes = run.actual_duration_ms / 60_000
        assert sync_result["events_imported"] >= 1
        assert discovery_result["discovery_tracks_created"] >= 1
        assert feature_result["checked"] >= 1
        assert 295 <= minutes <= 310
        assert 15 <= run.actual_discovery_percent <= 25
        assert "Midnight Signals" not in names
        assert published.status == RunStatus.published
        assert published.spotify_playlist_id == "e2e-private-playlist"
        assert db.scalar(select(Track).where(Track.spotify_id == "e2e-discovery")) is not None
        print(
            json.dumps(
                {
                    "sync": sync_result,
                    "discovery": discovery_result,
                    "features": feature_result,
                    "playlist_tracks": len(run.tracks),
                    "playlist_minutes": round(minutes, 1),
                    "discovery_percent": run.actual_discovery_percent,
                    "published": published.spotify_playlist_id,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
