"""Profile shared by common web browsers."""

from .helpers import hotkey, key
from .model import Button, Profile


PROFILE = Profile(
    name="Browser",
    processes=("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"),
    order=10,
    buttons=(
        Button("BACK", (40, 90, 180), hotkey("alt", "left")),
        Button("NEXT", (40, 90, 180), hotkey("alt", "right")),
        Button("RELOAD", (30, 145, 110), hotkey("ctrl", "r")),
        Button("NEW", (115, 70, 190), hotkey("ctrl", "t")),
        Button("CLOSE", (185, 55, 65), hotkey("ctrl", "w")),
        Button("FULL", (55, 65, 85), key("f11")),
    ),
)
