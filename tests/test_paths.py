from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamdeck_app.paths import default_config_path, resource_path, user_data_dir


class ApplicationPathTests(unittest.TestCase):
    def test_bundled_resources_are_addressable(self) -> None:
        self.assertTrue(resource_path("config.json").is_file())
        self.assertTrue(resource_path("assets", "screensaver", "emberling.png").is_file())

    def test_default_configuration_is_copied_to_local_app_data_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                target = default_config_path()
                self.assertEqual(target.parent, Path(directory) / "SoomfonController")
                self.assertEqual(json.loads(target.read_text(encoding="utf-8"))["brightness"], 65)

                target.write_text('{"custom": true}', encoding="utf-8")
                self.assertEqual(default_config_path().read_text(encoding="utf-8"), '{"custom": true}')

    def test_querying_user_directory_can_be_side_effect_free(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}):
                target = user_data_dir(create=False)
                self.assertFalse(target.exists())
