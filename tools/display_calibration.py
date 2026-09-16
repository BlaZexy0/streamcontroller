"""Write static orientation and pixel-width patterns to all six LCDs."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from streamdeck_app.core.device import Deck, IMAGE_SIZE, encode_image


BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
ROOT = Path(__file__).resolve().parent.parent


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype("segoeuib.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def orientation_pattern() -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, BLACK)
    draw = ImageDraw.Draw(image)
    # Intended visible orientation before the transport rotates the bitmap.
    draw.rectangle((0, 0, 59, 2), fill=(255, 40, 40))       # top: red
    draw.rectangle((57, 0, 59, 59), fill=(40, 255, 80))     # right: green
    draw.rectangle((0, 57, 59, 59), fill=(40, 100, 255))    # bottom: blue
    draw.rectangle((0, 0, 2, 59), fill=(255, 220, 30))      # left: yellow
    draw.line((30, 46, 30, 14), fill=WHITE, width=2)
    draw.polygon(((30, 8), (24, 17), (36, 17)), fill=WHITE)
    draw.text((16, 47), "OBEN", font=_font(9), fill=WHITE)
    return image


def stripe_pattern(*, vertical: bool) -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, BLACK)
    pixels = image.load()
    for y in range(60):
        for x in range(60):
            coordinate = x if vertical else y
            pixels[x, y] = WHITE if coordinate % 2 == 0 else BLACK
    return image


def width_pattern() -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, BLACK)
    draw = ImageDraw.Draw(image)
    for start, end, width in ((0, 19, 1), (20, 39, 2), (40, 59, 3)):
        x = start
        white = True
        while x <= end:
            draw.rectangle((x, 0, min(x + width - 1, end), 59), fill=WHITE if white else BLACK)
            white = not white
            x += width
    draw.line((19, 0, 19, 59), fill=(255, 50, 50), width=1)
    draw.line((39, 0, 39, 59), fill=(255, 50, 50), width=1)
    return image


def checker_pattern() -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, BLACK)
    pixels = image.load()
    for y in range(60):
        for x in range(60):
            pixels[x, y] = WHITE if (x + y) % 2 == 0 else BLACK
    return image


def checker_pattern_sized(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), BLACK)
    pixels = image.load()
    for y in range(size):
        for x in range(size):
            pixels[x, y] = WHITE if (x + y) % 2 == 0 else BLACK
    return image


def encode_exact_size(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").rotate(270).save(
        buffer,
        format="JPEG",
        quality=100,
        subsampling=0,
    )
    return buffer.getvalue()


def grid_pattern() -> Image.Image:
    image = Image.new("RGB", IMAGE_SIZE, (20, 20, 24))
    draw = ImageDraw.Draw(image)
    for position in range(0, 60, 5):
        color = (130, 130, 140) if position % 10 else WHITE
        draw.line((position, 0, position, 59), fill=color, width=1)
        draw.line((0, position, 59, position), fill=color, width=1)
    draw.line((29, 0, 29, 59), fill=(255, 50, 50), width=1)
    draw.line((0, 29, 59, 29), fill=(255, 50, 50), width=1)
    draw.rectangle((0, 0, 5, 5), fill=(255, 40, 40))
    draw.rectangle((54, 0, 59, 5), fill=(40, 255, 80))
    draw.rectangle((54, 54, 59, 59), fill=(40, 100, 255))
    draw.rectangle((0, 54, 5, 59), fill=(255, 220, 30))
    return image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--brightness", type=int, default=65)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "assets" / "test_patterns",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help="Dateien erzeugen, ohne das Deck anzusteuern",
    )
    parser.add_argument(
        "--dimension-sweep",
        action="store_true",
        help="Sechs aufeinanderfolgende Schachbrettgroessen auf die LCDs schreiben",
    )
    parser.add_argument(
        "--dimension-start",
        type=int,
        default=57,
        help="Erste JPEG-Kantenlaenge des Dimensionsvergleichs (Standard: 57)",
    )
    args = parser.parse_args()
    patterns = (
        ("01_orientation", orientation_pattern()),
        ("02_vertical_1px", stripe_pattern(vertical=True)),
        ("03_horizontal_1px", stripe_pattern(vertical=False)),
        ("04_widths_1_2_3px", width_pattern()),
        ("05_checkerboard_1px", checker_pattern()),
        ("06_grid_5px", grid_pattern()),
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, pattern in patterns:
        pattern.save(args.output_dir / f"{name}.png", format="PNG")
        (args.output_dir / f"{name}.device.jpg").write_bytes(encode_image(pattern))
    print(f"12 Testdateien exportiert: {args.output_dir}")

    if args.dimension_sweep:
        sweep_dir = args.output_dir / "dimension_sweep"
        sweep_dir.mkdir(parents=True, exist_ok=True)
        sweep = []
        sizes = range(args.dimension_start, args.dimension_start + 6)
        for size in sizes:
            pattern = checker_pattern_sized(size)
            jpeg = encode_exact_size(pattern)
            pattern.save(sweep_dir / f"checker_{size}x{size}.png", format="PNG")
            (sweep_dir / f"checker_{size}x{size}.device.jpg").write_bytes(jpeg)
            sweep.append((size, jpeg))
        print(f"Dimensionsvarianten exportiert: {sweep_dir}")
        if not args.export_only:
            with Deck() as deck:
                deck.clear_all()
                deck.set_brightness(args.brightness)
                for key, (_, jpeg) in enumerate(sweep):
                    deck.set_key_jpeg(key, jpeg)
            values = list(sizes)
            print(f"Oben: {values[0]} | {values[1]} | {values[2]} Pixel")
            print(f"Unten: {values[3]} | {values[4]} | {values[5]} Pixel")
        return

    if not args.export_only:
        with Deck() as deck:
            deck.clear_all()
            deck.set_brightness(args.brightness)
            for key, (_, pattern) in enumerate(patterns):
                deck.set_key_image(key, pattern)

        print("Kalibriermuster geschrieben; es bleibt bis zum naechsten Controller-Start sichtbar.")
        print("Oben: Rotation | 1px vertikal | 1px horizontal")
        print("Unten: 1/2/3px | 1px Schachbrett | 5px Raster")


if __name__ == "__main__":
    main()
