from __future__ import annotations

import base64
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import SpotifyCredential
from app.services.crypto import TokenCipher

logger = logging.getLogger(__name__)
SPOTIFY_API = "https://api.spotify.com/v1"
SPOTIFY_ACCOUNTS = "https://accounts.spotify.com"
SCOPES = [
    "user-read-private",
    "user-read-email",
    "user-read-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "user-top-read",
    "user-library-read",
    "playlist-modify-private",
    "user-modify-playback-state",
]


class SpotifyNotConfigured(RuntimeError):
    pass


class SpotifyClient:
    def __init__(self, db: Session, transport: httpx.BaseTransport | None = None) -> None:
        self.db = db
        self.settings = get_settings()
        self.cipher = TokenCipher()
        self.http = httpx.Client(timeout=20, transport=transport)

    @property
    def configured(self) -> bool:
        return bool(self.settings.spotify_client_id and self.settings.spotify_client_secret)

    def authorization_url(self) -> tuple[str, str]:
        if not self.configured:
            raise SpotifyNotConfigured("Spotify-Zugangsdaten fehlen in der zentralen .env")
        state = secrets.token_urlsafe(24)
        query = urlencode(
            {
                "client_id": self.settings.spotify_client_id,
                "response_type": "code",
                "redirect_uri": self.settings.spotify_redirect_uri,
                "scope": " ".join(SCOPES),
                "state": state,
            }
        )
        return f"{SPOTIFY_ACCOUNTS}/authorize?{query}", state

    def _basic_auth(self) -> str:
        raw = f"{self.settings.spotify_client_id}:{self.settings.spotify_client_secret}"
        return base64.b64encode(raw.encode()).decode()

    def exchange_code(self, code: str) -> SpotifyCredential:
        response = self.http.post(
            f"{SPOTIFY_ACCOUNTS}/api/token",
            headers={"Authorization": f"Basic {self._basic_auth()}"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.settings.spotify_redirect_uri,
            },
        )
        response.raise_for_status()
        token_data = response.json()
        profile = self.http.get(
            f"{SPOTIFY_API}/me",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        profile.raise_for_status()
        user = profile.json()
        credential = self.db.scalar(
            select(SpotifyCredential).where(SpotifyCredential.spotify_user_id == user["id"])
        )
        if credential is None:
            credential = SpotifyCredential(
                spotify_user_id=user["id"],
                display_name=user.get("display_name"),
                encrypted_refresh_token=self.cipher.encrypt(token_data["refresh_token"]),
            )
        credential.encrypted_access_token = self.cipher.encrypt(token_data["access_token"])
        credential.access_token_expires_at = datetime.now(UTC) + timedelta(
            seconds=token_data.get("expires_in", 3600) - 60
        )
        credential.scopes = token_data.get("scope", "").split()
        self.db.add(credential)
        self.db.commit()
        return credential

    def _credential(self) -> SpotifyCredential:
        credential = self.db.scalar(select(SpotifyCredential).limit(1))
        if credential is None:
            raise SpotifyNotConfigured("Spotify ist noch nicht verbunden")
        return credential

    def _refresh(self, credential: SpotifyCredential) -> str:
        response = self.http.post(
            f"{SPOTIFY_ACCOUNTS}/api/token",
            headers={"Authorization": f"Basic {self._basic_auth()}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.cipher.decrypt(credential.encrypted_refresh_token),
            },
        )
        response.raise_for_status()
        data = response.json()
        credential.encrypted_access_token = self.cipher.encrypt(data["access_token"])
        credential.access_token_expires_at = datetime.now(UTC) + timedelta(
            seconds=data.get("expires_in", 3600) - 60
        )
        if data.get("refresh_token"):
            credential.encrypted_refresh_token = self.cipher.encrypt(data["refresh_token"])
        self.db.commit()
        return data["access_token"]

    def access_token(self) -> str:
        credential = self._credential()
        now = datetime.now(UTC)
        expires_at = credential.access_token_expires_at
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if not credential.encrypted_access_token or not expires_at or expires_at <= now:
            return self._refresh(credential)
        return self.cipher.decrypt(credential.encrypted_access_token)

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self.access_token()}"
        response = self.http.request(method, f"{SPOTIFY_API}{path}", headers=headers, **kwargs)
        if response.status_code == 401:
            headers["Authorization"] = f"Bearer {self._refresh(self._credential())}"
            response = self.http.request(method, f"{SPOTIFY_API}{path}", headers=headers, **kwargs)
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "unknown")
            raise RuntimeError(f"Spotify-Rate-Limit; erneut versuchen nach {retry_after} Sekunden")
        response.raise_for_status()
        return response

    def paged_items(
        self,
        path: str,
        item_key: str = "items",
        *,
        max_pages: int = 20,
        max_items: int | None = None,
        **params,
    ) -> list[dict]:
        items: list[dict] = []
        next_path: str | None = path
        next_params = params
        pages_seen = 0
        visited_paths: set[str] = set()
        while next_path and pages_seen < max_pages and next_path not in visited_paths:
            visited_paths.add(next_path)
            response = self.request("GET", next_path, params=next_params).json()
            items.extend(response.get(item_key, []))
            pages_seen += 1
            if max_items is not None and len(items) >= max_items:
                return items[:max_items]
            next_url = response.get("next")
            next_path = next_url.removeprefix(SPOTIFY_API) if next_url else None
            next_params = {}
        return items

    def create_private_playlist(self, name: str, description: str) -> dict:
        return self.request(
            "POST",
            "/me/playlists",
            json={"name": name, "description": description, "public": False},
        ).json()

    def replace_playlist_items(self, playlist_id: str, uris: list[str]) -> None:
        self.request("PUT", f"/playlists/{playlist_id}/items", json={"uris": uris[:100]})
        for start in range(100, len(uris), 100):
            self.request(
                "POST",
                f"/playlists/{playlist_id}/items",
                json={"uris": uris[start : start + 100]},
            )

    def enqueue(self, uri: str, device_id: str | None = None) -> None:
        params = {"uri": uri}
        if device_id:
            params["device_id"] = device_id
        self.request("POST", "/me/player/queue", params=params)
