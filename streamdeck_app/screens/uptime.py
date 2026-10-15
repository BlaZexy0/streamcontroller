"""Compact Uptime Kuma monitor tiles."""

from __future__ import annotations

from PIL import Image, ImageDraw

from ..core.device import IMAGE_SIZE
from ..uptime import MonitorStatus
from .fonts import ui_font as _font


def _fit(draw: ImageDraw.ImageDraw, text: str, width: int = 52) -> str:
    value = " ".join(text.split())
    while value and draw.textlength(value, font=_font(10)) > width:
        value = value[:-1]
    return value.rstrip()


def uptime_tile(monitor: MonitorStatus, *, page: int = 1, pages: int = 1) -> Image.Image:
    if monitor.status == 1:
        background, accent, state = (20, 66, 45), (55, 220, 135), "ONLINE"
    elif monitor.status == 0:
        background, accent, state = (76, 31, 38), (255, 92, 105), "OFFLINE"
    elif monitor.status == 3:
        background, accent, state = (73, 59, 25), (255, 196, 70), "WARTUNG"
    else:
        background, accent, state = (48, 52, 63), (160, 170, 188), "WARTEN"
    image = Image.new("RGB", IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=7, outline=accent, width=2)
    draw.ellipse((5, 6, 11, 12), fill=accent)
    draw.text((15, 4), _fit(draw, monitor.name, 39), font=_font(10), fill="white")
    draw.text((5, 23), state, font=_font(10), fill=accent)
    ping = "-- ms" if monitor.ping_ms is None else f"{monitor.ping_ms:.0f} ms"
    draw.text((5, 39), ping, font=_font(10), fill=(225, 230, 236))
    if pages > 1:
        draw.text((43, 49), f"{page}/{pages}", font=_font(7), fill=(160, 170, 180))
    return image


def uptime_message_tile(title: str, detail: str = "") -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, (43, 47, 58))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=7, outline=(150, 165, 185), width=1)
    draw.text((5, 8), title[:9], font=_font(11), fill=(245, 190, 75))
    words = detail.split()
    draw.text((5, 28), " ".join(words[:2])[:10], font=_font(9), fill=(220, 225, 232))
    draw.text((5, 40), " ".join(words[2:4])[:10], font=_font(9), fill=(220, 225, 232))
    return image

