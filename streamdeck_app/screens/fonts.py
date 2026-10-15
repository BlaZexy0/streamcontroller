"""Shared font loading without dependencies on profiles or the service."""

from PIL import ImageFont


def ui_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)
