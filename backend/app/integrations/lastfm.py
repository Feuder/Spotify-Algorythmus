import httpx

from app.config import get_settings


class LastFmClient:
    BASE_URL = "https://ws.audioscrobbler.com/2.0/"

    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.settings = get_settings()
        self.http = httpx.Client(timeout=15, transport=transport)

    @property
    def configured(self) -> bool:
        return bool(self.settings.lastfm_api_key)

    def _get(self, method: str, **params) -> dict:
        if not self.configured:
            return {}
        response = self.http.get(
            self.BASE_URL,
            params={
                "method": method,
                "api_key": self.settings.lastfm_api_key,
                "format": "json",
                **params,
            },
        )
        response.raise_for_status()
        return response.json()

    def similar_tracks(self, artist: str, track: str, limit: int = 20) -> list[dict]:
        data = self._get("track.getSimilar", artist=artist, track=track, limit=limit)
        return data.get("similartracks", {}).get("track", [])

    def similar_artists(self, artist: str, limit: int = 20) -> list[dict]:
        data = self._get("artist.getSimilar", artist=artist, limit=limit)
        return data.get("similarartists", {}).get("artist", [])
