"""Low-frequency source profile reloading for development sessions."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from pathlib import Path

from . import discover_profiles, profile_module_names
from .model import Profile


PROFILE_DIR = Path(__file__).resolve().parent
_IGNORED_FILES = {"__init__.py", "helpers.py", "model.py", "reload.py", "runtime.py"}


def reload_discovered_profiles() -> tuple[Profile, ...]:
    importlib.invalidate_caches()
    package = __package__ or "streamdeck_app.profiles"
    for module_name in profile_module_names():
        qualified_name = f"{package}.{module_name}"
        module = sys.modules.get(qualified_name)
        if module is None:
            importlib.import_module(qualified_name)
        else:
            importlib.reload(module)
    return discover_profiles()


class ProfileReloader:
    def __init__(
        self,
        profile_dir: Path = PROFILE_DIR,
        loader: Callable[[], tuple[Profile, ...]] = reload_discovered_profiles,
        interval_seconds: float = 1.0,
    ) -> None:
        self.profile_dir = profile_dir
        self.loader = loader
        self.interval_seconds = interval_seconds
        self.next_check = 0.0
        self.snapshot = self._snapshot()

    def poll(self, now: float) -> tuple[Profile, ...] | None:
        if now < self.next_check:
            return None
        self.next_check = now + self.interval_seconds
        current = self._snapshot()
        if current == self.snapshot:
            return None
        self.snapshot = current
        return self.loader()

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        return {
            path.name: (path.stat().st_mtime_ns, path.stat().st_size)
            for path in self.profile_dir.glob("*.py")
            if path.name not in _IGNORED_FILES and not path.name.startswith("_")
        }
