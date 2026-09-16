"""Spotify profile using the global Windows media controls."""

from .helpers import key
from .model import Button, Profile


PROFILE = Profile(
    name="Spotify",
    processes=("spotify.exe",),
    order=40,
    buttons=(
        Button("PREV", (25, 145, 75), key("media_prev")),
        Button("PLAY", (30, 185, 95), key("media_play_pause")),
        Button("NEXT", (25, 145, 75), key("media_next")),
        Button("VOL-", (45, 65, 75), key("volume_down")),
        Button("MUTE", (175, 50, 60), key("volume_mute")),
        Button("VOL+", (45, 65, 75), key("volume_up")),
    ),
)
