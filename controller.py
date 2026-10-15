"""Startpunkt fuer den kontextabhaengigen SOOMFON-Controller."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from streamdeck_app.autostart import AutostartError, AutostartManager, preferred_executable
from streamdeck_app.control import ControllerControl
from streamdeck_app.logging_setup import configure_logging
from streamdeck_app.paths import default_config_path
from streamdeck_app.service import run
from streamdeck_app.settings import SettingsError
from streamdeck_app.single_instance import SingleInstance


LOG = logging.getLogger("streamdeck")


def _report(message: str) -> None:
    LOG.info(message)
    if sys.stdout is not None:
        print(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        help="Pfad zur Konfiguration (Standard: LOCALAPPDATA)",
    )
    parser.add_argument("--verbose", action="store_true")
    autostart = parser.add_mutually_exclusive_group()
    autostart.add_argument("--install-autostart", action="store_true")
    autostart.add_argument("--remove-autostart", action="store_true")
    autostart.add_argument("--autostart-status", action="store_true")
    parser.add_argument(
        "--autostart-delay",
        type=float,
        default=10.0,
        help="Verzoegerung fuer einen neu installierten Autostart",
    )
    parser.add_argument(
        "--startup-delay",
        type=float,
        default=0.0,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dev-reload",
        action="store_true",
        help="Profildateien im Entwicklungsmodus ohne Neustart neu laden",
    )
    parser.add_argument(
        "--screensaver-now",
        action="store_true",
        help="Screensaver sofort starten (Vorschau/Test)",
    )
    parser.add_argument(
        "--run-seconds",
        type=float,
        help="Dienst nach dieser Zeit automatisch beenden (fuer Vorschau/Tests)",
    )
    parser.add_argument(
        "--no-tray",
        action="store_true",
        help="Ohne Windows-Infobereich starten",
    )
    args = parser.parse_args()
    if args.run_seconds is not None and args.run_seconds <= 0:
        parser.error("--run-seconds muss groesser als 0 sein")
    if not 0 <= args.autostart_delay <= 300:
        parser.error("--autostart-delay muss zwischen 0 und 300 liegen")
    if not 0 <= args.startup_delay <= 300:
        parser.error("--startup-delay muss zwischen 0 und 300 liegen")
    configure_logging(args.verbose)
    manager = AutostartManager()
    try:
        if args.install_autostart:
            executable = preferred_executable()
            command = manager.install(executable, args.autostart_delay)
            _report(f"Autostart installiert/repariert: {command}")
            return 0
        if args.remove_autostart:
            removed = manager.remove()
            _report("Autostart entfernt." if removed else "Autostart war nicht eingerichtet.")
            return 0
        if args.autostart_status:
            try:
                executable = preferred_executable()
            except AutostartError:
                executable = None
            status = manager.status(executable)
            if not status.installed:
                _report("Autostart: nicht installiert")
            elif not status.target_exists:
                _report(f"Autostart: veraltet, Ziel fehlt: {status.executable}")
            elif executable is not None and not status.matches_current:
                _report(f"Autostart: zeigt auf andere EXE: {status.executable}")
            else:
                _report(f"Autostart: aktiv: {status.command}")
            return 0
    except (AutostartError, OSError) as exc:
        LOG.error("Autostart-Aktion fehlgeschlagen: %s", exc)
        parser.error(str(exc))

    if args.startup_delay:
        LOG.info("Autostart-Verzoegerung: %.1f Sekunden", args.startup_delay)
        time.sleep(args.startup_delay)

    instance = SingleInstance()
    if not instance.acquire():
        LOG.info("Controller laeuft bereits; zweite Instanz wird beendet.")
        return 0
    config_path = args.config or default_config_path()
    try:
        use_tray = not args.no_tray and args.run_seconds is None
        if use_tray:
            from streamdeck_app.tray import TrayApplication

            control = ControllerControl()
            tray = TrayApplication(control, config_path)
            tray.run(
                lambda: run(
                    config_path,
                    screensaver_now=args.screensaver_now,
                    dev_reload=args.dev_reload,
                    control=control,
                )
            )
        else:
            run(
                config_path,
                screensaver_now=args.screensaver_now,
                run_seconds=args.run_seconds,
                dev_reload=args.dev_reload,
            )
    except SettingsError as exc:
        parser.error(str(exc))
    finally:
        instance.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
