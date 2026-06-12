from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecommendationIntent(BaseModel):
    context: str = "mix"
    duration_minutes: int = Field(default=60, ge=15, le=600)
    bpm_min: float | None = Field(default=None, ge=30, le=260)
    bpm_max: float | None = Field(default=None, ge=30, le=260)
    energy_min: float | None = Field(default=None, ge=0, le=1)
    energy_max: float | None = Field(default=None, ge=0, le=1)
    genres: list[str] = Field(default_factory=list)
    artists: list[str] = Field(default_factory=list)
    excluded_tracks: list[str] = Field(default_factory=list)
    excluded_artists: list[str] = Field(default_factory=list)
    discovery_percent: int = Field(default=20, ge=0, le=100)
    text: str | None = Field(default=None, max_length=2000)

    @field_validator("bpm_max")
    @classmethod
    def bpm_order(cls, value: float | None, info):
        bpm_min = info.data.get("bpm_min")
        if value is not None and bpm_min is not None and value < bpm_min:
            raise ValueError("bpm_max muss groesser oder gleich bpm_min sein")
        return value

    @field_validator("energy_max")
    @classmethod
    def energy_order(cls, value: float | None, info):
        energy_min = info.data.get("energy_min")
        if value is not None and energy_min is not None and value < energy_min:
            raise ValueError("energy_max muss groesser oder gleich energy_min sein")
        return value


class IntentTextRequest(BaseModel):
    text: str = Field(min_length=2, max_length=2000)


class TrackFeaturePatch(BaseModel):
    bpm: float | None = Field(default=None, ge=30, le=260)
    musical_key: str | None = Field(default=None, max_length=16)
    energy: float | None = Field(default=None, ge=0, le=1)
    genres: list[str] | None = None


class SessionProfilePatch(BaseModel):
    profile_id: str


class AutomationPatch(BaseModel):
    enabled: bool
    daily_time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    duration_minutes: int = Field(ge=15, le=600)
    discovery_percent: int = Field(ge=0, le=100)


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    preferred_genres: list[str] = Field(default_factory=list)


class SourceProbeResult(BaseModel):
    source: str
    configured: bool
    checked_tracks: int
    matched_tracks: int
    match_rate: float
    status: Literal["ok", "partial", "not_configured", "error"]
    note: str


class ApiMessage(BaseModel):
    message: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    database: str
    timestamp: datetime
