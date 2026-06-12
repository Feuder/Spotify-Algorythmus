from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import ListeningEvent, ListeningSession, Profile


@dataclass(slots=True)
class ProfileAssignment:
    profile_id: str | None
    confidence: float
    reason: str


def guest_profile_assignment(
    *,
    primary_history_size: int,
    suspicious_track_count: int,
    genre_distance: float,
    skip_pattern_distance: float,
    guest_profile_id: str | None,
) -> ProfileAssignment:
    if primary_history_size < 50:
        return ProfileAssignment(None, 0.0, "Noch keine ausreichende Hauptprofil-Basis")
    if suspicious_track_count < 3:
        return ProfileAssignment(None, 0.0, "Weniger als drei auffaellige Tracks")
    confidence = min(1.0, 0.55 + genre_distance * 0.3 + skip_pattern_distance * 0.15)
    if confidence < 0.90 or not guest_profile_id:
        return ProfileAssignment(None, confidence, "Gastprofil-Konfidenz unter 0,90")
    return ProfileAssignment(
        guest_profile_id,
        confidence,
        "Mindestens drei Tracks weichen deutlich vom Hauptprofil ab",
    )


def assign_unclassified_sessions(db: Session) -> int:
    primary = db.scalar(select(Profile).where(Profile.is_primary.is_(True)).limit(1))
    guest = db.scalar(select(Profile).where(Profile.is_primary.is_(False)).limit(1))
    if primary is None or guest is None:
        return 0
    primary_history_size = (
        db.scalar(
            select(func.count(ListeningEvent.id))
            .join(ListeningSession)
            .where(ListeningSession.profile_id == primary.id)
        )
        or 0
    )
    sessions = db.scalars(
        select(ListeningSession)
        .where(ListeningSession.profile_id.is_(None))
        .options(selectinload(ListeningSession.events).selectinload(ListeningEvent.track))
    ).all()
    assigned = 0
    preferred = set(primary.preferred_genres)
    for session in sessions:
        suspicious = sum(1 for event in session.events if not (preferred & set(event.track.genres)))
        assignment = guest_profile_assignment(
            primary_history_size=primary_history_size,
            suspicious_track_count=suspicious,
            genre_distance=min(1.0, suspicious / max(1, len(session.events))),
            skip_pattern_distance=0.6,
            guest_profile_id=guest.id,
        )
        if assignment.profile_id:
            session.profile_id = assignment.profile_id
            session.profile_confidence = assignment.confidence
            session.assignment_reason = assignment.reason
            assigned += 1
    db.commit()
    return assigned
