"""Thread-safe live user guidance for active and upcoming generations."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading


class GuidanceManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._pending: list[dict] = []
        self._messages: list[dict] = []
        self._project: Path | None = None

    def add(self, message: str) -> dict:
        item = {"timestamp": datetime.now(timezone.utc).isoformat(), "message": str(message).strip()}
        with self._lock:
            (self._messages if self._active else self._pending).append(item)
            project = self._project if self._active else None
            active = self._active
        if project:
            self._persist(project, item)
        return {**item, "active_generation": active}

    def start_generation(self) -> None:
        with self._lock:
            self._active = True
            self._messages = self._pending
            self._pending = []
            self._project = None

    def attach_project(self, project: Path) -> None:
        with self._lock:
            self._project = Path(project)
            messages = list(self._messages)
        for item in messages:
            self._persist(Path(project), item)

    def finish_generation(self) -> None:
        with self._lock:
            self._active = False
            self._messages = []
            self._project = None

    def context(self, max_chars: int = 8000) -> str:
        with self._lock:
            messages = list(self._messages)
        rendered = "\n".join(f"- [{item['timestamp']}] {item['message']}" for item in messages)
        return rendered[-max_chars:]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "active_generation": self._active,
                "active_count": len(self._messages),
                "pending_count": len(self._pending),
            }

    @staticmethod
    def _persist(project: Path, item: dict) -> None:
        path = project / ".bookgen" / "guidance.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")


guidance_manager = GuidanceManager()
