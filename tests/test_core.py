from __future__ import annotations

import io
import unittest
import tempfile
from pathlib import Path

from PIL import Image

from streamdeck_app.core.device import JPEG_SIZE, REPORT_SIZE, decode_event, encode_image
from streamdeck_app.profiles import ALL_PROFILES, ProfileLifecycle, discover_profiles
from streamdeck_app.profiles.runtime import ProfileRuntime
from streamdeck_app.profiles.reload import ProfileReloader
from streamdeck_app.core.foreground import ForegroundWindow
from streamdeck_app.testing import MockDeck
from streamdeck_app.screens.profile_screen import profile_tile
from streamdeck_app.screens.screensaver import CREATURES, IdleAnimation
from streamdeck_app.service import ControllerService


ROOT = Path(__file__).resolve().parent.parent


class DeviceProtocolTests(unittest.TestCase):
    def test_key_event_decoding(self) -> None:
        report = bytearray(512)
        report[:3] = b"ACK"
        report[9] = 0x01
        report[10] = 1
        self.assertEqual(decode_event(bytes(report)), ("key", 0, True))

    def test_encoder_event_decoding(self) -> None:
        report = bytearray(512)
        report[:3] = b"ACK"
        report[9] = 0x61
        report[10] = 1
        self.assertEqual(decode_event(bytes(report)), ("encoder", 2, 1))

    def test_image_encoder_produces_jpeg(self) -> None:
        data = encode_image(Image.new("RGB", (60, 60), "red"))
        self.assertTrue(data.startswith(b"\xff\xd8"))
        self.assertLess(len(data), REPORT_SIZE * 10)

    def test_image_encoder_uses_native_mcu_size_and_preserves_contrast(self) -> None:
        image = Image.new("RGB", (60, 60), "black")
        pixels = image.load()
        for y in range(60):
            for x in range(60):
                if (x // 4 + y // 4) % 2 == 0:
                    pixels[x, y] = (255, 255, 255)

        encoded = encode_image(image)
        decoded = Image.open(io.BytesIO(encoded)).convert("RGB")
        self.assertEqual(decoded.size, JPEG_SIZE)
        light = decoded.getpixel((2, 2))[0]
        dark = decoded.getpixel((7, 2))[0]
        self.assertGreater(abs(light - dark), 240)


class ProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ControllerService(ROOT / "config.json")

    def test_matching_profiles(self) -> None:
        self.assertEqual(self.service.profiles[self.service.resolve_profile("Code.exe")].name, "VS Code")
        self.assertEqual(self.service.profiles[self.service.resolve_profile("chrome.exe")].name, "Browser")
        self.assertEqual(self.service.profiles[self.service.resolve_profile("unknown.exe")].name, "Desktop")

    def test_configuration_has_six_buttons_per_profile(self) -> None:
        for profile in ALL_PROFILES:
            self.assertEqual(len(profile.buttons), 6, profile.name)

    def test_profiles_are_discovered_in_configured_order(self) -> None:
        discovered = discover_profiles()
        self.assertEqual(discovered, ALL_PROFILES)
        self.assertEqual(
            [profile.name for profile in discovered],
            ["Desktop", "Browser", "VS Code", "Explorer", "Spotify"],
        )

    def test_profile_tile_size(self) -> None:
        tile = profile_tile(self.service.profiles[0].buttons[0])
        self.assertEqual(tile.size, (60, 60))

    def test_profile_runtime_owns_debounced_selection_state(self) -> None:
        runtime = ProfileRuntime(ALL_PROFILES)
        vscode_index = runtime.resolve("code.exe")

        self.assertIsNone(runtime.observe_process("code.exe", 1.0, 0.2))
        self.assertEqual(runtime.candidate_index, vscode_index)
        self.assertIsNone(runtime.observe_process("code.exe", 1.1, 0.2))
        self.assertEqual(runtime.observe_process("code.exe", 1.21, 0.2), vscode_index)

    def test_dev_reloader_only_loads_after_a_source_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_dir = Path(directory)
            source = profile_dir / "example.py"
            source.write_text("PROFILE = 1\n", encoding="utf-8")
            calls: list[bool] = []

            def load_profiles():  # type: ignore[no-untyped-def]
                calls.append(True)
                return ALL_PROFILES

            reloader = ProfileReloader(
                profile_dir=profile_dir,
                loader=load_profiles,
                interval_seconds=1.0,
            )
            self.assertIsNone(reloader.poll(0.0))
            source.write_text("PROFILE = 2\n", encoding="utf-8")
            self.assertIsNone(reloader.poll(0.5))
            self.assertEqual(reloader.poll(1.0), ALL_PROFILES)
            self.assertEqual(len(calls), 1)

    def test_profile_lifecycle_receives_all_events(self) -> None:
        events: list[str] = []

        class TrackingLifecycle(ProfileLifecycle):
            def on_activate(self, context) -> None:  # type: ignore[no-untyped-def]
                events.append(f"activate:{context.profile.name}")

            def on_deactivate(self, context) -> None:  # type: ignore[no-untyped-def]
                events.append(f"deactivate:{context.profile.name}")

            def on_button(self, context, index, pressed) -> bool:  # type: ignore[no-untyped-def]
                events.append(f"button:{index}:{pressed}")
                return True

            def on_encoder(self, context, index, direction) -> bool:  # type: ignore[no-untyped-def]
                events.append(f"encoder:{index}:{direction}")
                return True

            def on_tick(self, context, now) -> None:  # type: ignore[no-untyped-def]
                events.append(f"tick:{now}")

        deck = MockDeck()
        tracker = TrackingLifecycle()
        self.service.profile_lifecycles[0] = tracker
        self.service.foreground_provider = lambda: ForegroundWindow("", "", 0)

        self.service.activate_profile(deck, 0)
        self.service.handle_event(deck, ("key", 0, True))
        self.service.handle_event(deck, ("encoder", 0, 1))
        self.service.tick_profile(deck, 12.5)
        self.service.activate_profile(deck, 1)

        self.assertEqual(
            events,
            [
                "activate:Desktop",
                "button:0:True",
                "encoder:0:right",
                "tick:12.5",
                "deactivate:Desktop",
            ],
        )


class AnimationTests(unittest.TestCase):
    def test_sources_have_real_transparency(self) -> None:
        for path in CREATURES:
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_animation_is_preencoded(self) -> None:
        animation = IdleAnimation(frame_count=3)
        self.assertEqual(len(animation), 3)
        self.assertEqual(len(animation.get(0)), 3)
        self.assertTrue(all(frame.startswith(b"\xff\xd8") for frame in animation.get(0)))


if __name__ == "__main__":
    unittest.main()
