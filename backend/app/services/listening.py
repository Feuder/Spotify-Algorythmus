from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(slots=True)
class EventSignal:
    played_at: datetime
    duration_ms: int
    progress_ms: int | None = None
    track_id: str | None = None


def estimate_skip(progress_ms: int | None, duration_ms: int | None) -> bool | None:
    if progress_ms is None or not duration_ms or duration_ms <= 0:
        return None
    if progress_ms < 30_000:
        return True
    if progress_ms / duration_ms < 0.35:
        return True
    if progress_ms / duration_ms > 0.85:
        return False
    return None


def sessionize(events: Iterable[EventSignal], gap_minutes: int = 30) -> list[list[EventSignal]]:
    ordered = sorted(events, key=lambda event: event.played_at)
    sessions: list[list[EventSignal]] = []
    for event in ordered:
        if not sessions:
            sessions.append([event])
            continue
        previous = sessions[-1][-1]
        if event.played_at - previous.played_at > timedelta(minutes=gap_minutes):
            sessions.append([event])
        else:
            sessions[-1].append(event)
    return sessions


def mark_repetitions(events: list[EventSignal], within_minutes: int = 60) -> list[bool]:
    last_seen: dict[str, datetime] = {}
    flags: list[bool] = []
    for event in sorted(events, key=lambda item: item.played_at):
        previous = last_seen.get(event.track_id or "")
        repeated = bool(
            previous and event.played_at - previous <= timedelta(minutes=within_minutes)
        )
        flags.append(repeated)
        if event.track_id:
            last_seen[event.track_id] = event.played_at
    return flags
