"""Small three-LCD overlays for Windows audio feedback."""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..core.audio import AudioDeviceState, AudioState
from ..core.device import IMAGE_SIZE
from .profile_screen import _font


def _tile(background: tuple[int, int, int]) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=8, outline=(235, 245, 255), width=2)
    return image, draw


def volume_overlay(state: AudioState) -> dict[int, Image.Image]:
    accent = (190, 55, 65) if state.muted else (35, 145, 105)

    label, draw = _tile((28, 34, 45))
    text = "MUTE" if state.muted else state.label[:7]
    font = _font(15 if state.muted or len(text) > 4 else 18)
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((60 - box[2]) // 2, 19), text, font=font, fill=accent)

    value, draw = _tile((24, 31, 42))
    font = _font(19)
    text = f"{state.percent}%"
    box = draw.textbbox((0, 0), text, font=font)
    draw.text(((60 - box[2]) // 2, 17), text, font=font, fill="white")

    meter, draw = _tile((28, 34, 45))
    lit = 0 if state.muted else round(state.percent / 10)
    for segment in range(10):
        x = 7 + (segment % 5) * 10
        y = 32 if segment < 5 else 18
        color = accent if segment < lit else (65, 72, 82)
        draw.rounded_rectangle((x, y, x + 7, y + 8), radius=2, fill=color)

    return {0: label, 1: value, 2: meter}


def message_overlay(first: str, second: str, third: str) -> dict[int, Image.Image]:
    result: dict[int, Image.Image] = {}
    for key, text in enumerate((first, second, third)):
        image, draw = _tile((45, 35, 42))
        shown = text[:9]
        font = _font(13 if len(shown) > 5 else 17)
        box = draw.textbbox((0, 0), shown, font=font)
        draw.text(
            ((60 - (box[2] - box[0])) // 2, 19),
            shown,
            font=font,
            fill=(245, 225, 230),
        )
        result[key] = image
    return result


def device_overlay(state: AudioDeviceState) -> dict[int, Image.Image]:
    words = state.name.replace("(", " ").replace(")", " ").split()
    label = " ".join(words[:2]) if words else "AUDIO"
    return message_overlay("OUTPUT", "WECHSEL", label)
