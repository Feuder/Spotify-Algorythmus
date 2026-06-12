from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


class TokenCipher:
    def __init__(self, key: str | None = None) -> None:
        value = key or get_settings().app_encryption_key
        if not value:
            raise RuntimeError("APP_ENCRYPTION_KEY fehlt in der zentralen .env")
        self._fernet = Fernet(value.encode())

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, value: str) -> str:
        try:
            return self._fernet.decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise RuntimeError(
                "Gespeichertes Spotify-Token kann nicht entschluesselt werden"
            ) from exc
