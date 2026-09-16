"""Shared data model for one program profile."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from PIL import Image

    from ..core.interfaces import DeckInterface


Action = dict[str, Any]
Color = tuple[int, int, int]


@dataclass(frozen=True)
class ProfileContext:
    """Narrow service API exposed to one active profile."""

    deck: "DeckInterface"
    profile: "Profile"
    run_action: Callable[[Action | None], None]
    request_render: Callable[[], None]
    set_key_image: Callable[[int, "Image.Image | bytes"], None]
    show_overlay: Callable[[dict[int, "Image.Image | bytes"], float], None]


class ProfileLifecycle:
    """Optional stateful hooks for profiles with dynamic behaviour."""

    def on_activate(self, context: ProfileContext) -> None:
        pass

    def on_deactivate(self, context: ProfileContext) -> None:
        pass

    def on_button(self, context: ProfileContext, index: int, pressed: bool) -> bool:
        return False

    def on_encoder(self, context: ProfileContext, index: int, direction: str) -> bool:
        return False

    def on_tick(self, context: ProfileContext, now: float) -> None:
        pass


@dataclass(frozen=True)
class Button:
    label: str
    color: Color
    action: Action | None = None


@dataclass(frozen=True)
class Profile:
    name: str
    processes: tuple[str, ...]
    buttons: tuple[Button, ...]
    order: int = 100
    lifecycle_factory: Callable[[], ProfileLifecycle] = field(
        default=ProfileLifecycle,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Ein Profilname darf nicht leer sein")
        if isinstance(self.order, bool) or not isinstance(self.order, int) or self.order < 0:
            raise ValueError(f"Profil {self.name!r} hat eine ungueltige Reihenfolge")
        if len(self.buttons) != 6:
            raise ValueError(f"Profil {self.name!r} braucht genau sechs LCD-Tasten")
        for button in self.buttons:
            if not button.label.strip():
                raise ValueError(f"Profil {self.name!r} enthaelt eine leere Beschriftung")
            if len(button.color) != 3 or any(not 0 <= channel <= 255 for channel in button.color):
                raise ValueError(
                    f"Profil {self.name!r}, Taste {button.label!r}: ungueltige RGB-Farbe"
                )

    def matches(self, process_name: str) -> bool:
        candidate = process_name.lower()
        return candidate in (process.lower() for process in self.processes)
