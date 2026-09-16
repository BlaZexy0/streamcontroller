"""Minimal HID transport for the SOOMFON CN002 controller."""

from __future__ import annotations

import io
import threading
from typing import Any

import hid
from PIL import Image


VENDOR_ID = 0x1500
PRODUCT_ID = 0x3001
INTERFACE_NUMBER = 0
PACKET_SIZE = 1024
REPORT_SIZE = PACKET_SIZE + 1
IMAGE_SIZE = (60, 60)
JPEG_SIZE = (64, 64)
CRT = b"\x00CRT\x00\x00"
ACK = b"ACK"


class DeckConnectionError(OSError):
    """The deck vanished or a HID transfer failed."""

KEY_CODES = {
    0x01: 0,
    0x02: 1,
    0x03: 2,
    0x04: 3,
    0x05: 4,
    0x06: 5,
    0x25: 6,
    0x30: 7,
    0x31: 8,
    0x33: 9,
    0x35: 10,
    0x34: 11,
}

ENCODER_CODES = {
    0x90: (0, -1),
    0x91: (0, 1),
    0x50: (1, -1),
    0x51: (1, 1),
    0x60: (2, -1),
    0x61: (2, 1),
}


def _command(tail: bytes) -> bytes:
    return (CRT + tail).ljust(REPORT_SIZE, b"\x00")


DISPLAY_INIT = _command(b"DIS")
LIGHT_INIT = _command(b"LIG\x00\x00\x00\x00")
STOP = _command(b"STP")


def _brightness(percent: int) -> bytes:
    value = max(0, min(100, percent))
    return _command(bytes((0x4C, 0x49, 0x47, 0, 0, value)))


def _clear_all() -> bytes:
    return _command(bytes((0x43, 0x4C, 0x45, 0, 0, 0, 0xFF)))


def _image_header(key: int, size: int) -> bytes:
    return _command(
        bytes((0x42, 0x41, 0x54, 0, 0, (size >> 8) & 0xFF, size & 0xFF, key + 1))
    )


def encode_image(image: Image.Image) -> bytes:
    prepared = (
        image.convert("RGB")
        # The controller's JPEG decoder works in 8x8 MCU blocks. Supplying the
        # native 64x64 transport size avoids its uneven padding of 60x60 JPEGs.
        .resize(JPEG_SIZE, Image.Resampling.LANCZOS)
        .rotate(270)
    )
    buffer = io.BytesIO()
    # Tiny text and single-pixel patterns suffer badly from JPEG's default
    # chroma subsampling. The panel requires JPEG, so use loss-minimizing
    # settings; 60x60 images remain small enough for the HID transport.
    prepared.save(buffer, format="JPEG", quality=100, subsampling=0)
    return buffer.getvalue()


def find_control_interface() -> dict[str, Any] | None:
    return next(
        (
            item
            for item in hid.enumerate(VENDOR_ID, PRODUCT_ID)
            if item.get("interface_number") == INTERFACE_NUMBER
        ),
        None,
    )


class Deck:
    def __init__(self) -> None:
        try:
            interface = find_control_interface()
        except OSError as exc:
            raise DeckConnectionError(f"HID-Erkennung fehlgeschlagen: {exc}") from exc
        if interface is None:
            raise DeckConnectionError(
                "SOOMFON 1500:3001, Interface 0, wurde nicht gefunden."
            )

        self._device = hid.device()
        self._write_lock = threading.Lock()
        self._last_images: list[bytes | None] = [None] * 6
        self._last_brightness: int | None = None
        self.write_count = 0
        self.bytes_written = 0
        self._closed = False
        try:
            self._device.open_path(interface["path"])
            self.write(DISPLAY_INIT)
            self.write(LIGHT_INIT)
        except Exception as exc:
            self._device.close()
            if isinstance(exc, DeckConnectionError):
                raise
            raise DeckConnectionError(f"SOOMFON konnte nicht geoeffnet werden: {exc}") from exc

    def __enter__(self) -> "Deck":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _write_unlocked(self, payload: bytes) -> None:
        try:
            written = self._device.write(payload)
        except OSError as exc:
            raise DeckConnectionError(f"HID-Schreibfehler: {exc}") from exc
        if written != len(payload):
            raise DeckConnectionError(
                f"Unvollstaendiger HID-Write: {written}/{len(payload)} Bytes"
            )
        self.write_count += 1
        self.bytes_written += written

    def write(self, payload: bytes) -> None:
        with self._write_lock:
            self._write_unlocked(payload)

    def set_brightness(self, percent: int) -> bool:
        value = max(0, min(100, percent))
        if value == self._last_brightness:
            return False
        self.write(_brightness(value))
        self._last_brightness = value
        return True

    def set_key_image(self, key: int, image: Image.Image) -> bool:
        return self.set_key_jpeg(key, encode_image(image))

    def set_key_jpeg(self, key: int, data: bytes) -> bool:
        if not 0 <= key < 6:
            raise ValueError("LCD-Taste muss zwischen 0 und 5 liegen")
        if self._last_images[key] == data:
            return False
        with self._write_lock:
            self._write_unlocked(_image_header(key, len(data)))
            for offset in range(0, len(data), PACKET_SIZE):
                chunk = data[offset : offset + PACKET_SIZE]
                self._write_unlocked(b"\x00" + chunk.ljust(PACKET_SIZE, b"\x00"))
            self._write_unlocked(STOP)
        self._last_images[key] = data
        return True

    def clear_all(self) -> None:
        with self._write_lock:
            self._write_unlocked(_clear_all())
            self._write_unlocked(STOP)
        self._last_images = [None] * 6

    def read(self, timeout_ms: int = 50) -> bytes:
        try:
            return bytes(self._device.read(512, timeout_ms))
        except OSError as exc:
            raise DeckConnectionError(f"HID-Lesefehler: {exc}") from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._device.close()
        except OSError:
            pass


def decode_event(report: bytes) -> tuple[str, int, int | bool] | None:
    if len(report) < 11 or report[:3] != ACK:
        return None
    code = report[9]
    if code in KEY_CODES:
        return ("key", KEY_CODES[code], bool(report[10]))
    if code in ENCODER_CODES:
        encoder, delta = ENCODER_CODES[code]
        return ("encoder", encoder, delta)
    return None
