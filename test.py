"""Interaktiver Funktionstest fuer den SOOMFON Stream Controller SE.

Getestet wird das Modell CN002 mit USB-ID 1500:3001. Die normale
Hersteller-Anwendung muss waehrend des Tests geschlossen sein.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import hid
from PIL import Image, ImageDraw, ImageFont


VENDOR_ID = 0x1500
PRODUCT_ID = 0x3001
INTERFACE_NUMBER = 0

PACKET_SIZE = 1024
REPORT_SIZE = PACKET_SIZE + 1
IMAGE_SIZE = (60, 60)
IMAGE_ROTATION = 270
CRT = b"\x00CRT\x00\x00"
ACK = b"ACK"

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

KEY_NAMES = [
    *(f"LCD-Taste {number}" for number in range(1, 7)),
    *(f"Zusatztaste {number}" for number in range(1, 4)),
    *(f"Encoder {number} druecken" for number in range(1, 4)),
]

TEST_COLORS = [
    (220, 40, 40),
    (230, 130, 25),
    (215, 190, 25),
    (35, 170, 75),
    (35, 110, 220),
    (155, 55, 205),
]


def command(tail: bytes) -> bytes:
    return (CRT + tail).ljust(REPORT_SIZE, b"\x00")


DISPLAY_INIT = command(b"DIS")
LIGHT_INIT = command(b"LIG\x00\x00\x00\x00")
STOP = command(b"STP")


def brightness_command(percent: int) -> bytes:
    value = max(0, min(100, percent))
    return command(bytes((0x4C, 0x49, 0x47, 0, 0, value)))


def clear_command(key: int = -1) -> bytes:
    wire_key = 0xFF if key < 0 else key + 1
    return command(bytes((0x43, 0x4C, 0x45, 0, 0, 0, wire_key)))


def image_header(key: int, size: int) -> bytes:
    return command(
        bytes((0x42, 0x41, 0x54, 0, 0, (size >> 8) & 0xFF, size & 0xFF, key + 1))
    )


def encode_image(image: Image.Image) -> bytes:
    prepared = (
        image.convert("RGB")
        .resize(IMAGE_SIZE, Image.Resampling.LANCZOS)
        .rotate(IMAGE_ROTATION)
    )
    buffer = io.BytesIO()
    prepared.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_image(number: int, color: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, color)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    label = str(number)
    box = draw.textbbox((0, 0), label, font=font, stroke_width=1)
    width = box[2] - box[0]
    height = box[3] - box[1]
    position = ((IMAGE_SIZE[0] - width) // 2, (IMAGE_SIZE[1] - height) // 2 - 2)
    draw.rectangle((1, 1, 58, 58), outline="white", width=2)
    draw.text(position, label, fill="white", font=font, stroke_width=2, stroke_fill="black")
    return image


def matching_devices() -> list[dict[str, Any]]:
    return list(hid.enumerate(VENDOR_ID, PRODUCT_ID))


def control_interface(devices: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (item for item in devices if item.get("interface_number") == INTERFACE_NUMBER),
        None,
    )


class Deck:
    def __init__(self, path: bytes) -> None:
        self._device = hid.device()
        self._write_lock = threading.Lock()
        try:
            self._device.open_path(path)
            self.write(DISPLAY_INIT)
            self.write(LIGHT_INIT)
        except Exception:
            self._device.close()
            raise

    def __enter__(self) -> "Deck":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def write(self, payload: bytes) -> None:
        with self._write_lock:
            self._write_unlocked(payload)

    def _write_unlocked(self, payload: bytes) -> None:
        written = self._device.write(payload)
        if written != len(payload):
            raise OSError(f"Unvollstaendiger HID-Write: {written}/{len(payload)} Bytes")

    def set_brightness(self, percent: int) -> None:
        self.write(brightness_command(percent))

    def set_key_image(self, key: int, image: Image.Image) -> None:
        if not 0 <= key < 6:
            raise ValueError("LCD-Taste muss zwischen 0 und 5 liegen")
        data = encode_image(image)
        with self._write_lock:
            self._write_unlocked(image_header(key, len(data)))
            for offset in range(0, len(data), PACKET_SIZE):
                chunk = data[offset : offset + PACKET_SIZE]
                report = b"\x00" + chunk.ljust(PACKET_SIZE, b"\x00")
                self._write_unlocked(report)
            self._write_unlocked(STOP)

    def clear_all(self) -> None:
        with self._write_lock:
            self._write_unlocked(clear_command())
            self._write_unlocked(STOP)

    def read(self, timeout_ms: int = 100) -> bytes:
        return bytes(self._device.read(512, timeout_ms))

    def close(self) -> None:
        self._device.close()


@dataclass
class TestResult:
    mode: str = "interactive"
    started_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat())
    device_found: bool = False
    device_opened: bool = False
    display_writes: bool = False
    display_visual: bool | None = None
    brightness_writes: bool = False
    brightness_visual: bool | None = None
    pressed: list[bool] = field(default_factory=lambda: [False] * 12)
    released: list[bool] = field(default_factory=lambda: [False] * 12)
    encoder_left: list[bool] = field(default_factory=lambda: [False] * 3)
    encoder_right: list[bool] = field(default_factory=lambda: [False] * 3)
    completed: bool = False
    error: str | None = None


def device_summary(device: dict[str, Any]) -> dict[str, Any]:
    return {
        "vendor_id": f"0x{device['vendor_id']:04X}",
        "product_id": f"0x{device['product_id']:04X}",
        "manufacturer": device.get("manufacturer_string") or "-",
        "product": device.get("product_string") or "-",
        "serial": device.get("serial_number") or "-",
        "interface": device.get("interface_number"),
    }


def ask_visible(question: str) -> bool | None:
    while True:
        answer = input(f"{question} [J/n/u = unklar]: ").strip().lower()
        if answer in ("", "j", "ja", "y", "yes"):
            return True
        if answer in ("n", "nein", "no"):
            return False
        if answer in ("u", "unklar", "s", "skip"):
            return None
        print("Bitte J, n oder u eingeben.")


def checklist_complete(result: TestResult) -> bool:
    return all(
        (
            *result.pressed,
            *result.released,
            *result.encoder_left,
            *result.encoder_right,
        )
    )


def print_checklist(result: TestResult) -> None:
    def mark(value: bool) -> str:
        return "OK" if value else "--"

    print("\nEingabe-Checkliste:")
    for index, name in enumerate(KEY_NAMES):
        print(
            f"  [{mark(result.pressed[index])}/{mark(result.released[index])}] "
            f"{name} (druecken/loslassen)"
        )
    for encoder in range(3):
        print(
            f"  [{mark(result.encoder_left[encoder])}/{mark(result.encoder_right[encoder])}] "
            f"Encoder {encoder + 1} (links/rechts)"
        )


def test_inputs(deck: Deck, result: TestResult, timeout: float) -> None:
    print("\nJetzt alle 6 LCD-Tasten, 3 Zusatztasten und 3 Encoder druecken.")
    print("Jeden Encoder ausserdem mindestens einen Schritt nach links und rechts drehen.")
    print("Strg+C bricht den Test ab. Die Checkliste erscheint nach jedem neuen Treffer.")
    print_checklist(result)
    deadline = time.monotonic() + timeout

    while not checklist_complete(result):
        if time.monotonic() >= deadline:
            print(f"\nZeitlimit von {timeout:.0f} Sekunden erreicht.")
            return

        report = deck.read(timeout_ms=100)
        if len(report) < 11 or report[:3] != ACK:
            continue

        code = report[9]
        state = bool(report[10])
        changed = False

        if code in KEY_CODES:
            key = KEY_CODES[code]
            target = result.pressed if state else result.released
            if not target[key]:
                target[key] = True
                changed = True
        elif code in ENCODER_CODES:
            encoder, delta = ENCODER_CODES[code]
            target = result.encoder_right if delta > 0 else result.encoder_left
            if not target[encoder]:
                target[encoder] = True
                changed = True

        if changed:
            print_checklist(result)


def save_report(result: TestResult, device: dict[str, Any] | None) -> Path:
    path = Path(__file__).with_name("function_test_report.json")
    payload = asdict(result)
    payload["device"] = device_summary(device) if device else None
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def diagnose() -> int:
    devices = matching_devices()
    interface = control_interface(devices)
    print(f"Gefundene HID-Interfaces fuer {VENDOR_ID:04X}:{PRODUCT_ID:04X}: {len(devices)}")
    for item in devices:
        print(json.dumps(device_summary(item), ensure_ascii=False))
    if interface is None:
        print("FEHLER: Steuer-Interface 0 wurde nicht gefunden.")
        return 1
    print("OK: SOOMFON-Steuer-Interface 0 ist vorhanden.")
    return 0


def run_test(timeout: float, interactive: bool) -> int:
    result = TestResult(mode="interactive" if interactive else "smoke")
    device: dict[str, Any] | None = None
    deck: Deck | None = None

    try:
        devices = matching_devices()
        device = control_interface(devices)
        result.device_found = device is not None
        if device is None:
            raise RuntimeError(
                "SOOMFON 1500:3001, Interface 0, wurde nicht gefunden. "
                "USB-Datenkabel und Anschluss pruefen."
            )

        print("Geraet erkannt:")
        for key, value in device_summary(device).items():
            print(f"  {key}: {value}")

        try:
            deck = Deck(device["path"])
        except OSError as exc:
            raise RuntimeError(
                "Das Geraet konnte nicht exklusiv geoeffnet werden. "
                "Bitte die SOOMFON-Hersteller-App vollstaendig schliessen."
            ) from exc
        result.device_opened = True

        print("\nDisplaytest: Schreibe sechs Farben und die Nummern 1 bis 6 ...")
        deck.set_brightness(100)
        for key, color in enumerate(TEST_COLORS):
            deck.set_key_image(key, test_image(key + 1, color))
        result.display_writes = True
        if interactive:
            result.display_visual = ask_visible(
                "Sind alle sechs Farben, weissen Rahmen und Nummern richtig sichtbar?"
            )

        print("Helligkeitstest: 20 % -> 100 % -> 60 % ...")
        for value in (20, 100, 60):
            deck.set_brightness(value)
            time.sleep(0.8)
        result.brightness_writes = True
        if interactive:
            result.brightness_visual = ask_visible(
                "War der deutliche Helligkeitswechsel sichtbar?"
            )
            test_inputs(deck, result, timeout)

        result.completed = (
            result.device_found
            and result.device_opened
            and result.display_writes
            and result.brightness_writes
            and (not interactive or checklist_complete(result))
            and result.display_visual is not False
            and result.brightness_visual is not False
        )
    except (KeyboardInterrupt, EOFError):
        result.error = "Test durch Benutzer abgebrochen."
        print("\nTest abgebrochen.")
    except Exception as exc:  # klare Diagnose statt ungeklaertem Traceback
        result.error = str(exc)
        print(f"\nFEHLER: {exc}", file=sys.stderr)
    finally:
        if deck is not None:
            try:
                deck.set_brightness(60)
                deck.clear_all()
            except OSError:
                pass
            deck.close()

    report_path = save_report(result, device)
    if interactive:
        print_checklist(result)
    print(f"\nErgebnis: {'BESTANDEN' if result.completed else 'NICHT VOLLSTAENDIG BESTANDEN'}")
    print(f"Bericht: {report_path}")
    return 0 if result.completed else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="nur USB-Erkennung pruefen, nichts an das Geraet senden",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Ausgabefunktionen automatisch testen, keine Eingaben abfragen",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="Zeitlimit fuer den Eingabetest in Sekunden (Standard: 180)",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout muss groesser als 0 sein")
    return args


def main() -> int:
    args = parse_args()
    if args.diagnose:
        return diagnose()
    return run_test(timeout=args.timeout, interactive=not args.smoke)


if __name__ == "__main__":
    raise SystemExit(main())
