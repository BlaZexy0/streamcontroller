from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

from streamdeck_app.core.device import DeckConnectionError
from streamdeck_app.core.foreground import ForegroundWindow
from streamdeck_app.core.audio import AudioDeviceState, AudioState, AudioUnavailableError
from streamdeck_app.service import ControllerService
from streamdeck_app.settings import SettingsError, load_settings
from streamdeck_app.screens import DisplayController
from streamdeck_app.testing import MockDeck


ROOT = Path(__file__).resolve().parent.parent


class SettingsTests(unittest.TestCase):
    def test_project_configuration_is_valid(self) -> None:
        settings = load_settings(ROOT / "config.json")
        self.assertEqual(settings.brightness, 65)
        self.assertEqual(settings.hid_read_timeout_ms, 100)
        self.assertEqual(settings.screensaver_hold_key, 9)
        self.assertEqual(settings.screensaver_hold_seconds, 5)
        self.assertEqual(settings.audio_overlay_seconds, 1.5)
        self.assertEqual(settings.audio_device_hold_key, 11)
        self.assertEqual(settings.audio_device_hold_seconds, 2)
        self.assertEqual(settings.audio_output_devices, ())
        self.assertTrue(settings.market_enabled)
        self.assertEqual(settings.market_refresh_seconds, 15)
        self.assertEqual(settings.market_closed_refresh_seconds, 1800)
        self.assertEqual(settings.market_stale_seconds, 180)
        self.assertEqual(len(settings.market_watchlist), 3)
        self.assertEqual(len({item.symbol for item in settings.market_watchlist}), 3)
        self.assertIn(0, settings.encoders)

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"typo_field": True}), encoding="utf-8")
            with self.assertRaisesRegex(SettingsError, "Unbekannte Konfigurationsfelder"):
                load_settings(path)

    def test_invalid_action_is_rejected_with_location(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "hardware_buttons": {
                            "6": {"type": "key", "key": "does_not_exist"}
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SettingsError, "hardware_buttons.6.key"):
                load_settings(path)


class DisplayCacheTests(unittest.TestCase):
    def test_identical_image_is_only_transmitted_once(self) -> None:
        deck = MockDeck()
        image = Image.new("RGB", (60, 60), "navy")
        self.assertTrue(deck.set_key_image(0, image))
        self.assertFalse(deck.set_key_image(0, image))
        self.assertEqual(deck.image_write_count, 1)

    def test_identical_brightness_is_only_transmitted_once(self) -> None:
        deck = MockDeck()
        self.assertTrue(deck.set_brightness(65))
        self.assertFalse(deck.set_brightness(65))
        self.assertEqual(deck.command_count, 1)

    def test_overlay_expires_and_restores_previous_content(self) -> None:
        deck = MockDeck()
        display = DisplayController()
        display.set_base([Image.new("RGB", (60, 60), "navy") for _ in range(6)])
        display.render(deck)
        base_image = deck.images[2]

        display.show_overlay(
            {2: Image.new("RGB", (60, 60), "orange")},
            now=10.0,
            duration=2.0,
        )
        display.render(deck)
        self.assertNotEqual(deck.images[2], base_image)
        self.assertEqual(deck.image_write_count, 7)

        display.tick(deck, 11.99)
        self.assertEqual(deck.image_write_count, 7)
        display.tick(deck, 12.0)
        self.assertEqual(deck.images[2], base_image)
        self.assertEqual(deck.image_write_count, 8)


class ServiceStabilityTests(unittest.TestCase):
    def _service(self, process_name: str = "code.exe") -> ControllerService:
        window = ForegroundWindow(process_name, "Test", 42)
        return ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: window,
        )

    def test_foreground_change_is_debounced(self) -> None:
        service = self._service("code.exe")
        service.settings = replace(
            service.settings,
            foreground_poll_seconds=0.1,
            foreground_debounce_seconds=0.2,
        )
        service.profile_index = 0
        service.candidate_profile_index = 0
        service.last_window_poll = 0
        deck = MockDeck()

        service.poll_foreground(deck, 1.0)
        self.assertEqual(service.profile.name, "Desktop")
        service.poll_foreground(deck, 1.11)
        self.assertEqual(service.profile.name, "Desktop")
        service.poll_foreground(deck, 1.25)
        self.assertEqual(service.profile.name, "VS Code")

    def test_ignored_helper_window_does_not_switch_profile(self) -> None:
        service = self._service("searchhost.exe")
        service.profile_index = service.resolve_profile("code.exe")
        service.last_window_poll = 0
        service.poll_foreground(MockDeck(), 1.0)
        self.assertEqual(service.profile.name, "VS Code")

    def test_connection_is_retried(self) -> None:
        deck = MockDeck()

        class FlakyFactory:
            def __init__(self) -> None:
                self.calls = 0

            def __call__(self) -> MockDeck:
                self.calls += 1
                if self.calls < 3:
                    raise RuntimeError("simulierter USB-Ausfall")
                return deck

        factory = FlakyFactory()
        window = ForegroundWindow("code.exe", "Test", 42)
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=factory,
            foreground_provider=lambda: window,
        )
        service.settings = replace(
            service.settings,
            reconnect_seconds=0.01,
            hid_read_timeout_ms=20,
        )
        service.run(run_seconds=0.09)

        self.assertGreaterEqual(factory.calls, 3)
        self.assertEqual(deck.image_write_count, 6)

    def test_disconnect_during_read_reconnects(self) -> None:
        class DisconnectingDeck(MockDeck):
            def read(self, timeout_ms: int = 100) -> bytes:
                raise DeckConnectionError("simulierter Kabelverlust")

        healthy_deck = MockDeck()

        class ReconnectFactory:
            def __init__(self) -> None:
                self.calls = 0

            def __call__(self) -> MockDeck:
                self.calls += 1
                return DisconnectingDeck() if self.calls == 1 else healthy_deck

        factory = ReconnectFactory()
        window = ForegroundWindow("code.exe", "Test", 42)
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=factory,
            foreground_provider=lambda: window,
        )
        service.settings = replace(
            service.settings,
            reconnect_seconds=0.01,
            hid_read_timeout_ms=20,
        )
        service.run(run_seconds=0.08)

        self.assertGreaterEqual(factory.calls, 2)
        self.assertEqual(healthy_deck.image_write_count, 6)

    def test_old_vendor_layout_is_cleared_before_rendering(self) -> None:
        deck = MockDeck()
        window = ForegroundWindow("code.exe", "Test", 42)
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=lambda: deck,
            foreground_provider=lambda: window,
        )
        service.settings = replace(service.settings, hid_read_timeout_ms=20)
        service.run(run_seconds=0.03)

        self.assertEqual(deck.operations[0], "clear")
        self.assertEqual(deck.operations[1], "brightness:65")
        self.assertEqual(deck.operations[2:8], [f"image:{key}" for key in range(6)])


class ScreensaverEncoderHoldTests(unittest.TestCase):
    def _service(self) -> ControllerService:
        return ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
        )

    def test_direct_toggle_still_toggles_screensaver(self) -> None:
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
        )
        deck = MockDeck()

        service.toggle_screensaver(deck, now=1.0)
        self.assertTrue(service.idle)
        self.assertEqual(deck.operations[0], "clear")

        service.toggle_screensaver(deck, now=2.0)
        self.assertFalse(service.idle)
        self.assertEqual(deck.image_write_count, 12)

    def test_five_second_large_encoder_hold_starts_and_stops_screensaver(self) -> None:
        service = self._service()
        deck = MockDeck()

        service.handle_event(deck, ("key", 9, True))
        assert service.screensaver_hold_started_at is not None
        pressed_at = service.screensaver_hold_started_at
        service.check_screensaver_hold(deck, pressed_at + 4.99)
        self.assertFalse(service.idle)
        service.check_screensaver_hold(deck, pressed_at + 5)
        self.assertTrue(service.idle)
        service.handle_event(deck, ("key", 9, False))

        service.handle_event(deck, ("key", 9, True))
        assert service.screensaver_hold_started_at is not None
        service.check_screensaver_hold(
            deck,
            service.screensaver_hold_started_at + 5,
        )
        self.assertFalse(service.idle)
        service.handle_event(deck, ("key", 9, False))

    def test_short_press_keeps_encoder_action_on_release(self) -> None:
        service = self._service()
        service.settings = replace(service.settings, screensaver_hold_key=8)
        deck = MockDeck()

        service.handle_event(deck, ("key", 8, True))
        self.assertFalse(service.locked)
        service.handle_event(deck, ("key", 8, False))
        self.assertTrue(service.locked)

    def test_short_press_only_wakes_screensaver(self) -> None:
        service = self._service()
        service.settings = replace(service.settings, screensaver_hold_key=8)
        deck = MockDeck()
        service.start_screensaver(deck, now=1.0)

        service.handle_event(deck, ("key", 8, True))
        self.assertTrue(service.idle)
        service.handle_event(deck, ("key", 8, False))

        self.assertFalse(service.idle)
        self.assertFalse(service.locked)

    def test_invalid_hold_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(
                json.dumps({"screensaver_hold_key": 12}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(SettingsError, "screensaver_hold_key"):
                load_settings(path)


class AudioCockpitTests(unittest.TestCase):
    class FakeAudioController:
        def __init__(self) -> None:
            self.percent = 50
            self.muted = False
            self.application_calls: list[tuple[int, str]] = []
            self.microphone_percent = 60
            self.microphone_muted = False
            self.device_switches = 0

        def change_system_volume(self, delta_percent: int) -> AudioState:
            self.percent = max(0, min(100, self.percent + delta_percent))
            if delta_percent > 0:
                self.muted = False
            return AudioState(self.percent, self.muted)

        def toggle_system_mute(self) -> AudioState:
            self.muted = not self.muted
            return AudioState(self.percent, self.muted)

        def change_application_volume(
            self, process_id: int, process_name: str, delta_percent: int
        ) -> AudioState:
            self.application_calls.append((process_id, process_name))
            self.percent = max(0, min(100, self.percent + delta_percent))
            return AudioState(self.percent, self.muted, "CODE")

        def toggle_application_mute(
            self, process_id: int, process_name: str
        ) -> AudioState:
            self.application_calls.append((process_id, process_name))
            self.muted = not self.muted
            return AudioState(self.percent, self.muted, "CODE")

        def change_microphone_volume(self, delta_percent: int) -> AudioState:
            self.microphone_percent = max(
                0, min(100, self.microphone_percent + delta_percent)
            )
            return AudioState(self.microphone_percent, self.microphone_muted, "MIC")

        def toggle_microphone_mute(self) -> AudioState:
            self.microphone_muted = not self.microphone_muted
            return AudioState(self.microphone_percent, self.microphone_muted, "MIC")

        def cycle_output_device(
            self, preferred_names: tuple[str, ...]
        ) -> AudioDeviceState:
            self.device_switches += 1
            return AudioDeviceState("Test Headset")

    def test_large_encoder_changes_volume_and_shows_overlay(self) -> None:
        audio = self.FakeAudioController()
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=audio,
        )
        deck = MockDeck()
        service.render_profile(deck)

        service.handle_event(deck, ("encoder", 0, 1))

        self.assertEqual(audio.percent, 52)
        self.assertEqual(set(service.display.overlays[-1].images), {0, 1, 2})
        self.assertEqual(deck.image_write_count, 9)

    def test_short_large_encoder_press_toggles_mute(self) -> None:
        audio = self.FakeAudioController()
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=audio,
        )
        deck = MockDeck()

        service.handle_event(deck, ("key", 9, True))
        self.assertFalse(audio.muted)
        service.handle_event(deck, ("key", 9, False))

        self.assertTrue(audio.muted)
        self.assertEqual(set(service.display.overlays[-1].images), {0, 1, 2})

    def test_second_encoder_controls_foreground_application(self) -> None:
        audio = self.FakeAudioController()
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=audio,
        )
        deck = MockDeck()

        service.handle_event(deck, ("encoder", 1, -1))
        self.assertEqual(audio.percent, 48)
        self.assertEqual(audio.application_calls[-1], (42, "code.exe"))

        service.handle_event(deck, ("key", 10, True))
        self.assertTrue(audio.muted)
        self.assertEqual(audio.application_calls[-1], (42, "code.exe"))

    def test_third_encoder_controls_microphone(self) -> None:
        audio = self.FakeAudioController()
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=audio,
        )
        deck = MockDeck()

        service.handle_event(deck, ("encoder", 2, 1))
        self.assertEqual(audio.microphone_percent, 62)

        service.handle_event(deck, ("key", 11, True))
        self.assertFalse(audio.microphone_muted)
        service.handle_event(deck, ("key", 11, False))
        self.assertTrue(audio.microphone_muted)

    def test_long_third_encoder_press_switches_output_without_mic_mute(self) -> None:
        audio = self.FakeAudioController()
        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=audio,
        )
        deck = MockDeck()

        service.handle_event(deck, ("key", 11, True))
        assert service.audio_device_hold_started_at is not None
        service.check_audio_device_hold(
            deck,
            service.audio_device_hold_started_at + 2,
        )
        service.handle_event(deck, ("key", 11, False))

        self.assertEqual(audio.device_switches, 1)
        self.assertFalse(audio.microphone_muted)
        self.assertEqual(set(service.display.overlays[-1].images), {0, 1, 2})

    def test_missing_application_session_shows_error_overlay(self) -> None:
        class MissingSessionAudio(self.FakeAudioController):
            def change_application_volume(
                self, process_id: int, process_name: str, delta_percent: int
            ) -> AudioState:
                raise AudioUnavailableError("Keine aktive Audiositzung fuer code.exe")

        service = ControllerService(
            ROOT / "config.json",
            deck_factory=MockDeck,
            foreground_provider=lambda: ForegroundWindow("code.exe", "Test", 42),
            audio_controller=MissingSessionAudio(),
        )
        deck = MockDeck()

        service.handle_event(deck, ("encoder", 1, 1))

        self.assertEqual(set(service.display.overlays[-1].images), {0, 1, 2})


if __name__ == "__main__":
    unittest.main()
