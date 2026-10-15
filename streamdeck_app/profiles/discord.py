"""Discord voice controls and application-volume buttons."""

from ..screens.discord import discord_confirmation
from .helpers import hotkey, internal
from .model import Button, Profile, ProfileContext, ProfileLifecycle


class DiscordLifecycle(ProfileLifecycle):
    def on_button(self, context: ProfileContext, index: int, pressed: bool) -> bool:
        if not pressed or index not in (0, 1):
            return False
        context.run_action(context.profile.buttons[index].action)
        action = "microphone" if index == 0 else "deafen"
        context.show_overlay(discord_confirmation(action), 0.9)
        return True


PROFILE = Profile(
    name="Discord",
    processes=("discord.exe", "discordcanary.exe", "discordptb.exe", "vesktop.exe"),
    order=35,
    lifecycle_factory=DiscordLifecycle,
    buttons=(
        Button("MIC", (75, 85, 145), hotkey("ctrl", "shift", "m")),
        Button("DEAF", (145, 65, 90), hotkey("ctrl", "shift", "d")),
        Button("VOICE", (70, 85, 145), hotkey("ctrl", "alt", "a")),
        Button("VOL-", (55, 65, 105), internal("application_volume_down")),
        Button("MUTE", (150, 55, 75), internal("application_volume_mute")),
        Button("VOL+", (55, 65, 105), internal("application_volume_up")),
    ),
)
