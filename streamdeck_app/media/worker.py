"""Low-frequency background reader for a local media session."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Awaitable, Callable
from typing import Protocol

from .model import MediaState


class MediaProvider(Protocol):
    def fetch(self) -> Awaitable[MediaState]: ...


class MediaSessionWorker:
    def __init__(
        self,
        provider: MediaProvider,
        *,
        refresh_seconds: float = 2.0,
        runner: Callable[[Awaitable[MediaState]], MediaState] = asyncio.run,
    ) -> None:
        self.provider = provider
        self.refresh_seconds = refresh_seconds
        self.runner = runner
        self._state = MediaState()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.revision = 0

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="spotify-media",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def snapshot(self) -> tuple[int, MediaState]:
        with self._lock:
            return self.revision, self._state

    def refresh_once(self) -> None:
        try:
            state = self.runner(self.provider.fetch())
        except Exception as exc:
            state = MediaState(error=str(exc))
        with self._lock:
            if state != self._state:
                self._state = state
                self.revision += 1

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh_once()
            if self._stop.wait(self.refresh_seconds):
                return
