"""Manually selected overview of services published by Uptime Kuma."""

from __future__ import annotations

from ..screens.uptime import uptime_message_tile, uptime_tile
from ..uptime import UptimeKumaProvider, UptimeWorker
from .model import Button, Profile, ProfileContext, ProfileLifecycle


class UptimeLifecycle(ProfileLifecycle):
    def __init__(self) -> None:
        self.worker: UptimeWorker | None = None
        self.last_revision = -1
        self.page = 0

    def on_activate(self, context: ProfileContext) -> None:
        self.last_revision = -1
        self.page = 0
        settings = context.settings
        if settings is None or not settings.uptime_kuma_enabled:
            self._render_message(context, "KUMA AUS", "in config aktivieren")
            return
        if not settings.uptime_kuma_status_page:
            self._render_message(context, "SETUP", "Statusseite eintragen")
            return
        self.worker = UptimeWorker(
            UptimeKumaProvider(
                settings.uptime_kuma_url,
                settings.uptime_kuma_status_page,
                timeout_seconds=settings.uptime_kuma_timeout_seconds,
            ),
            refresh_seconds=settings.uptime_kuma_refresh_seconds,
        )
        self.worker.start()
        self._render(context)

    def on_deactivate(self, context: ProfileContext) -> None:
        if self.worker is not None:
            self.worker.stop()
        self.worker = None

    def on_tick(self, context: ProfileContext, now: float) -> None:
        if self.worker is None:
            return
        revision, _monitors, _error = self.worker.snapshot()
        if revision != self.last_revision:
            self._render(context)

    def on_button(self, context: ProfileContext, index: int, pressed: bool) -> bool:
        if pressed and context.settings is not None and context.settings.uptime_kuma_url:
            context.run_action({"type": "open", "target": context.settings.uptime_kuma_url + "/dashboard"})
        return True

    def on_encoder(self, context: ProfileContext, index: int, direction: str) -> bool:
        if index != 2 or self.worker is None:
            return False
        _revision, monitors, _error = self.worker.snapshot()
        pages = max(1, (len(monitors) + 5) // 6)
        self.page = (self.page + (1 if direction == "right" else -1)) % pages
        self._render(context)
        return True

    def _render(self, context: ProfileContext) -> None:
        assert self.worker is not None
        revision, monitors, error = self.worker.snapshot()
        pages = max(1, (len(monitors) + 5) // 6)
        self.page %= pages
        visible = monitors[self.page * 6 : self.page * 6 + 6]
        if not visible:
            if error:
                self._render_message(context, "FEHLER", "Kuma nicht erreichbar")
            else:
                self._render_message(context, "LADEN", "Dienste werden geladen")
        else:
            for index in range(6):
                if index < len(visible):
                    image = uptime_tile(visible[index], page=self.page + 1, pages=pages)
                else:
                    image = uptime_message_tile("FREI")
                context.set_key_image(index, image)
        self.last_revision = revision

    @staticmethod
    def _render_message(context: ProfileContext, title: str, detail: str) -> None:
        for index in range(6):
            context.set_key_image(index, uptime_message_tile(title if index == 0 else "KUMA", detail))


PROFILE = Profile(
    name="Dienste",
    processes=("uptime-kuma-dashboard.exe",),
    order=50,
    lifecycle_factory=UptimeLifecycle,
    buttons=tuple(
        Button(f"DIENST{index}", (35, 70, 58)) for index in range(1, 7)
    ),
)
