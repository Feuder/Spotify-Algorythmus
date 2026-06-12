from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class FeatureSource(enum.StrEnum):
    manual = "manual"
    getsongbpm = "getsongbpm"
    acousticbrainz = "acousticbrainz"
    musicbrainz = "musicbrainz"
    demo = "demo"
    unknown = "unknown"


class RunStatus(enum.StrEnum):
    pending = "pending"
    completed = "completed"
    published = "published"
    failed = "failed"


track_artists = Table(
    "track_artists",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id", ondelete="CASCADE"), primary_key=True),
    Column("artist_id", ForeignKey("artists.id", ondelete="CASCADE"), primary_key=True),
)


class Artist(Base):
    __tablename__ = "artists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spotify_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    musicbrainz_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    tracks: Mapped[list[Track]] = relationship(secondary=track_artists, back_populates="artists")


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spotify_id: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    uri: Mapped[str | None] = mapped_column(String(200), unique=True)
    isrc: Mapped[str | None] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(500), index=True)
    album_name: Mapped[str | None] = mapped_column(String(500))
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    image_url: Mapped[str | None] = mapped_column(Text)
    popularity: Mapped[int | None] = mapped_column(Integer)
    genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    bpm: Mapped[float | None] = mapped_column(Float)
    musical_key: Mapped[str | None] = mapped_column(String(16))
    camelot_key: Mapped[str | None] = mapped_column(String(8))
    energy: Mapped[float | None] = mapped_column(Float)
    feature_source: Mapped[FeatureSource] = mapped_column(
        Enum(FeatureSource), default=FeatureSource.unknown
    )
    feature_confidence: Mapped[float | None] = mapped_column(Float)
    features_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_discovery: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    artists: Mapped[list[Artist]] = relationship(secondary=track_artists, back_populates="tracks")
    listening_events: Mapped[list[ListeningEvent]] = relationship(back_populates="track")


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spotify_id: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(300))
    device_type: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_genres: Mapped[list[str]] = mapped_column(JSON, default=list)
    excluded_track_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    sessions: Mapped[list[ListeningSession]] = relationship(back_populates="profile")


class ListeningSession(Base):
    __tablename__ = "listening_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_id: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    profile_confidence: Mapped[float | None] = mapped_column(Float)
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    manually_corrected: Mapped[bool] = mapped_column(Boolean, default=False)

    profile: Mapped[Profile | None] = relationship(back_populates="sessions")
    events: Mapped[list[ListeningEvent]] = relationship(
        back_populates="session", order_by="ListeningEvent.played_at"
    )


class ListeningEvent(Base):
    __tablename__ = "listening_events"
    __table_args__ = (UniqueConstraint("track_id", "played_at", name="uq_track_played_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    session_id: Mapped[str | None] = mapped_column(ForeignKey("listening_sessions.id"))
    device_id: Mapped[str | None] = mapped_column(ForeignKey("devices.id"))
    played_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    progress_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_skip: Mapped[bool | None] = mapped_column(Boolean)
    repeated: Mapped[bool] = mapped_column(Boolean, default=False)

    track: Mapped[Track] = relationship(back_populates="listening_events")
    session: Mapped[ListeningSession | None] = relationship(back_populates="events")


class PlaylistRun(Base):
    __tablename__ = "playlist_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    context: Mapped[str] = mapped_column(String(100), default="mix")
    requested_duration_minutes: Mapped[int] = mapped_column(Integer)
    actual_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    requested_discovery_percent: Mapped[int] = mapped_column(Integer, default=20)
    actual_discovery_percent: Mapped[float] = mapped_column(Float, default=0)
    intent: Mapped[dict] = mapped_column(JSON, default=dict)
    algorithm_version: Mapped[str] = mapped_column(String(50), default="v1")
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.pending)
    spotify_playlist_id: Mapped[str | None] = mapped_column(String(100))
    spotify_playlist_url: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    tracks: Mapped[list[PlaylistRunTrack]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="PlaylistRunTrack.position",
    )


class PlaylistRunTrack(Base):
    __tablename__ = "playlist_run_tracks"
    __table_args__ = (UniqueConstraint("run_id", "position", name="uq_run_position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("playlist_runs.id", ondelete="CASCADE"))
    track_id: Mapped[str] = mapped_column(ForeignKey("tracks.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    score_details: Mapped[dict] = mapped_column(JSON, default=dict)

    run: Mapped[PlaylistRun] = relationship(back_populates="tracks")
    track: Mapped[Track] = relationship()


class SpotifyCredential(Base):
    __tablename__ = "spotify_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    spotify_user_id: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str | None] = mapped_column(String(300))
    encrypted_refresh_token: Mapped[str] = mapped_column(Text)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
