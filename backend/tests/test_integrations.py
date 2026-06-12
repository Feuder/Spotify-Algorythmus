import json
from datetime import UTC, datetime, timedelta

import httpx

from app.integrations.lastfm import LastFmClient
from app.integrations.spotify import SpotifyClient
from app.models import SpotifyCredential
from app.services.crypto import TokenCipher


def test_spotify_refreshes_after_401(db, monkeypatch) -> None:
    calls = {"api": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/token":
            return httpx.Response(200, json={"access_token": "fresh", "expires_in": 3600})
        calls["api"] += 1
        if calls["api"] == 1:
            return httpx.Response(401, json={"error": {"message": "expired"}})
        assert request.headers["Authorization"] == "Bearer fresh"
        return httpx.Response(200, json={"id": "user"})

    cipher = TokenCipher()
    db.add(
        SpotifyCredential(
            spotify_user_id="user",
            encrypted_refresh_token=cipher.encrypt("refresh-token"),
            encrypted_access_token=cipher.encrypt("old"),
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    client = SpotifyClient(db, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(client.settings, "spotify_client_id", "client")
    monkeypatch.setattr(client.settings, "spotify_client_secret", "secret")

    assert client.request("GET", "/me").json()["id"] == "user"
    assert calls["api"] == 2


def test_spotify_reports_rate_limit(db) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "3"}, json={"error": {}})

    cipher = TokenCipher()
    db.add(
        SpotifyCredential(
            spotify_user_id="user",
            encrypted_refresh_token=cipher.encrypt("refresh-token"),
            encrypted_access_token=cipher.encrypt("valid"),
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    client = SpotifyClient(db, transport=httpx.MockTransport(handler))
    try:
        client.request("GET", "/me")
    except RuntimeError as exc:
        assert "3 Sekunden" in str(exc)
    else:
        raise AssertionError("Rate limit was not raised")


def test_spotify_surfaces_forbidden_response(db) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    cipher = TokenCipher()
    db.add(
        SpotifyCredential(
            spotify_user_id="user",
            encrypted_refresh_token=cipher.encrypt("refresh-token"),
            encrypted_access_token=cipher.encrypt("valid"),
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    client = SpotifyClient(db, transport=httpx.MockTransport(handler))

    try:
        client.request("GET", "/me/player")
    except httpx.HTTPStatusError as exc:
        assert exc.response.status_code == 403
    else:
        raise AssertionError("Forbidden response was not raised")


def test_spotify_paging_honors_page_and_item_limits(db) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        next_url = f"https://api.spotify.com/v1/items?page={calls['count'] + 1}"
        return httpx.Response(
            200,
            json={"items": [{"id": calls["count"]}], "next": next_url},
        )

    cipher = TokenCipher()
    db.add(
        SpotifyCredential(
            spotify_user_id="user",
            encrypted_refresh_token=cipher.encrypt("refresh-token"),
            encrypted_access_token=cipher.encrypt("valid"),
            access_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    db.commit()
    client = SpotifyClient(db, transport=httpx.MockTransport(handler))

    assert client.paged_items("/items", max_pages=2) == [{"id": 1}, {"id": 2}]
    assert calls["count"] == 2

    calls["count"] = 0
    assert client.paged_items("/items", max_items=1) == [{"id": 1}]
    assert calls["count"] == 1


def test_lastfm_tolerates_missing_fields(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({}).encode())

    client = LastFmClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(client.settings, "lastfm_api_key", "configured")
    assert client.similar_tracks("Artist", "Track") == []
