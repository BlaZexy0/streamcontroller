"""Rendering for one compact stock quote LCD."""

from __future__ import annotations

import time

from PIL import Image, ImageDraw

from ..core.device import IMAGE_SIZE
from ..market.model import MarketResult, WatchItem
from .profile_screen import _font


def market_tile(
    item: WatchItem,
    result: MarketResult,
    *,
    stale_seconds: float,
    now: float | None = None,
) -> Image.Image:
    current = time.time() if now is None else now
    quote = result.quote
    market_open = bool(quote) and quote.market_state in {"REGULAR", "OPEN"}
    stale = bool(quote) and (
        result.error is not None
        or market_open and current - result.fetched_at > stale_seconds
    )
    background = (34, 39, 49) if quote else (58, 38, 42)
    image = Image.new("RGB", IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, 58, 58), radius=7, outline=(210, 220, 230), width=1)
    draw.text((4, 3), item.label[:8], font=_font(10), fill=(225, 230, 238))

    if quote is None:
        draw.text((14, 23), "LADEN" if result.error is None else "FEHLER", font=_font(11), fill=(245, 150, 155))
        return image

    price = f"{quote.price:.2f}"
    price_font = _font(13 if len(price) <= 7 else 11)
    draw.text((4, 19), price, font=price_font, fill="white")
    draw.text((4, 35), quote.currency[:4], font=_font(9), fill=(165, 175, 190))

    positive = quote.change_percent >= 0
    arrow = "+" if positive else "-"
    change = f"{arrow}{abs(quote.change_percent):.1f}%"
    color = (55, 205, 125) if positive else (245, 90, 100)
    box = draw.textbbox((0, 0), change, font=_font(10))
    draw.text((56 - (box[2] - box[0]), 45), change, font=_font(10), fill=color)
    if stale:
        draw.text((49, 2), "~", font=_font(10), fill=(255, 195, 70))
    elif quote.market_state in {"CLOSED", "PRE", "PREPRE", "POST", "POSTPOST"}:
        draw.text((48, 2), "C", font=_font(8), fill=(145, 175, 225))
    return image
