"""Compact six-tile Spotify now-playing screen."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from ..core.device import IMAGE_SIZE
from ..media.model import MediaState
from .fonts import ui_font as _font

SPOTIFY_GREEN = (29, 185, 84)
PANEL = (19, 31, 25)


def _control_tile(label: str) -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, (25, 145, 75))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=8, outline="white", width=2)
    font = _font(13)
    box = draw.textbbox((0, 0), label, font=font, stroke_width=1)
    x = (60 - (box[2] - box[0])) // 2
    y = (60 - (box[3] - box[1])) // 2 - 2
    draw.text((x, y), label, font=font, fill="white", stroke_width=1, stroke_fill="black")
    return image


def _fit_text(draw: ImageDraw.ImageDraw, text: str, width: int, size: int) -> str:
    value = " ".join(text.split())
    font = _font(size)
    if draw.textlength(value, font=font) <= width:
        return value
    while value and draw.textlength(value + "...", font=font) > width:
        value = value[:-1]
    return value.rstrip() + "..." if value else ""


def _cover_tile(state: MediaState) -> Image.Image:
    image: Image.Image | None = None
    if state.artwork:
        try:
            with Image.open(BytesIO(state.artwork)) as source:
                image = ImageOps.fit(source.convert("RGB"), IMAGE_SIZE)
        except (OSError, UnidentifiedImageError):
            image = None
    if image is None:
        image = Image.new("RGB", IMAGE_SIZE, SPOTIFY_GREEN if state.available else PANEL)
        draw = ImageDraw.Draw(image)
        draw.ellipse((12, 12, 48, 48), fill=(10, 20, 14))
        for offset in (0, 7, 14):
            draw.arc((19, 20 + offset, 43, 36 + offset), 205, 330, fill="white", width=2)

    draw = ImageDraw.Draw(image)
    draw.ellipse((39, 39, 58, 58), fill=(8, 15, 11), outline=SPOTIFY_GREEN, width=2)
    if state.playing:
        draw.rectangle((46, 45, 48, 53), fill="white")
        draw.rectangle((51, 45, 53, 53), fill="white")
    else:
        draw.polygon(((46, 44), (46, 54), (54, 49)), fill="white")
    return image


def _metadata_tiles(state: MediaState) -> tuple[Image.Image, Image.Image, Image.Image]:
    canvas = Image.new("RGB", (180, 60), PANEL)
    draw = ImageDraw.Draw(canvas)
    labels = ("VOL-", "MUTE", "VOL+")
    for index, label in enumerate(labels):
        box = draw.textbbox((0, 0), label, font=_font(8))
        x = index * 60 + (60 - (box[2] - box[0])) // 2
        draw.text((x, 2), label, font=_font(8), fill=(110, 170, 130))

    if state.error:
        artist, title, color = "MEDIENFEHLER", state.error, (245, 115, 110)
    elif not state.available:
        artist, title, color = "SPOTIFY", "Keine Wiedergabe", (155, 170, 160)
    else:
        artist = state.artist or "Unbekannter Interpret"
        title = state.title or "Unbekannter Titel"
        color = (238, 245, 240)
    draw.text((5, 17), _fit_text(draw, artist, 170, 11), font=_font(11), fill=SPOTIFY_GREEN)
    draw.text((5, 34), _fit_text(draw, title, 170, 13), font=_font(13), fill=color)
    status = "LIVE" if state.playing else "PAUSE" if state.status == "paused" else ""
    if status:
        draw.text((145, 50), status, font=_font(7), fill=(125, 145, 132))
    return tuple(canvas.crop((x, 0, x + 60, 60)) for x in (0, 60, 120))  # type: ignore[return-value]


def spotify_tiles(state: MediaState) -> tuple[Image.Image, ...]:
    previous = _control_tile("PREV")
    following = _control_tile("NEXT")
    return (previous, _cover_tile(state), following, *_metadata_tiles(state))
