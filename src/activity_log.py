"""Thread-safe, bounded activity journal for generation observability."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import threading


MAX_MESSAGE_LENGTH = 12_000


@dataclass(frozen=True)
class ActivityEvent:
    sequence: int
    timestamp: str
    source: str
    kind: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


class ActivityLog:
    """Keeps recent generation events without allowing unbounded growth."""

    def __init__(self, max_events: int = 1_000):
        self._events: deque[ActivityEvent] = deque(maxlen=max_events)
        self._sequence = 0
        self._lock = threading.Lock()

    def reset(self) -> None:
        """Clear an old run while preserving monotonic event sequence numbers."""
        with self._lock:
            self._events.clear()

    def emit(self, message: object, kind: str = "info", source: str = "pipeline") -> ActivityEvent:
        text = str(message).strip()
        if not text:
            text = "Activity event"
        if len(text) > MAX_MESSAGE_LENGTH:
            text = f"{text[:MAX_MESSAGE_LENGTH]}\n[output truncated]"
        with self._lock:
            self._sequence += 1
            event = ActivityEvent(
                sequence=self._sequence,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=source,
                kind=kind,
                message=text,
            )
            self._events.append(event)
            return event

    def snapshot(self, after: int = 0, limit: int = 250) -> dict:
        safe_limit = max(1, min(int(limit), 1_000))
        with self._lock:
            matching = [event.to_dict() for event in self._events if event.sequence > after]
            events = matching[:safe_limit]
            return {
                "events": events,
                "last_sequence": events[-1]["sequence"] if events else self._sequence,
                "has_more": len(matching) > safe_limit,
            }


activity_log = ActivityLog()
