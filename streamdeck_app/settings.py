"""Validated global settings loaded from config.json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core.actions import VK
from .market.model import WatchItem
from .profiles.model import Action


class SettingsError(ValueError):
    """Raised when the user configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    idle_seconds: float
    animation_fps: float
    brightness: int
    reconnect_seconds: float
    foreground_poll_seconds: float
    foreground_debounce_seconds: float
    hid_read_timeout_ms: int
    screensaver_hold_key: int
    screensaver_hold_seconds: float
    audio_overlay_seconds: float
    audio_device_hold_key: int
    audio_device_hold_seconds: float
    audio_output_devices: tuple[str, ...]
    market_enabled: bool
    market_refresh_seconds: float
    market_closed_refresh_seconds: float
    market_stale_seconds: float
    market_watchlist: tuple[WatchItem, ...]
    ignored_processes: frozenset[str]
    hardware_buttons: dict[int, Action]
    encoders: dict[int, dict[str, Action]]


_TOP_LEVEL_KEYS = {
    "idle_seconds",
    "animation_fps",
    "brightness",
    "reconnect_seconds",
    "foreground_poll_seconds",
    "foreground_debounce_seconds",
    "hid_read_timeout_ms",
    "screensaver_hold_key",
    "screensaver_hold_seconds",
    "audio_overlay_seconds",
    "audio_device_hold_key",
    "audio_device_hold_seconds",
    "audio_output_devices",
    "market_enabled",
    "market_refresh_seconds",
    "market_closed_refresh_seconds",
    "market_stale_seconds",
    "market_watchlist",
    "ignored_processes",
    "hardware_buttons",
    "encoders",
}
_INTERNAL_ACTIONS = {
    "previous_profile",
    "next_profile",
    "toggle_lock",
    "system_volume_down",
    "system_volume_up",
    "system_volume_mute",
    "application_volume_down",
    "application_volume_up",
    "application_volume_mute",
    "microphone_volume_down",
    "microphone_volume_up",
    "microphone_volume_mute",
}


def _number(data: dict[str, Any], name: str, default: float) -> float:
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SettingsError(f"{name} muss eine Zahl sein")
    return float(value)


def validate_action(action: Any, location: str) -> Action:
    if not isinstance(action, dict):
        raise SettingsError(f"{location} muss ein Aktionsobjekt sein")
    kind = action.get("type")
    if kind == "key":
        key_name = action.get("key")
        if not isinstance(key_name, str) or key_name.lower() not in VK:
            raise SettingsError(f"{location}.key ist unbekannt: {key_name!r}")
    elif kind == "hotkey":
        keys = action.get("keys")
        if not isinstance(keys, list) or not keys:
            raise SettingsError(f"{location}.keys muss eine nichtleere Liste sein")
        unknown = [key for key in keys if not isinstance(key, str) or key.lower() not in VK]
        if unknown:
            raise SettingsError(f"{location}.keys enthaelt unbekannte Tasten: {unknown!r}")
    elif kind == "open":
        if not isinstance(action.get("target"), str) or not action["target"].strip():
            raise SettingsError(f"{location}.target darf nicht leer sein")
    elif kind == "launch":
        command = action.get("command")
        if not (
            isinstance(command, str)
            and command.strip()
            or isinstance(command, list)
            and command
            and all(isinstance(part, str) and part for part in command)
        ):
            raise SettingsError(f"{location}.command ist ungueltig")
    elif kind == "internal":
        if action.get("name") not in _INTERNAL_ACTIONS:
            raise SettingsError(f"{location}.name ist unbekannt: {action.get('name')!r}")
    else:
        raise SettingsError(f"{location}.type ist unbekannt: {kind!r}")
    return dict(action)


def load_settings(path: Path) -> Settings:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SettingsError(f"Konfigurationsdatei fehlt: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Ungueltiges JSON in {path.name}, Zeile {exc.lineno}: {exc.msg}") from exc

    if not isinstance(raw, dict):
        raise SettingsError("Die Konfiguration muss ein JSON-Objekt sein")
    unknown = set(raw) - _TOP_LEVEL_KEYS
    if unknown:
        raise SettingsError(f"Unbekannte Konfigurationsfelder: {', '.join(sorted(unknown))}")

    idle_seconds = _number(raw, "idle_seconds", 300)
    animation_fps = _number(raw, "animation_fps", 3)
    brightness = _number(raw, "brightness", 65)
    reconnect_seconds = _number(raw, "reconnect_seconds", 2)
    poll_seconds = _number(raw, "foreground_poll_seconds", 0.5)
    debounce_seconds = _number(raw, "foreground_debounce_seconds", 0.35)
    read_timeout = _number(raw, "hid_read_timeout_ms", 100)
    hold_key = raw.get("screensaver_hold_key", 9)
    hold_seconds = _number(raw, "screensaver_hold_seconds", 5)
    audio_overlay_seconds = _number(raw, "audio_overlay_seconds", 1.5)
    audio_device_hold_key = raw.get("audio_device_hold_key", 11)
    audio_device_hold_seconds = _number(raw, "audio_device_hold_seconds", 2)
    if isinstance(hold_key, bool) or not isinstance(hold_key, int) or hold_key not in range(6, 12):
        raise SettingsError("screensaver_hold_key muss ein Tastenindex zwischen 6 und 11 sein")

    if idle_seconds <= 0:
        raise SettingsError("idle_seconds muss groesser als 0 sein")
    if not 0.5 <= animation_fps <= 6:
        raise SettingsError("animation_fps muss zwischen 0.5 und 6 liegen")
    if not 0 <= brightness <= 100 or not brightness.is_integer():
        raise SettingsError("brightness muss eine ganze Zahl zwischen 0 und 100 sein")
    if reconnect_seconds <= 0:
        raise SettingsError("reconnect_seconds muss groesser als 0 sein")
    if poll_seconds < 0.1:
        raise SettingsError("foreground_poll_seconds muss mindestens 0.1 sein")
    if debounce_seconds < 0:
        raise SettingsError("foreground_debounce_seconds darf nicht negativ sein")
    if not 20 <= read_timeout <= 1000 or not read_timeout.is_integer():
        raise SettingsError("hid_read_timeout_ms muss ganzzahlig zwischen 20 und 1000 sein")
    if not 1 <= hold_seconds <= 10:
        raise SettingsError("screensaver_hold_seconds muss zwischen 1 und 10 liegen")
    if not 0.5 <= audio_overlay_seconds <= 5:
        raise SettingsError("audio_overlay_seconds muss zwischen 0.5 und 5 liegen")
    if (
        isinstance(audio_device_hold_key, bool)
        or not isinstance(audio_device_hold_key, int)
        or audio_device_hold_key not in range(6, 12)
    ):
        raise SettingsError("audio_device_hold_key muss ein Tastenindex zwischen 6 und 11 sein")
    if audio_device_hold_key == hold_key:
        raise SettingsError("Die beiden Langdruck-Funktionen brauchen unterschiedliche Tasten")
    if not 1 <= audio_device_hold_seconds <= 5:
        raise SettingsError("audio_device_hold_seconds muss zwischen 1 und 5 liegen")

    output_devices_raw = raw.get("audio_output_devices", [])
    if not isinstance(output_devices_raw, list) or not all(
        isinstance(name, str) and name.strip() for name in output_devices_raw
    ):
        raise SettingsError("audio_output_devices muss eine Liste nichtleerer Namen sein")

    market_enabled = raw.get("market_enabled", True)
    if not isinstance(market_enabled, bool):
        raise SettingsError("market_enabled muss true oder false sein")
    market_refresh_seconds = _number(raw, "market_refresh_seconds", 60)
    market_closed_refresh_seconds = _number(raw, "market_closed_refresh_seconds", 1800)
    market_stale_seconds = _number(raw, "market_stale_seconds", 180)
    if not 15 <= market_refresh_seconds <= 3600:
        raise SettingsError("market_refresh_seconds muss zwischen 15 und 3600 liegen")
    if not market_refresh_seconds <= market_stale_seconds <= 86400:
        raise SettingsError(
            "market_stale_seconds muss mindestens dem Abrufintervall entsprechen "
            "und darf hoechstens 86400 sein"
        )
    if not market_refresh_seconds <= market_closed_refresh_seconds <= 86400:
        raise SettingsError(
            "market_closed_refresh_seconds muss mindestens dem normalen "
            "Abrufintervall entsprechen und darf hoechstens 86400 sein"
        )
    watchlist_raw = raw.get(
        "market_watchlist",
        [
            {"symbol": "AAPL", "label": "APPLE"},
            {"symbol": "MSFT", "label": "MSFT"},
            {"symbol": "NVDA", "label": "NVIDIA"},
        ],
    )
    if not isinstance(watchlist_raw, list) or len(watchlist_raw) != 3:
        raise SettingsError("market_watchlist muss genau drei Eintraege enthalten")
    market_watchlist: list[WatchItem] = []
    for index, entry in enumerate(watchlist_raw):
        if not isinstance(entry, dict) or set(entry) != {"symbol", "label"}:
            raise SettingsError(
                f"market_watchlist.{index} braucht genau symbol und label"
            )
        symbol = entry["symbol"]
        label = entry["label"]
        if not isinstance(symbol, str) or not symbol.strip() or len(symbol.strip()) > 20:
            raise SettingsError(f"market_watchlist.{index}.symbol ist ungueltig")
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 8:
            raise SettingsError(f"market_watchlist.{index}.label ist ungueltig")
        market_watchlist.append(WatchItem(symbol.strip().upper(), label.strip()))
    symbols = [item.symbol for item in market_watchlist]
    if len(set(symbols)) != len(symbols):
        raise SettingsError("market_watchlist darf keine doppelten Symbole enthalten")

    ignored_raw = raw.get("ignored_processes", [])
    if not isinstance(ignored_raw, list) or not all(isinstance(item, str) for item in ignored_raw):
        raise SettingsError("ignored_processes muss eine Liste von Dateinamen sein")

    buttons_raw = raw.get("hardware_buttons", {})
    if not isinstance(buttons_raw, dict):
        raise SettingsError("hardware_buttons muss ein Objekt sein")
    hardware_buttons: dict[int, Action] = {}
    for key, action in buttons_raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"Ungueltiger Hardware-Tastenindex: {key!r}") from exc
        if index not in range(6, 12):
            raise SettingsError(f"Hardware-Tastenindex ausserhalb 6..11: {index}")
        hardware_buttons[index] = validate_action(action, f"hardware_buttons.{key}")

    encoders_raw = raw.get("encoders", {})
    if not isinstance(encoders_raw, dict):
        raise SettingsError("encoders muss ein Objekt sein")
    encoders: dict[int, dict[str, Action]] = {}
    for key, directions in encoders_raw.items():
        try:
            index = int(key)
        except (TypeError, ValueError) as exc:
            raise SettingsError(f"Ungueltiger Encoderindex: {key!r}") from exc
        if index not in range(3) or not isinstance(directions, dict):
            raise SettingsError(f"Encoder {key!r} ist ungueltig")
        unknown_directions = set(directions) - {"left", "right"}
        if unknown_directions:
            raise SettingsError(f"Encoder {index} hat unbekannte Richtungen: {unknown_directions}")
        encoders[index] = {
            direction: validate_action(action, f"encoders.{key}.{direction}")
            for direction, action in directions.items()
        }

    return Settings(
        idle_seconds=idle_seconds,
        animation_fps=animation_fps,
        brightness=int(brightness),
        reconnect_seconds=reconnect_seconds,
        foreground_poll_seconds=poll_seconds,
        foreground_debounce_seconds=debounce_seconds,
        hid_read_timeout_ms=int(read_timeout),
        screensaver_hold_key=hold_key,
        screensaver_hold_seconds=hold_seconds,
        audio_overlay_seconds=audio_overlay_seconds,
        audio_device_hold_key=audio_device_hold_key,
        audio_device_hold_seconds=audio_device_hold_seconds,
        audio_output_devices=tuple(output_devices_raw),
        market_enabled=market_enabled,
        market_refresh_seconds=market_refresh_seconds,
        market_closed_refresh_seconds=market_closed_refresh_seconds,
        market_stale_seconds=market_stale_seconds,
        market_watchlist=tuple(market_watchlist),
        ignored_processes=frozenset(item.lower() for item in ignored_raw),
        hardware_buttons=hardware_buttons,
        encoders=encoders,
    )
