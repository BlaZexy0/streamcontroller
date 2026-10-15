"""Short confirmation overlay for Discord voice actions."""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..core.device import IMAGE_SIZE
from .fonts import ui_font


def discord_confirmation(action: str) -> dict[int, Image.Image]:
    words = {
        "microphone": ("MIC", "UM", "SCHALT"),
        "deafen": ("DEAF", "UM", "SCHALT"),
    }.get(action, ("DIS", "CORD", "OK"))
    images: dict[int, Image.Image] = {}
    for index, word in enumerate(words):
        image = Image.new("RGB", IMAGE_SIZE, (55, 65, 105))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((1, 1, 58, 58), radius=8, outline=(155, 170, 255), width=2)
        font = ui_font(15 if len(word) <= 4 else 11)
        box = draw.textbbox((0, 0), word, font=font, stroke_width=1)
        x = (60 - (box[2] - box[0])) // 2
        y = (60 - (box[3] - box[1])) // 2 - 2
        draw.text((x, y), word, font=font, fill="white", stroke_width=1, stroke_fill=(20, 25, 45))
        images[index] = image
    return images
