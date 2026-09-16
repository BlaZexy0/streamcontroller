"""Automatic discovery and validation of application profile modules."""

from __future__ import annotations

import importlib
import pkgutil

from .model import Button, Profile, ProfileContext, ProfileLifecycle


_UTILITY_MODULES = {"helpers", "model", "reload", "runtime"}


def profile_module_names() -> tuple[str, ...]:
    return tuple(
        module_info.name
        for module_info in pkgutil.iter_modules(__path__)
        if not module_info.ispkg
        and not module_info.name.startswith("_")
        and module_info.name not in _UTILITY_MODULES
    )


def discover_profiles() -> tuple[Profile, ...]:
    discovered: list[Profile] = []
    for module_name in profile_module_names():
        module = importlib.import_module(f"{__name__}.{module_name}")
        profile = getattr(module, "PROFILE", None)
        if profile is None:
            continue
        if not isinstance(profile, Profile):
            raise TypeError(f"{module_name}.PROFILE muss ein Profile-Objekt sein")
        discovered.append(profile)

    if not discovered:
        raise RuntimeError("Keine Profile in streamdeck_app.profiles gefunden")

    names = [profile.name.casefold() for profile in discovered]
    if len(names) != len(set(names)):
        raise ValueError("Profilnamen muessen eindeutig sein")

    fallbacks = [profile for profile in discovered if not profile.processes]
    if len(fallbacks) != 1:
        raise ValueError("Genau ein Profil ohne Prozessnamen muss als Fallback existieren")

    claimed_processes: dict[str, str] = {}
    for profile in discovered:
        for process in profile.processes:
            normalized = process.casefold()
            owner = claimed_processes.get(normalized)
            if owner is not None:
                raise ValueError(
                    f"Prozess {process!r} wird von {owner!r} und {profile.name!r} verwendet"
                )
            claimed_processes[normalized] = profile.name

    return tuple(sorted(discovered, key=lambda profile: (profile.order, profile.name.casefold())))


ALL_PROFILES = discover_profiles()

__all__ = ["ALL_PROFILES", "Button", "Profile", "ProfileContext", "ProfileLifecycle"]
