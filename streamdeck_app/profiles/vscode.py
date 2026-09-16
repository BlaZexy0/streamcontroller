"""Visual Studio Code and VSCodium profile."""

from .helpers import hotkey
from .model import Button, Profile


PROFILE = Profile(
    name="VS Code",
    processes=("code.exe", "codium.exe"),
    order=20,
    buttons=(
        Button("CMD", (35, 125, 185), hotkey("ctrl", "shift", "p")),
        Button("FILE", (35, 125, 185), hotkey("ctrl", "p")),
        Button("FIND", (155, 105, 30), hotkey("ctrl", "shift", "f")),
        Button("TERM", (45, 55, 70), hotkey("ctrl", "grave")),
        Button("GIT", (205, 85, 45), hotkey("ctrl", "shift", "g")),
        Button("SAVE", (45, 145, 90), hotkey("ctrl", "s")),
    ),
)
