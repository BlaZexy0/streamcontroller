"""Thread-safe command and status bridge between tray and controller loop."""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ControllerStatus:
    connected: bool = False
    paused: bool = False
    screensaver: bool = False
    profile: str = "Startet ..."
    profiles: tuple[str, ...] = ()
    error: str | None = None
    boot_logo_status: str | None = None


class ControllerControl:
    def __init__(self) -> None:
        self._commands: queue.SimpleQueue[tuple[str, Any]] = queue.SimpleQueue()
        self._lock = threading.Lock()
        self._status = ControllerStatus()
        self.stop_requested = threading.Event()

    def request(self, command: str, value: Any = None) -> None:
        if command == "exit":
            self.stop_requested.set()
        self._commands.put((command, value))

    def commands(self) -> list[tuple[str, Any]]:
        result: list[tuple[str, Any]] = []
        while True:
            try:
                result.append(self._commands.get_nowait())
            except queue.Empty:
                return result

    def update(self, **changes: Any) -> None:
        with self._lock:
            current = self._status.__dict__ | changes
            self._status = ControllerStatus(**current)

    def snapshot(self) -> ControllerStatus:
        with self._lock:
            return self._status
