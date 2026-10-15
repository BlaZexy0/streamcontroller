"""Load and save user-editable profiles next to the active configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .profiles.model import Button, Profile, ProfileLifecycle
from .settings import SettingsError, validate_action


PROFILE_FILE_VERSION = 1


def profiles_path(config_path: Path) -> Path:
    return config_path.with_name("profiles.json")


def profile_to_dict(profile: Profile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "processes": list(profile.processes),
        "order": profile.order,
        "buttons": [
            {
                "label": button.label,
                "color": "#%02X%02X%02X" % button.color,
                "action": button.action,
            }
            for button in profile.buttons
        ],
    }


def profiles_document(profiles: tuple[Profile, ...] | list[Profile]) -> dict[str, Any]:
    return {"version": PROFILE_FILE_VERSION, "profiles": [profile_to_dict(p) for p in profiles]}


def _color(value: Any, location: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise SettingsError(f"{location}.color muss #RRGGBB sein")
    try:
        return tuple(bytes.fromhex(value[1:]))  # type: ignore[return-value]
    except ValueError as exc:
        raise SettingsError(f"{location}.color ist ungueltig") from exc


def profiles_from_document(
    document: Any,
    lifecycle_defaults: tuple[Profile, ...] = (),
) -> tuple[Profile, ...]:
    if not isinstance(document, dict) or document.get("version") != PROFILE_FILE_VERSION:
        raise SettingsError("profiles.json hat eine unbekannte Version")
    raw_profiles = document.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise SettingsError("profiles.json braucht mindestens ein Profil")

    profiles: list[Profile] = []
    lifecycle_by_name = {
        profile.name.casefold(): profile.lifecycle_factory for profile in lifecycle_defaults
    }
    names: set[str] = set()
    for profile_index, raw in enumerate(raw_profiles):
        location = f"profiles[{profile_index}]"
        if not isinstance(raw, dict):
            raise SettingsError(f"{location} muss ein Objekt sein")
        name = raw.get("name")
        if not isinstance(name, str) or not name.strip():
            raise SettingsError(f"{location}.name darf nicht leer sein")
        if name.casefold() in names:
            raise SettingsError(f"Doppelter Profilname: {name}")
        names.add(name.casefold())
        processes = raw.get("processes", [])
        if not isinstance(processes, list) or not all(
            isinstance(process, str) and process.strip() for process in processes
        ):
            raise SettingsError(f"{location}.processes muss eine Liste von Dateinamen sein")
        order = raw.get("order", 100)
        buttons_raw = raw.get("buttons")
        if not isinstance(buttons_raw, list) or len(buttons_raw) != 6:
            raise SettingsError(f"{location}.buttons braucht genau sechs Eintraege")
        buttons: list[Button] = []
        for button_index, button_raw in enumerate(buttons_raw):
            button_location = f"{location}.buttons[{button_index}]"
            if not isinstance(button_raw, dict):
                raise SettingsError(f"{button_location} muss ein Objekt sein")
            label = button_raw.get("label")
            if not isinstance(label, str) or not label.strip():
                raise SettingsError(f"{button_location}.label darf nicht leer sein")
            action_raw = button_raw.get("action")
            action = None if action_raw is None else validate_action(action_raw, button_location)
            buttons.append(Button(label.strip(), _color(button_raw.get("color"), button_location), action))
        profiles.append(
            Profile(
                name=name.strip(),
                processes=tuple(process.strip() for process in processes),
                order=order,
                buttons=tuple(buttons),
                lifecycle_factory=lifecycle_by_name.get(name.casefold(), ProfileLifecycle),
            )
        )

    if not any(not profile.processes for profile in profiles):
        raise SettingsError("Mindestens ein Fallback-Profil ohne Prozess ist erforderlich")
    return tuple(sorted(profiles, key=lambda profile: (profile.order, profile.name.casefold())))


def load_profiles(config_path: Path, defaults: tuple[Profile, ...]) -> tuple[Profile, ...]:
    path = profiles_path(config_path)
    if not path.exists():
        return defaults
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SettingsError(f"Ungueltiges JSON in profiles.json, Zeile {exc.lineno}: {exc.msg}") from exc
    return profiles_from_document(document, defaults)


def save_profiles(
    config_path: Path,
    document: Any,
    lifecycle_defaults: tuple[Profile, ...] = (),
) -> tuple[Profile, ...]:
    profiles = profiles_from_document(document, lifecycle_defaults)
    path = profiles_path(config_path)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(profiles_document(profiles), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)
    return profiles


def reset_profiles(config_path: Path) -> None:
    profiles_path(config_path).unlink(missing_ok=True)
