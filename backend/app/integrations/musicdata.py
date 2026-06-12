from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from app.config import get_settings
from app.models import FeatureSource
from app.services.camelot import to_camelot


@dataclass(slots=True)
class FeatureMatch:
    bpm: float | None = None
    musical_key: str | None = None
    genres: list[str] | None = None
    energy: float | None = None
    musicbrainz_id: str | None = None
    source: FeatureSource = FeatureSource.unknown
    confidence: float = 0.0
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def camelot_key(self) -> str | None:
        return to_camelot(self.musical_key)


class MusicDataResolver:
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = get_settings()
        self.http = httpx.Client(timeout=15, transport=transport)

    def getsongbpm(self, artist: str, track: str) -> FeatureMatch | None:
        if not self.settings.getsongbpm_api_key:
            return None
        response = self.http.get(
            "https://api.getsong.co/search/",
            params={
                "api_key": self.settings.getsongbpm_api_key,
                "type": "song",
                "lookup": f"song:{track} artist:{artist}",
            },
        )
        response.raise_for_status()
        songs = response.json().get("search", [])
        if not songs:
            return None
        first = songs[0]
        return FeatureMatch(
            bpm=float(first["tempo"]) if first.get("tempo") else None,
            musical_key=first.get("key_of"),
            source=FeatureSource.getsongbpm,
            confidence=0.92,
        )

    def musicbrainz(self, artist: str, track: str) -> FeatureMatch | None:
        if not self.settings.musicbrainz_contact_email:
            return None
        response = self.http.get(
            "https://musicbrainz.org/ws/2/recording/",
            params={
                "query": f'recording:"{track}" AND artist:"{artist}"',
                "fmt": "json",
                "limit": 1,
            },
            headers={"User-Agent": f"Resonanz/0.1 ({self.settings.musicbrainz_contact_email})"},
        )
        response.raise_for_status()
        recordings = response.json().get("recordings", [])
        if not recordings:
            return None
        genres = [genre["name"] for genre in recordings[0].get("genres", [])]
        return FeatureMatch(
            genres=genres,
            musicbrainz_id=recordings[0].get("id"),
            source=FeatureSource.musicbrainz,
            confidence=0.72,
        )

    def acousticbrainz(self, musicbrainz_id: str | None) -> FeatureMatch | None:
        if not musicbrainz_id:
            return None
        response = self.http.get(f"https://acousticbrainz.org/{musicbrainz_id}/low-level")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        rhythm = payload.get("rhythm", {})
        tonal = payload.get("tonal", {})
        key = tonal.get("key_key")
        scale = tonal.get("key_scale")
        musical_key = f"{key}m" if key and scale == "minor" else key
        return FeatureMatch(
            bpm=rhythm.get("bpm"),
            musical_key=musical_key,
            source=FeatureSource.acousticbrainz,
            confidence=0.78,
        )

    def resolve(self, artist: str, track: str) -> FeatureMatch:
        musicbrainz = self.musicbrainz(artist, track)
        matches = [
            match
            for match in (
                self.getsongbpm(artist, track),
                self.acousticbrainz(musicbrainz.musicbrainz_id) if musicbrainz else None,
                musicbrainz,
            )
            if match is not None
        ]
        if not matches:
            return FeatureMatch()
        return max(matches, key=lambda item: item.confidence)
