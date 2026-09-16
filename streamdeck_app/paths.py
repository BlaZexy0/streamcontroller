"""Stable resource and writable paths for source and PyInstaller builds."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


APP_DIR_NAME = "SoomfonController"
RESOURCE_ROOT = Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    return RESOURCE_ROOT.joinpath(*parts)


def user_data_dir(*, create: bool = True) -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
    target = base / APP_DIR_NAME
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def default_config_path() -> Path:
    target = user_data_dir() / "config.json"
    if not target.exists():
        shutil.copyfile(resource_path("config.json"), target)
    return target


def default_log_path() -> Path:
    return user_data_dir() / "controller.log"
