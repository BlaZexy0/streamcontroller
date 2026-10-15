"""Safe preparation and local storage for the persistent controller boot logo."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


VISIBLE_SIZE = (320, 240)
TRANSPORT_SIZE = (240, 320)
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_PIXELS = 20_000_000
MAX_JPEG_BYTES = 0xFFFF


class BootLogoError(ValueError):
    """The selected file cannot be converted into a safe device logo."""


def boot_logo_path(config_path: Path) -> Path:
    return config_path.with_name("boot_logo.jpg")


def _open_source(data: bytes) -> Image.Image:
    if not data or len(data) > MAX_SOURCE_BYTES:
        raise BootLogoError("Das Bild darf hoechstens 8 MB gross sein")
    try:
        with Image.open(io.BytesIO(data)) as source:
            width, height = source.size
            if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
                raise BootLogoError("Das Bild ist zu gross oder hat ungueltige Abmessungen")
            source.load()
            return ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise BootLogoError("Die Datei ist kein lesbares Bild") from exc


def prepare_boot_logo(data: bytes) -> tuple[bytes, bytes]:
    """Return a metadata-free visible preview and the rotated transport JPEG."""

    source = _open_source(data)
    visible = ImageOps.fit(
        source,
        VISIBLE_SIZE,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    # Pillow propagates fields such as JPEG comments through resize/crop
    # operations. Clear them explicitly before creating either output file.
    visible.info.clear()

    preview_buffer = io.BytesIO()
    visible.save(
        preview_buffer,
        format="JPEG",
        quality=92,
        subsampling=0,
        optimize=True,
        progressive=False,
    )

    # The AKP03/CN002 firmware expects a portrait JPEG. It rotates this data
    # back onto the landscape 320x240 boot screen.
    transport = visible.transpose(Image.Transpose.ROTATE_270)
    transport.info.clear()
    transport_buffer = io.BytesIO()
    transport.save(
        transport_buffer,
        format="JPEG",
        quality=90,
        subsampling=0,
        optimize=True,
        progressive=False,
    )
    transport_data = transport_buffer.getvalue()
    if len(transport_data) > MAX_JPEG_BYTES:
        raise BootLogoError("Das vorbereitete Bootlogo ist fuer den Controller zu gross")
    return preview_buffer.getvalue(), transport_data


def save_boot_logo(config_path: Path, preview_data: bytes) -> Path:
    path = boot_logo_path(config_path)
    temporary = path.with_suffix(".jpg.tmp")
    temporary.write_bytes(preview_data)
    temporary.replace(path)
    return path
