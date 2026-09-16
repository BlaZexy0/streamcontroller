"""Safe local actions used by program profiles."""

from __future__ import annotations

import ctypes
import os
import subprocess
from typing import Any, Callable


KEYEVENTF_KEYUP = 0x0002
VK = {
    "backspace": 0x08,
    "tab": 0x09,
    "enter": 0x0D,
    "shift": 0x10,
    "ctrl": 0x11,
    "alt": 0x12,
    "escape": 0x1B,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "f5": 0x74,
    "f11": 0x7A,
    "grave": 0xC0,
    "volume_mute": 0xAD,
    "volume_down": 0xAE,
    "volume_up": 0xAF,
    "media_next": 0xB0,
    "media_prev": 0xB1,
    "media_stop": 0xB2,
    "media_play_pause": 0xB3,
}
for character in "abcdefghijklmnopqrstuvwxyz0123456789":
    VK[character] = ord(character.upper())
for number in range(1, 25):
    VK[f"f{number}"] = 0x6F + number


def press_key(name: str) -> None:
    key = VK[name.lower()]
    ctypes.windll.user32.keybd_event(key, 0, 0, 0)
    ctypes.windll.user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)


def hotkey(keys: list[str]) -> None:
    codes = [VK[key.lower()] for key in keys]
    for code in codes:
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
    for code in reversed(codes):
        ctypes.windll.user32.keybd_event(code, 0, KEYEVENTF_KEYUP, 0)


def execute(action: dict[str, Any] | None, internal: Callable[[str], None]) -> None:
    if not action:
        return
    kind = action.get("type")
    if kind == "key":
        press_key(str(action["key"]))
    elif kind == "hotkey":
        hotkey([str(key) for key in action["keys"]])
    elif kind == "open":
        os.startfile(os.path.expandvars(str(action["target"])))
    elif kind == "launch":
        command = action["command"]
        args = [command] if isinstance(command, str) else list(command)
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    elif kind == "internal":
        internal(str(action["name"]))
    else:
        raise ValueError(f"Unbekannter Aktionstyp: {kind!r}")
