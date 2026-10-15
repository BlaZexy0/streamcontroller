"""Current-user Windows autostart management."""

from __future__ import annotations

import subprocess
import sys
import winreg
from dataclasses import dataclass
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SoomfonController"


class AutostartError(RuntimeError):
    pass


@dataclass(frozen=True)
class AutostartStatus:
    command: str | None
    executable: Path | None
    installed: bool
    target_exists: bool
    matches_current: bool


def build_command(executable: Path, delay_seconds: float = 10.0) -> str:
    return subprocess.list2cmdline(
        [str(executable.resolve()), "--startup-delay", f"{delay_seconds:g}"]
    )


def command_executable(command: str) -> Path | None:
    text = command.strip()
    if not text:
        return None
    if text.startswith('"'):
        end = text.find('"', 1)
        return Path(text[1:end]) if end > 1 else None
    return Path(text.split(maxsplit=1)[0])


def preferred_executable() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    candidate = Path(__file__).resolve().parent.parent / "dist" / "SoomfonController.exe"
    if candidate.is_file():
        return candidate.resolve()
    raise AutostartError("Onefile-EXE fehlt. Zuerst build_controller.ps1 onefile ausfuehren.")


class AutostartManager:
    def read_command(self) -> str | None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, VALUE_NAME)
                return str(value)
        except FileNotFoundError:
            return None

    def status(self, current_executable: Path | None = None) -> AutostartStatus:
        command = self.read_command()
        executable = command_executable(command) if command else None
        current = current_executable.resolve() if current_executable else None
        return AutostartStatus(
            command=command,
            executable=executable,
            installed=command is not None,
            target_exists=bool(executable and executable.is_file()),
            matches_current=bool(
                executable
                and current
                and str(executable.resolve()).casefold() == str(current).casefold()
            ),
        )

    def install(self, executable: Path, delay_seconds: float = 10.0) -> str:
        if not executable.is_file():
            raise AutostartError(f"EXE fehlt: {executable}")
        command = build_command(executable, delay_seconds)
        if len(command) > 260:
            raise AutostartError("Autostart-Befehlszeile ist laenger als 260 Zeichen")
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        return command

    def remove(self) -> bool:
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                RUN_KEY,
                0,
                winreg.KEY_SET_VALUE,
            ) as key:
                winreg.DeleteValue(key, VALUE_NAME)
            return True
        except FileNotFoundError:
            return False
