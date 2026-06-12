from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import get_db
from app.integrations.spotify import SpotifyClient, SpotifyNotConfigured
from app.models import (
    AppSetting,
    Artist,
    Device,
    FeatureSource,
    ListeningEvent,
    ListeningSession,
    PlaylistRun,
    PlaylistRunTrack,
    Profile,
    SpotifyCredential,
    Track,
)
from app.schemas import (
    AutomationPatch,
    IntentTextRequest,
    ProfileCreate,
    RecommendationIntent,
    SessionProfilePatch,
    TrackFeaturePatch,
)
from app.serializers import run_payload, track_payload
from app.services.camelot import to_camelot
from app.services.intents import parse_intent
from app.services.publishing import enqueue_run, publish_run
from app.services.recommender import build_playlist
from app.services.sync import discover_tracks, enrich_features, source_probe, sync_spotify

router = APIRouter(prefix="/api")


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "app": get_settings().app_name,
        "database": "ok",
        "timestamp": datetime.now(UTC),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)) -> dict:
    latest_run = db.scalar(
        select(PlaylistRun)
        .options(
            selectinload(PlaylistRun.tracks)
            .selectinload(PlaylistRunTrack.track)
            .selectinload(Track.artists)
        )
        .order_by(PlaylistRun.created_at.desc())
        .limit(1)
    )
    recent_events = list(
        db.scalars(
            select(ListeningEvent)
            .options(selectinload(ListeningEvent.track).selectinload(Track.artists))
            .order_by(ListeningEvent.played_at.desc())
            .limit(8)
        ).all()
    )
    track_count = db.scalar(select(func.count(Track.id))) or 0
    feature_count = db.scalar(select(func.count(Track.id)).where(Track.bpm.is_not(None))) or 0
    session_count = db.scalar(select(func.count(ListeningSession.id))) or 0
    spotify_connected = db.scalar(select(func.count(SpotifyCredential.id))) or 0
    settings = get_settings()
    return {
        "summary": {
            "track_count": track_count,
            "feature_coverage_percent": round(feature_count / track_count * 100, 1)
            if track_count
            else 0,
            "session_count": session_count,
            "spotify_connected": bool(spotify_connected),
            "demo_mode": settings.demo_mode,
        },
        "latest_run": run_payload(latest_run) if latest_run else None,
        "recent_events": [
            {
                "id": event.id,
                "played_at": event.played_at,
                "estimated_skip": event.estimated_skip,
                "repeated": event.repeated,
                "track": track_payload(event.track),
            }
            for event in recent_events
        ],
    }


@router.get("/auth/spotify/status")
def spotify_status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    credential = db.scalar(select(SpotifyCredential).limit(1))
    return {
        "configured": bool(settings.spotify_client_id and settings.spotify_client_secret),
        "connected": credential is not None,
        "display_name": credential.display_name if credential else None,
    }


@router.get("/auth/spotify/login")
def spotify_login(db: Session = Depends(get_db)):
    try:
        url, state = SpotifyClient(db).authorization_url()
    except SpotifyNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    record = db.get(AppSetting, "spotify_oauth_state") or AppSetting(key="spotify_oauth_state")
    record.value = {"state": state}
    db.add(record)
    db.commit()
    return RedirectResponse(url)


@router.get("/auth/spotify/callback")
def spotify_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    stored = db.get(AppSetting, "spotify_oauth_state")
    if not stored or stored.value.get("state") != state:
        raise HTTPException(status_code=400, detail="Ungueltiger OAuth-State")
    SpotifyClient(db).exchange_code(code)
    return RedirectResponse("http://127.0.0.1:3000/?spotify=connected")


@router.post("/sync/spotify")
def sync_spotify_endpoint(db: Session = Depends(get_db)) -> dict:
    try:
        return sync_spotify(db)
    except SpotifyNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sync/discovery")
def discovery_endpoint(db: Session = Depends(get_db)) -> dict:
    try:
        return discover_tracks(db)
    except SpotifyNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sync/features")
def features_endpoint(limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)) -> dict:
    return enrich_features(db, limit)


@router.post("/system/source-probe")
def source_probe_endpoint(
    limit: int = Query(100, ge=1, le=100), db: Session = Depends(get_db)
) -> dict:
    return source_probe(db, limit)


@router.post("/intents/parse")
def parse_intent_endpoint(payload: IntentTextRequest) -> dict:
    intent, parser = parse_intent(payload.text)
    return {"intent": intent, "parser": parser}


@router.post("/playlists/generate")
def generate_playlist(intent: RecommendationIntent, db: Session = Depends(get_db)) -> dict:
    return run_payload(build_playlist(db, intent))


@router.get("/playlist-runs")
def playlist_runs(db: Session = Depends(get_db)) -> list[dict]:
    runs = db.scalars(
        select(PlaylistRun)
        .options(
            selectinload(PlaylistRun.tracks)
            .selectinload(PlaylistRunTrack.track)
            .selectinload(Track.artists)
        )
        .order_by(PlaylistRun.created_at.desc())
        .limit(30)
    ).all()
    return [run_payload(run) for run in runs]


@router.get("/playlist-runs/{run_id}")
def playlist_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    run = db.scalar(
        select(PlaylistRun)
        .where(PlaylistRun.id == run_id)
        .options(
            selectinload(PlaylistRun.tracks)
            .selectinload(PlaylistRunTrack.track)
            .selectinload(Track.artists)
        )
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Playlist-Lauf nicht gefunden")
    return run_payload(run)


@router.post("/playlist-runs/{run_id}/publish")
def publish(run_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return run_payload(publish_run(db, run_id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SpotifyNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/playlist-runs/{run_id}/enqueue")
def enqueue(run_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return {"enqueued": enqueue_run(db, run_id), "queue_order_guaranteed": False}
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tracks")
def tracks(
    missing_features: bool = False,
    discovery: bool | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    query = select(Track).options(selectinload(Track.artists)).order_by(Track.name)
    if missing_features:
        query = query.where((Track.bpm.is_(None)) | (Track.camelot_key.is_(None)))
    if discovery is not None:
        query = query.where(Track.is_discovery.is_(discovery))
    return [track_payload(track) for track in db.scalars(query.limit(500)).all()]


@router.patch("/tracks/{track_id}/features")
def patch_track_features(
    track_id: str, payload: TrackFeaturePatch, db: Session = Depends(get_db)
) -> dict:
    track = db.scalar(
        select(Track).where(Track.id == track_id).options(selectinload(Track.artists))
    )
    if track is None:
        raise HTTPException(status_code=404, detail="Track nicht gefunden")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(track, key, value)
    if payload.musical_key is not None:
        track.camelot_key = to_camelot(payload.musical_key)
    track.feature_source = FeatureSource.manual
    track.feature_confidence = 1.0
    track.features_checked_at = datetime.now(UTC)
    db.commit()
    return track_payload(track)


@router.get("/sessions")
def sessions(db: Session = Depends(get_db)) -> list[dict]:
    items = db.scalars(
        select(ListeningSession)
        .options(selectinload(ListeningSession.profile), selectinload(ListeningSession.events))
        .order_by(ListeningSession.started_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": item.id,
            "started_at": item.started_at,
            "ended_at": item.ended_at,
            "profile_id": item.profile_id,
            "profile_name": item.profile.name if item.profile else None,
            "profile_confidence": item.profile_confidence,
            "assignment_reason": item.assignment_reason,
            "manually_corrected": item.manually_corrected,
            "event_count": len(item.events),
        }
        for item in items
    ]


@router.patch("/sessions/{session_id}/profile")
def patch_session_profile(
    session_id: str, payload: SessionProfilePatch, db: Session = Depends(get_db)
) -> dict:
    session = db.get(ListeningSession, session_id)
    if session is None or db.get(Profile, payload.profile_id) is None:
        raise HTTPException(status_code=404, detail="Session oder Profil nicht gefunden")
    session.profile_id = payload.profile_id
    session.profile_confidence = 1.0
    session.assignment_reason = "Manuell im Dashboard korrigiert"
    session.manually_corrected = True
    db.commit()
    return {"message": "Profilzuordnung gespeichert"}


@router.get("/profiles")
def profiles(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "id": profile.id,
            "name": profile.name,
            "is_primary": profile.is_primary,
            "preferred_genres": profile.preferred_genres,
            "excluded_track_ids": profile.excluded_track_ids,
        }
        for profile in db.scalars(select(Profile).order_by(Profile.name)).all()
    ]


@router.post("/profiles")
def create_profile(payload: ProfileCreate, db: Session = Depends(get_db)) -> dict:
    profile = Profile(name=payload.name, preferred_genres=payload.preferred_genres)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return {"id": profile.id, "name": profile.name}


@router.get("/settings/automation")
def get_automation(db: Session = Depends(get_db)) -> dict:
    configured = get_settings()
    setting = db.get(AppSetting, "automation")
    return (
        setting.value
        if setting
        else {
            "enabled": configured.automation_enabled,
            "daily_time": configured.automation_daily_time,
            "duration_minutes": configured.default_playlist_duration_minutes,
            "discovery_percent": configured.default_discovery_percent,
        }
    )


@router.patch("/settings/automation")
def patch_automation(payload: AutomationPatch, db: Session = Depends(get_db)) -> dict:
    setting = db.get(AppSetting, "automation") or AppSetting(key="automation")
    setting.value = payload.model_dump()
    db.add(setting)
    db.commit()
    return setting.value


@router.get("/system/status")
def system_status(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    spotify_credential = db.scalar(select(SpotifyCredential).limit(1))
    return {
        "services": {
            "database": {"status": "ok"},
            "spotify": {
                "configured": bool(settings.spotify_client_id and settings.spotify_client_secret),
                "connected": spotify_credential is not None,
            },
            "lastfm": {"configured": bool(settings.lastfm_api_key)},
            "getsongbpm": {"configured": bool(settings.getsongbpm_api_key)},
            "musicbrainz": {"configured": bool(settings.musicbrainz_contact_email)},
            "acousticbrainz": {
                "configured": bool(settings.musicbrainz_contact_email),
                "privacy": "Fallback ueber MusicBrainz-ID",
            },
            "openai": {
                "configured": bool(settings.openai_api_key),
                "privacy": "Nur manuelle Texteingaben werden uebertragen",
            },
        },
        "counts": {
            "tracks": db.scalar(select(func.count(Track.id))) or 0,
            "artists": db.scalar(select(func.count(Artist.id))) or 0,
            "events": db.scalar(select(func.count(ListeningEvent.id))) or 0,
            "devices": db.scalar(select(func.count(Device.id))) or 0,
        },
    }
