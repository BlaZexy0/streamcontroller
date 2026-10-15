from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from streamdeck_app.autostart import (
    RUN_KEY,
    VALUE_NAME,
    AutostartManager,
    build_command,
    command_executable,
)
from streamdeck_app.single_instance import SingleInstance


class AutostartTests(unittest.TestCase):
    def test_command_quotes_executable_and_contains_delay(self) -> None:
        executable = Path(r"C:\Program Files\Soomfon Controller\SoomfonController.exe")
        command = build_command(executable, 12.5)
        self.assertTrue(command.startswith('"'))
        self.assertEqual(command_executable(command), executable)
        self.assertIn("--startup-delay 12.5", command)

    def test_install_uses_current_user_run_key(self) -> None:
        manager = AutostartManager()
        key = MagicMock()
        context = MagicMock()
        context.__enter__.return_value = key
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Soomfon Controller.exe"
            executable.touch()
            with (
                patch("streamdeck_app.autostart.winreg.CreateKeyEx", return_value=context) as create,
                patch("streamdeck_app.autostart.winreg.SetValueEx") as set_value,
            ):
                command = manager.install(executable, 10)

        create.assert_called_once()
        self.assertEqual(create.call_args.args[1], RUN_KEY)
        set_value.assert_called_once()
        self.assertEqual(set_value.call_args.args[1], VALUE_NAME)
        self.assertEqual(set_value.call_args.args[4], command)

    def test_status_detects_missing_registered_executable(self) -> None:
        manager = AutostartManager()
        with patch.object(
            manager,
            "read_command",
            return_value='"C:\\missing\\SoomfonController.exe" --startup-delay 10',
        ):
            status = manager.status()
        self.assertTrue(status.installed)
        self.assertFalse(status.target_exists)


class SingleInstanceTests(unittest.TestCase):
    def test_second_mutex_instance_is_rejected_until_first_closes(self) -> None:
        name = f"Local\\SoomfonController_Test_{uuid.uuid4()}"
        first = SingleInstance(name)
        second = SingleInstance(name)
        third = SingleInstance(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
            first.close()
            self.assertTrue(third.acquire())
        finally:
            first.close()
            second.close()
            third.close()


if __name__ == "__main__":
    unittest.main()
