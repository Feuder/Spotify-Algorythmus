import logging
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db import SessionLocal
from app.models import AppSetting
from app.schemas import RecommendationIntent
from app.services.publishing import publish_run
from app.services.recommender import build_playlist
from app.services.sync import poll_current_playback, sync_spotify

logger = logging.getLogger(__name__)
settings = get_settings()


def automation_config() -> dict:
    with SessionLocal() as db:
        stored = db.get(AppSetting, "automation")
        return (
            stored.value
            if stored
            else {
                "enabled": settings.automation_enabled,
                "daily_time": settings.automation_daily_time,
                "duration_minutes": settings.default_playlist_duration_minutes,
                "discovery_percent": settings.default_discovery_percent,
            }
        )


def daily_playlist() -> None:
    config = automation_config()
    if not config["enabled"]:
        return
    with SessionLocal() as db:
        now = datetime.now(ZoneInfo(settings.app_timezone))
        if now.strftime("%H:%M") != config["daily_time"]:
            return
        marker = db.get(AppSetting, "last_daily_playlist")
        if marker and marker.value.get("date") == now.date().isoformat():
            return
        run = build_playlist(
            db,
            RecommendationIntent(
                context="taeglicher mix",
                duration_minutes=config["duration_minutes"],
                discovery_percent=config["discovery_percent"],
            ),
        )
        try:
            publish_run(db, run.id)
            marker = marker or AppSetting(key="last_daily_playlist")
            marker.value = {"date": now.date().isoformat(), "run_id": run.id}
            db.add(marker)
            db.commit()
        except Exception:
            logger.exception("Taegliche Playlist konnte nicht veroeffentlicht werden")


def periodic_sync() -> None:
    if not settings.spotify_client_id:
        return
    with SessionLocal() as db:
        try:
            sync_spotify(db)
            poll_current_playback(db)
        except Exception:
            logger.exception("Spotify-Synchronisierung fehlgeschlagen")


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.app_log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    scheduler = BackgroundScheduler(timezone=settings.app_timezone)
    scheduler.add_job(
        daily_playlist,
        "interval",
        minutes=1,
        id="daily-playlist",
        replace_existing=True,
    )
    scheduler.add_job(
        periodic_sync,
        "interval",
        minutes=15,
        id="spotify-sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Worker gestartet")
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()


if __name__ == "__main__":
    main()
