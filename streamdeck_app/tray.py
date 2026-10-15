"""Windows notification-area menu for the running controller."""

from __future__ import annotations

import json
import logging
import os
import platform
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pystray
from PIL import Image, ImageDraw

from .autostart import AutostartManager, preferred_executable
from .control import ControllerControl
from .paths import default_log_path, user_data_dir
from .profiles import ALL_PROFILES


LOG = logging.getLogger("streamdeck")


def tray_icon_image() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((4, 4, 60, 60), radius=14, fill=(24, 34, 45), outline=(70, 210, 135), width=4)
    for y in (17, 35):
        for x in (16, 29, 42):
            draw.rounded_rectangle((x, y, x + 8, y + 8), radius=2, fill=(70, 210, 135))
    return image


def write_diagnostic_report(control: ControllerControl, config_path: Path) -> Path:
    status = control.snapshot()
    target = user_data_dir() / "diagnostic_report.json"
    payload = {
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "controller": status.__dict__,
        "config": str(config_path.resolve()),
        "log": str(default_log_path().resolve()),
        "executable": str(Path(sys.executable).resolve()),
        "frozen": bool(getattr(sys, "frozen", False)),
        "windows": platform.platform(),
        "python": platform.python_version(),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


class TrayApplication:
    def __init__(self, control: ControllerControl, config_path: Path) -> None:
        self.control = control
        self.config_path = config_path
        self.autostart = AutostartManager()
        self.editor = None
        self.worker: threading.Thread | None = None
        self.icon = pystray.Icon(
            "SoomfonController",
            tray_icon_image(),
            "SOOMFON Controller",
            self._menu(),
        )

    def _menu(self) -> pystray.Menu:
        profile_items = tuple(
            pystray.MenuItem(
                profile.name,
                self._select_profile(index),
                checked=self._profile_checked(profile.name),
                radio=True,
            )
            for index, profile in enumerate(ALL_PROFILES)
        )
        return pystray.Menu(
            pystray.MenuItem(self._status_text, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self._pause_text, self._toggle_pause, default=True),
            pystray.MenuItem("Screensaver umschalten", lambda _i, _m: self.control.request("screensaver")),
            pystray.MenuItem("Profil", pystray.Menu(*profile_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Konfiguration neu laden", self._reload),
            pystray.MenuItem("Profil-Editor öffnen", self._open_profile_editor),
            pystray.MenuItem("Konfiguration öffnen", self._open_config),
            pystray.MenuItem("Logdatei öffnen", self._open_log),
            pystray.MenuItem("Diagnosebericht erstellen", self._open_diagnostics),
            pystray.MenuItem(
                "Autostart",
                self._toggle_autostart,
                checked=self._autostart_checked,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Beenden", self._exit),
        )

    def _select_profile(self, index: int) -> Callable[[pystray.Icon, pystray.MenuItem], None]:
        def select(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
            self.control.request("profile", index)

        return select

    def _profile_checked(self, name: str) -> Callable[[pystray.MenuItem], bool]:
        def checked(_item: pystray.MenuItem) -> bool:
            return self.control.snapshot().profile == name

        return checked

    def _status_text(self, _item: pystray.MenuItem) -> str:
        status = self.control.snapshot()
        if status.error:
            return f"Fehler · {status.error[:45]}"
        connection = "verbunden" if status.connected else "warte auf Deck"
        mode = "pausiert" if status.paused else "Screensaver" if status.screensaver else status.profile
        return f"{connection} · {mode}"

    def _pause_text(self, _item: pystray.MenuItem) -> str:
        return "Fortsetzen" if self.control.snapshot().paused else "Pausieren"

    def _toggle_pause(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.control.request("pause")
        icon.update_menu()

    def _reload(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.control.request("reload")
        if icon.HAS_NOTIFICATION:
            icon.notify("Konfiguration wird neu geladen.", "SOOMFON Controller")

    def _open_config(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        os.startfile(self.config_path)

    def _open_profile_editor(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        if self.editor is None:
            from .profile_editor import ProfileEditorServer

            self.editor = ProfileEditorServer(
                self.config_path,
                lambda: self.control.request("reload"),
                on_boot_logo=lambda data: self.control.request("boot_logo", data),
                status_provider=lambda: self.control.snapshot().boot_logo_status,
            )
        self.editor.open()

    def _open_log(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        path = default_log_path()
        path.touch(exist_ok=True)
        os.startfile(path)

    def _open_diagnostics(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        os.startfile(write_diagnostic_report(self.control, self.config_path))

    def _toggle_autostart(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        executable = preferred_executable()
        status = self.autostart.status(executable)
        if status.installed and status.matches_current:
            self.autostart.remove()
            message = "Autostart deaktiviert."
        else:
            self.autostart.install(executable, 10)
            message = "Autostart aktiviert/repariert."
        if icon.HAS_NOTIFICATION:
            icon.notify(message, "SOOMFON Controller")
        icon.update_menu()

    def _autostart_checked(self, _item: pystray.MenuItem) -> bool:
        try:
            status = self.autostart.status(preferred_executable())
            return status.installed and status.matches_current and status.target_exists
        except (OSError, RuntimeError):
            return False

    def _exit(self, icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self.control.request("exit")
        icon.stop()

    def run(self, controller_target: Callable[[], None]) -> None:
        def setup(icon: pystray.Icon) -> None:
            icon.visible = True

            def worker() -> None:
                try:
                    controller_target()
                except Exception as exc:
                    LOG.exception("Controller-Dienst abgebrochen")
                    self.control.update(error=str(exc), connected=False)
                finally:
                    icon.stop()

            self.worker = threading.Thread(target=worker, name="controller", daemon=True)
            self.worker.start()

        self.icon.run(setup=setup)
        self.control.request("exit")
        if self.editor is not None:
            self.editor.stop()
        if self.worker is not None:
            self.worker.join(timeout=3.0)
