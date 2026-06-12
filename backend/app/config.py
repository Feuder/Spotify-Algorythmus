from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV if ROOT_ENV.exists() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Resonanz"
    app_env: str = "development"
    app_timezone: str = "Europe/Berlin"
    app_log_level: str = "INFO"
    app_encryption_key: str = ""
    database_url: str = "sqlite:///./resonanz.db"

    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://127.0.0.1:8000/api/auth/spotify/callback"
    lastfm_api_key: str = ""
    getsongbpm_api_key: str = ""
    musicbrainz_contact_email: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

    automation_enabled: bool = True
    automation_daily_time: str = "06:00"
    default_playlist_duration_minutes: int = 300
    default_discovery_percent: int = 20
    current_playback_poll_seconds: int = 30
    demo_mode: bool = True
    allow_queue_assistant: bool = False
    backend_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.backend_cors_origins.split(",") if item.strip()]

    @field_validator("automation_daily_time")
    @classmethod
    def validate_daily_time(cls, value: str) -> str:
        hour, minute = value.split(":", maxsplit=1)
        if not 0 <= int(hour) <= 23 or not 0 <= int(minute) <= 59:
            raise ValueError("AUTOMATION_DAILY_TIME muss HH:MM verwenden")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
