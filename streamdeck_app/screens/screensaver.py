"""Offline idle animation for the upper three LCD keys."""

from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageEnhance

from ..core.device import IMAGE_SIZE, encode_image
from ..paths import resource_path


CREATURES = (
    resource_path("assets", "screensaver", "emberling.png"),
    resource_path("assets", "screensaver", "aquaffin.png"),
    resource_path("assets", "screensaver", "spriggle.png"),
)
CREATURE_GLOWS = ((255, 85, 25), (20, 160, 255), (120, 230, 50))


class IdleAnimation:
    """Pre-rendered breathing/bobbing loop to keep live HID work cheap."""

    def __init__(self, frame_count: int = 12) -> None:
        sources: list[Image.Image] = []
        for path in CREATURES:
            with Image.open(path) as image:
                sources.append(
                    image.convert("RGBA").resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
                )
        self.frames: list[list[bytes]] = []
        for frame_index in range(frame_count):
            phase = 2 * math.pi * frame_index / frame_count
            row: list[bytes] = []
            for creature_index, (source, glow) in enumerate(zip(sources, CREATURE_GLOWS)):
                local_phase = phase + creature_index * 0.9
                scale = 0.80 + 0.035 * math.sin(local_phase)
                y_offset = round(2.0 * math.sin(local_phase))
                size = max(1, round(60 * scale))
                sprite = source.resize((size, size), Image.Resampling.LANCZOS)
                sprite = ImageEnhance.Brightness(sprite).enhance(
                    0.94 + 0.10 * (math.sin(local_phase) + 1) / 2
                )

                canvas = Image.new("RGBA", IMAGE_SIZE, (4, 7, 16, 255))
                draw = ImageDraw.Draw(canvas)
                pulse = int(18 + 9 * (math.sin(local_phase) + 1))
                draw.ellipse((8, 43, 52, 57), fill=(*glow, pulse))
                x = (60 - size) // 2
                y = (60 - size) // 2 + y_offset
                canvas.alpha_composite(sprite, (x, y))
                row.append(encode_image(canvas))
            self.frames.append(row)

    def get(self, frame_index: int) -> list[bytes]:
        return self.frames[frame_index % len(self.frames)]

    def __len__(self) -> int:
        return len(self.frames)
