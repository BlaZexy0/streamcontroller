"""Fallback profile for programs without a dedicated module."""

from .helpers import key, launch, open_target
from .model import Button, Profile


PROFILE = Profile(
    name="Desktop",
    processes=(),
    order=0,
    buttons=(
        Button("WEB", (28, 98, 190), open_target("https://www.google.de")),
        Button("FILES", (205, 145, 20), launch("explorer.exe")),
        Button("TERM", (40, 45, 55), launch("wt.exe")),
        Button("TASK", (35, 130, 125), launch("taskmgr.exe")),
        Button("SET", (80, 85, 100), open_target("ms-settings:")),
        Button("PLAY", (30, 175, 90), key("media_play_pause")),
    ),
)
