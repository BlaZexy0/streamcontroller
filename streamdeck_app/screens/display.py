"""Composites persistent LCD content with temporary per-key overlays."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from PIL import Image

from ..core.interfaces import DeckInterface


DisplayContent: TypeAlias = Image.Image | bytes


@dataclass(frozen=True)
class Overlay:
    images: dict[int, DisplayContent]
    expires_at: float


class DisplayController:
    def __init__(self, key_count: int = 6) -> None:
        self.key_count = key_count
        self.base: list[DisplayContent | None] = [None] * key_count
        self.overlays: list[Overlay] = []

    def set_base(self, images: list[DisplayContent]) -> None:
        if len(images) != self.key_count:
            raise ValueError(f"Basisanzeige braucht genau {self.key_count} Bilder")
        self.base = list(images)

    def set_base_key(self, key: int, image: DisplayContent) -> None:
        self._validate_key(key)
        self.base[key] = image

    def show_overlay(
        self,
        images: dict[int, DisplayContent],
        *,
        now: float,
        duration: float,
    ) -> None:
        if duration <= 0:
            raise ValueError("Overlay-Dauer muss groesser als 0 sein")
        if not images:
            raise ValueError("Ein Overlay braucht mindestens ein Bild")
        for key in images:
            self._validate_key(key)
        self.overlays = [
            overlay for overlay in self.overlays if overlay.expires_at > now
        ]
        self.overlays.append(Overlay(dict(images), now + duration))

    def clear_overlays(self) -> None:
        self.overlays.clear()

    def tick(self, deck: DeckInterface, now: float, *, render_enabled: bool = True) -> None:
        active = [overlay for overlay in self.overlays if overlay.expires_at > now]
        changed = len(active) != len(self.overlays)
        self.overlays = active
        if changed and render_enabled:
            self.render(deck)

    def render(self, deck: DeckInterface) -> None:
        for key, base_image in enumerate(self.base):
            image = base_image
            for overlay in self.overlays:
                if key in overlay.images:
                    image = overlay.images[key]
            if image is None:
                continue
            if isinstance(image, bytes):
                deck.set_key_jpeg(key, image)
            else:
                deck.set_key_image(key, image)

    def _validate_key(self, key: int) -> None:
        if isinstance(key, bool) or not isinstance(key, int) or not 0 <= key < self.key_count:
            raise ValueError(f"LCD-Tastenindex muss zwischen 0 und {self.key_count - 1} liegen")
