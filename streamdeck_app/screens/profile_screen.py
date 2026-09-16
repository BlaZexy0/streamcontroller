"""Rendering for the six normal profile buttons."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont

from ..core.device import IMAGE_SIZE
from ..profiles.model import Button


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def profile_tile(button: Button, locked: bool = False) -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, button.color)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=8, outline=(255, 255, 255), width=2)

    label = button.label[:7]
    font_size = 22 if len(label) <= 3 else 13
    font = _font(font_size)
    box = draw.textbbox((0, 0), label, font=font, stroke_width=1)
    x = (60 - (box[2] - box[0])) // 2
    y = (60 - (box[3] - box[1])) // 2 - 2
    draw.text((x, y), label, font=font, fill="white", stroke_width=1, stroke_fill="black")
    if locked:
        draw.ellipse((48, 3, 56, 11), fill=(255, 205, 35), outline=(45, 35, 0))
    return image
