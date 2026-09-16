"""Startpunkt fuer den kontextabhaengigen SOOMFON-Controller."""

from __future__ import annotations

import argparse
from pathlib import Path

from streamdeck_app.logging_setup import configure_logging
from streamdeck_app.paths import default_config_path
from streamdeck_app.service import run
from streamdeck_app.settings import SettingsError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        help="Pfad zur Konfiguration (Standard: LOCALAPPDATA)",
    )
    parser.add_argument("--verbose", action="store_true")
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
    args = parser.parse_args()
    if args.run_seconds is not None and args.run_seconds <= 0:
        parser.error("--run-seconds muss groesser als 0 sein")
    configure_logging(args.verbose)
    config_path = args.config or default_config_path()
    try:
        run(
            config_path,
            screensaver_now=args.screensaver_now,
            run_seconds=args.run_seconds,
            dev_reload=args.dev_reload,
        )
    except SettingsError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
