"""
make_icon.py — Generate electron/assets/icon.ico for PDF Extractor V3.

electron-builder (nsis + portable) requires a valid multi-size .ico with at
least a 256x256 frame. This produces a simple branded icon so packaging does
not fail. Replace assets/icon.ico with a designed icon anytime.

Run:  python make_icon.py   (from PDF Extractor V3/)
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).parent.resolve()
ASSETS = ROOT / "electron" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)
ICON = ASSETS / "icon.ico"

SIZE = 256
BG_TOP = (37, 99, 235)      # blue-600
BG_BOTTOM = (30, 58, 138)   # blue-900
FG = (255, 255, 255)


def make_base() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Vertical gradient background inside a rounded square
    for y in range(SIZE):
        t = y / (SIZE - 1)
        r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
        g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
        b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
        draw.line([(0, y), (SIZE, y)], fill=(r, g, b, 255))

    # Rounded-corner mask
    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, SIZE - 1, SIZE - 1], radius=48, fill=255
    )
    img.putalpha(mask)

    draw = ImageDraw.Draw(img)

    # Draw a document/page glyph
    page_w, page_h = 120, 150
    px = (SIZE - page_w) // 2
    py = (SIZE - page_h) // 2 - 6
    draw.rounded_rectangle(
        [px, py, px + page_w, py + page_h], radius=10, fill=FG
    )
    # Folded corner
    fold = 34
    draw.polygon(
        [
            (px + page_w - fold, py),
            (px + page_w, py + fold),
            (px + page_w - fold, py + fold),
        ],
        fill=BG_BOTTOM,
    )
    # Text lines on the page
    line_color = (37, 99, 235)
    for i in range(4):
        ly = py + 46 + i * 22
        lw = page_w - 40 if i < 3 else page_w - 70
        draw.rounded_rectangle(
            [px + 20, ly, px + 20 + lw, ly + 8], radius=4, fill=line_color
        )

    # "PDF" label
    try:
        font = ImageFont.truetype("arialbd.ttf", 40)
    except Exception:
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except Exception:
            font = ImageFont.load_default()
    label = "PDF"
    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text(
        ((SIZE - tw) // 2 - bbox[0], SIZE - th - 18 - bbox[1]),
        label,
        font=font,
        fill=FG,
    )
    return img


def main() -> None:
    base = make_base()
    sizes = [16, 24, 32, 48, 64, 128, 256]
    base.save(ICON, format="ICO", sizes=[(s, s) for s in sizes])
    print(f"[ok] wrote {ICON} ({', '.join(str(s) for s in sizes)} px)")


if __name__ == "__main__":
    main()
