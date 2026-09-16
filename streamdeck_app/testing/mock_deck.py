"""In-memory deck with realistic blocking reads and display caching."""

from __future__ import annotations

import queue
import time

from PIL import Image

from ..core.device import encode_image


class MockDeck:
    def __init__(self) -> None:
        self.brightness: int | None = None
        self.images: list[bytes | None] = [None] * 6
        self.events: queue.Queue[bytes] = queue.Queue()
        self.image_write_count = 0
        self.command_count = 0
        self.bytes_written = 0
        self.first_display_at: float | None = None
        self.closed = False
        self.operations: list[str] = []

    def __enter__(self) -> "MockDeck":
        self.closed = False
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def set_brightness(self, percent: int) -> bool:
        value = max(0, min(100, percent))
        if self.brightness == value:
            return False
        self.brightness = value
        self.operations.append(f"brightness:{value}")
        self.command_count += 1
        self.bytes_written += 1025
        return True

    def set_key_image(self, key: int, image: Image.Image) -> bool:
        return self.set_key_jpeg(key, encode_image(image))

    def set_key_jpeg(self, key: int, data: bytes) -> bool:
        if self.images[key] == data:
            return False
        self.images[key] = data
        self.operations.append(f"image:{key}")
        self.image_write_count += 1
        chunks = max(1, (len(data) + 1023) // 1024)
        self.command_count += chunks + 2
        self.bytes_written += (chunks + 2) * 1025
        if self.first_display_at is None:
            self.first_display_at = time.perf_counter()
        return True

    def clear_all(self) -> None:
        self.images = [None] * 6
        self.operations.append("clear")
        self.command_count += 2
        self.bytes_written += 2050

    def read(self, timeout_ms: int = 100) -> bytes:
        try:
            return self.events.get(timeout=timeout_ms / 1000)
        except queue.Empty:
            return b""

    def push_report(self, report: bytes) -> None:
        self.events.put(report)

    def close(self) -> None:
        self.closed = True
