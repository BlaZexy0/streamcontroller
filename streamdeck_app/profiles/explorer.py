"""Windows File Explorer profile."""

from .helpers import hotkey, key
from .model import Button, Profile


PROFILE = Profile(
    name="Explorer",
    processes=("explorer.exe",),
    order=30,
    buttons=(
        Button("BACK", (190, 135, 25), hotkey("alt", "left")),
        Button("NEXT", (190, 135, 25), hotkey("alt", "right")),
        Button("UP", (45, 125, 185), hotkey("alt", "up")),
        Button("FRESH", (35, 145, 105), key("f5")),
        Button("NEW", (100, 75, 180), hotkey("ctrl", "n")),
        Button("CLOSE", (180, 55, 60), hotkey("ctrl", "w")),
    ),
)
