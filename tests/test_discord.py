from __future__ import annotations

import unittest

from streamdeck_app.profiles.discord import DiscordLifecycle, PROFILE
from streamdeck_app.profiles.model import ProfileContext
from streamdeck_app.screens.discord import discord_confirmation
from streamdeck_app.testing import MockDeck


class DiscordProfileTests(unittest.TestCase):
    def test_common_discord_variants_are_detected(self) -> None:
        for process in ("Discord.exe", "DiscordCanary.exe", "DiscordPTB.exe", "Vesktop.exe"):
            self.assertTrue(PROFILE.matches(process))

    def test_voice_and_volume_actions_are_assigned(self) -> None:
        self.assertEqual(PROFILE.buttons[0].action, {"type": "hotkey", "keys": ["ctrl", "shift", "m"]})
        self.assertEqual(PROFILE.buttons[1].action, {"type": "hotkey", "keys": ["ctrl", "shift", "d"]})
        self.assertEqual(
            tuple(button.action["name"] for button in PROFILE.buttons[3:]),
            ("application_volume_down", "application_volume_mute", "application_volume_up"),
        )

    def test_mute_button_runs_action_and_shows_confirmation(self) -> None:
        actions: list[dict[str, object] | None] = []
        overlays: list[tuple[dict[int, object], float]] = []
        context = ProfileContext(
            deck=MockDeck(),
            profile=PROFILE,
            run_action=actions.append,
            request_render=lambda: None,
            set_key_image=lambda _key, _image: None,
            show_overlay=lambda images, duration: overlays.append((images, duration)),
        )

        handled = DiscordLifecycle().on_button(context, 0, True)

        self.assertTrue(handled)
        self.assertEqual(actions, [PROFILE.buttons[0].action])
        self.assertEqual(set(overlays[0][0]), {0, 1, 2})
        self.assertEqual(overlays[0][1], 0.9)

    def test_confirmation_tiles_are_complete(self) -> None:
        images = discord_confirmation("deafen")
        self.assertEqual(set(images), {0, 1, 2})
        self.assertTrue(all(image.size == (60, 60) for image in images.values()))


if __name__ == "__main__":
    unittest.main()
