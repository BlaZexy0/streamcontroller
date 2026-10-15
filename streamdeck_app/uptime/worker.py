"""Background refresh for Uptime Kuma so HID input never waits on the network."""

from __future__ import annotations

import threading

from .model import MonitorStatus
from .provider import UptimeKumaProvider, UptimeProviderError


class UptimeWorker:
    def __init__(self, provider: UptimeKumaProvider, *, refresh_seconds: float) -> None:
        self.provider = provider
        self.refresh_seconds = refresh_seconds
        self._monitors: tuple[MonitorStatus, ...] = ()
        self._error: str | None = None
        self._revision = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="uptime-kuma", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def snapshot(self) -> tuple[int, tuple[MonitorStatus, ...], str | None]:
        with self._lock:
            return self._revision, self._monitors, self._error

    def refresh_once(self) -> None:
        try:
            monitors = self.provider.fetch()
            error = None
        except (UptimeProviderError, OSError, ValueError) as exc:
            monitors = None
            error = str(exc)
        with self._lock:
            if monitors is not None:
                self._monitors = monitors
            self._error = error
            self._revision += 1

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh_once()
            if self._stop.wait(self.refresh_seconds):
                return

