from __future__ import annotations

import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from streamdeck_app.boot_logo import prepare_boot_logo
from streamdeck_app.control import ControllerControl
from streamdeck_app.core.foreground import ForegroundWindow
from streamdeck_app.service import ControllerService
from streamdeck_app.testing import MockDeck
from streamdeck_app.tray import TrayApplication, tray_icon_image, write_diagnostic_report


ROOT = Path(__file__).resolve().parent.parent


class ControllerControlTests(unittest.TestCase):
    def test_status_and_commands_are_thread_safe_value_objects(self) -> None:
        control = ControllerControl()
        control.update(connected=True, profile="Discord", profiles=("Desktop", "Discord"))
        control.request("profile", 1)
        control.request("exit")

        status = control.snapshot()
        self.assertTrue(status.connected)
        self.assertEqual(status.profile, "Discord")
        self.assertEqual(control.commands(), [("profile", 1), ("exit", None)])
        self.assertTrue(control.stop_requested.is_set())


class TrayCommandTests(unittest.TestCase):
    def _service(self, control: ControllerControl, config: Path = ROOT / "config.json") -> ControllerService:
        return ControllerService(
            config,
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            control=control,
        )

    def test_pause_resume_screensaver_and_profile_commands(self) -> None:
        control = ControllerControl()
        service = self._service(control)
        deck = MockDeck()
        service.activate_profile(deck, service.resolve_profile("code.exe"))

        control.request("pause")
        service.process_control_commands(deck)
        self.assertTrue(service.paused)
        self.assertEqual(deck.operations[-1], "clear")

        control.request("pause")
        service.process_control_commands(deck)
        self.assertFalse(service.paused)

        control.request("screensaver")
        service.process_control_commands(deck)
        self.assertTrue(service.idle)

        control.request("profile", 0)
        service.process_control_commands(deck)
        self.assertFalse(service.paused)
        self.assertTrue(service.locked)
        self.assertEqual(service.profile.name, "Desktop")

    def test_configuration_reload_applies_new_brightness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            data = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
            config.write_text(json.dumps(data), encoding="utf-8")
            control = ControllerControl()
            service = self._service(control, config)
            deck = MockDeck()

            data["brightness"] = 42
            config.write_text(json.dumps(data), encoding="utf-8")
            control.request("reload")
            service.process_control_commands(deck)

            self.assertEqual(service.settings.brightness, 42)
            self.assertIn("brightness:42", deck.operations)

    def test_boot_logo_command_is_written_by_the_connected_service(self) -> None:
        control = ControllerControl()
        service = self._service(control)
        deck = MockDeck()
        source = io.BytesIO()
        Image.new("RGB", (320, 240), "green").save(source, format="PNG")
        _preview, transport = prepare_boot_logo(source.getvalue())

        control.request("boot_logo", transport)
        service.process_control_commands(deck)

        self.assertEqual(deck.boot_logo, transport)
        self.assertEqual(
            control.snapshot().boot_logo_status,
            "Bootlogo wurde dauerhaft gespeichert.",
        )


class TrayUtilityTests(unittest.TestCase):
    def test_icon_and_diagnostic_report_are_generated_locally(self) -> None:
        self.assertEqual(tray_icon_image().size, (64, 64))
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {"LOCALAPPDATA": directory}):
                config = Path(directory) / "config.json"
                config.write_text("{}", encoding="utf-8")
                report = write_diagnostic_report(ControllerControl(), config)
                payload = json.loads(report.read_text(encoding="utf-8"))
                self.assertIn("controller", payload)
                self.assertEqual(Path(payload["config"]), config)

    def test_tray_menu_can_be_constructed(self) -> None:
        application = TrayApplication(ControllerControl(), ROOT / "config.json")
        self.assertEqual(application.icon.name, "SoomfonController")


if __name__ == "__main__":
    unittest.main()
