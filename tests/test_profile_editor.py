from __future__ import annotations

import json
import base64
import io
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

from streamdeck_app.profile_editor import ProfileEditorServer
from streamdeck_app.profile_overrides import (
    load_profiles,
    profiles_document,
    profiles_from_document,
    profiles_path,
    save_profiles,
)
from streamdeck_app.profiles import ALL_PROFILES
from streamdeck_app.settings import SettingsError


class ProfileDocumentTests(unittest.TestCase):
    def test_roundtrip_preserves_buttons_and_dynamic_lifecycles(self) -> None:
        document = profiles_document(ALL_PROFILES)
        profiles = profiles_from_document(document, ALL_PROFILES)
        spotify_original = next(profile for profile in ALL_PROFILES if profile.name == "Spotify")
        spotify_loaded = next(profile for profile in profiles if profile.name == "Spotify")
        self.assertEqual(spotify_loaded.buttons, spotify_original.buttons)
        self.assertIs(spotify_loaded.lifecycle_factory, spotify_original.lifecycle_factory)

    def test_document_requires_one_fallback_profile(self) -> None:
        document = profiles_document(ALL_PROFILES)
        for profile in document["profiles"]:
            if not profile["processes"]:
                profile["processes"] = ["desktop.exe"]
        with self.assertRaisesRegex(SettingsError, "Fallback"):
            profiles_from_document(document)

    def test_save_and_load_use_profiles_json_next_to_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{}", encoding="utf-8")
            document = profiles_document(ALL_PROFILES)
            document["profiles"][0]["buttons"][0]["label"] = "TEST"
            save_profiles(config, document, ALL_PROFILES)

            loaded = load_profiles(config, ALL_PROFILES)
            self.assertEqual(loaded[0].buttons[0].label, "TEST")
            self.assertEqual(profiles_path(config), Path(directory) / "profiles.json")


class ProfileEditorServerTests(unittest.TestCase):
    def test_local_api_requires_token_and_saves_valid_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{}", encoding="utf-8")
            saved: list[bool] = []
            server = ProfileEditorServer(config, lambda: saved.append(True))
            url = server.start()
            try:
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(url.split("?", 1)[0] + "api/profiles")
                self.assertEqual(denied.exception.code, 403)

                api_url = url.replace("/?", "/api/profiles?")
                with urllib.request.urlopen(api_url) as response:
                    document = json.loads(response.read())
                document["profiles"][0]["buttons"][0]["label"] = "WEB"
                request = urllib.request.Request(
                    api_url,
                    data=json.dumps(document).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    result = json.loads(response.read())

                self.assertEqual(result["profiles"][0]["buttons"][0]["label"], "WEB")
                self.assertEqual(saved, [True])
                self.assertTrue(profiles_path(config).is_file())
            finally:
                server.stop()

    def test_boot_logo_api_sanitizes_saves_and_queues_transport_jpeg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "config.json"
            config.write_text("{}", encoding="utf-8")
            queued: list[bytes] = []
            server = ProfileEditorServer(
                config,
                lambda: None,
                on_boot_logo=queued.append,
                status_provider=lambda: "bereit",
            )
            url = server.start()
            try:
                source = io.BytesIO()
                Image.new("RGB", (640, 480), "navy").save(source, format="PNG")
                payload = {
                    "image": "data:image/png;base64,"
                    + base64.b64encode(source.getvalue()).decode("ascii")
                }
                api_url = url.replace("/?", "/api/boot-logo?")
                request = urllib.request.Request(
                    api_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    result = json.loads(response.read())

                self.assertTrue(result["image"].startswith("data:image/jpeg;base64,"))
                self.assertEqual(len(queued), 1)
                with Image.open(io.BytesIO(queued[0])) as image:
                    self.assertEqual(image.size, (240, 320))
                self.assertTrue(config.with_name("boot_logo.jpg").is_file())
            finally:
                server.stop()


if __name__ == "__main__":
    unittest.main()
