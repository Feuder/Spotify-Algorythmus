from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.integrations.spotify import SpotifyClient
from app.models import PlaylistRun, PlaylistRunTrack, RunStatus


def publish_run(db: Session, run_id: str) -> PlaylistRun:
    run = db.scalar(
        select(PlaylistRun)
        .where(PlaylistRun.id == run_id)
        .options(selectinload(PlaylistRun.tracks).selectinload(PlaylistRunTrack.track))
    )
    if run is None:
        raise LookupError("Playlist-Lauf nicht gefunden")
    spotify = SpotifyClient(db)
    if run.spotify_playlist_id:
        playlist_id = run.spotify_playlist_id
        playlist_url = run.spotify_playlist_url
    else:
        today = datetime.now(UTC).date()
        start = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
        prior_today = db.scalar(
            select(PlaylistRun)
            .where(
                PlaylistRun.id != run.id,
                PlaylistRun.created_at >= start,
                PlaylistRun.created_at < start + timedelta(days=1),
                PlaylistRun.spotify_playlist_id.is_not(None),
            )
            .order_by(PlaylistRun.created_at.desc())
            .limit(1)
        )
        if prior_today:
            playlist_id = prior_today.spotify_playlist_id
            playlist_url = prior_today.spotify_playlist_url
        else:
            name = f"Resonanz - {date.today().isoformat()}"
            playlist = spotify.create_private_playlist(
                name,
                f"Automatisch erstellt mit Resonanz ({run.algorithm_version})",
            )
            playlist_id = playlist["id"]
            playlist_url = playlist.get("external_urls", {}).get("spotify")
    uris = [item.track.uri for item in run.tracks if item.track.uri]
    spotify.replace_playlist_items(playlist_id, uris)
    run.spotify_playlist_id = playlist_id
    run.spotify_playlist_url = playlist_url
    run.status = RunStatus.published
    db.commit()
    return run


def enqueue_run(db: Session, run_id: str) -> int:
    if not get_settings().allow_queue_assistant:
        raise PermissionError("Queue-Assistent ist in der zentralen .env deaktiviert")
    run = db.scalar(
        select(PlaylistRun)
        .where(PlaylistRun.id == run_id)
        .options(selectinload(PlaylistRun.tracks).selectinload(PlaylistRunTrack.track))
    )
    if run is None:
        raise LookupError("Playlist-Lauf nicht gefunden")
    spotify = SpotifyClient(db)
    count = 0
    for item in run.tracks:
        if item.track.uri:
            spotify.enqueue(item.track.uri)
            count += 1
    return count
