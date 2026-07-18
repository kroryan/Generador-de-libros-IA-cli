"""Cooperative pause, resume, and cancellation for one generation process."""

from __future__ import annotations

import subprocess
import threading


class GenerationCancelled(RuntimeError):
    """Raised at a safe checkpoint after cancellation was requested."""


class GenerationControl:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._paused = False
        self._cancel_requested = False
        self._process: subprocess.Popen | None = None

    def reset(self) -> None:
        with self._condition:
            self._paused = False
            self._cancel_requested = False
            self._process = None
            self._condition.notify_all()

    def pause(self) -> dict:
        with self._condition:
            if not self._cancel_requested:
                self._paused = True
            return self.snapshot()

    def resume(self) -> dict:
        with self._condition:
            self._paused = False
            self._condition.notify_all()
            return self.snapshot()

    def cancel(self) -> dict:
        process = None
        with self._condition:
            self._cancel_requested = True
            self._paused = False
            process = self._process
            self._condition.notify_all()
        if process and process.poll() is None:
            process.terminate()
        return self.snapshot()

    def checkpoint(self) -> None:
        with self._condition:
            while self._paused and not self._cancel_requested:
                self._condition.wait(timeout=0.5)
            if self._cancel_requested:
                raise GenerationCancelled("Generation cancelled by the user")

    def register_process(self, process: subprocess.Popen) -> None:
        with self._condition:
            if self._cancel_requested:
                process.terminate()
                raise GenerationCancelled("Generation cancelled by the user")
            self._process = process

    def unregister_process(self, process: subprocess.Popen) -> None:
        with self._condition:
            if self._process is process:
                self._process = None

    def snapshot(self) -> dict:
        # RLock semantics are provided by Condition's default lock.
        with self._condition:
            return {
                "paused": self._paused,
                "cancel_requested": self._cancel_requested,
            }


generation_control = GenerationControl()
