"""Verse-art pin builder — Scripture overlaid on art, Pinterest-shape.

Pinterest is a search engine for evergreen content. Pins that show up in
"hymn quotes" / "scripture for anxiety" / "psalm verse art" searches drive
audience FOR YEARS. Free distribution. We make pins.

Pipeline:
  Stable Diffusion generates a thematic background → Pillow overlays Scripture
  text + small watermark → 1080×1920 PNG ready for Pinterest.

For Stage 1 audience-draw, we can pre-render a few dozen pins per week and
schedule them via Pinterest's built-in scheduler.

Pre-req:
  - pip install Pillow
  - Stable Diffusion running (optional — falls back to solid-color background)
  - render_art.py works (we use its output as input image, or generate solid color)

Usage:
  python tools/build_verse_art.py --verse "John 14:27" --text "Peace I leave with you, my peace I give unto you..."
  python tools/build_verse_art.py --from-hymns  # batch from hymns.json — one pin per hymn's anchor scripture
  python tools/build_verse_art.py --from-daily  # today's devotion scripture
"""
from __future__ import annotations
import argparse
import json
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "site" / "art" / "pins"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH, HEIGHT = 1080, 1920  # Pinterest vertical optimal
WATERMARK_TEXT = "narrowhighway.com"


def try_pil():
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return True
    except ImportError:
        return False


def find_font(size: int):
    """Find a reasonable serif font on the system."""
    from PIL import ImageFont
    candidates_serif = [
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/georgiab.ttf",
        "C:/Windows/Fonts/times.ttf",
        "/System/Library/Fonts/Georgia.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]
    for fp in candidates_serif:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def find_font_mono(size: int):
    from PIL import ImageFont
    candidates = [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cour.ttf",
        "/System/Library/Fonts/Courier.dfont",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]
    for fp in candidates:
        if Path(fp).exists():
            return ImageFont.truetype(fp, size)
    return ImageFont.load_default()


def make_pin(verse_ref: str, verse_text: str, out_path: Path, background_image: Path | None = None):
    if not try_pil():
        print("[skip] Pillow not installed — pip install Pillow")
        return False
    from PIL import Image, ImageDraw, ImageFilter

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Background: solid color gradient OR provided image
    if background_image and background_image.exists():
        bg = Image.open(background_image).convert("RGB")
        # Cover-fit to 1080x1920
        ar_target = WIDTH / HEIGHT
        ar_src = bg.width / bg.height
        if ar_src > ar_target:
            new_h = bg.height
            new_w = int(new_h * ar_target)
        else:
            new_w = bg.width
            new_h = int(new_w / ar_target)
        left = (bg.width - new_w) // 2
        top = (bg.height - new_h) // 2
        bg = bg.crop((left, top, left + new_w, top + new_h)).resize((WIDTH, HEIGHT))
        # Darken for text legibility
        from PIL import ImageEnhance
        bg = ImageEnhance.Brightness(bg).enhance(0.55)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=2))
    else:
        # Warm-dark gradient
        bg = Image.new("RGB", (WIDTH, HEIGHT), (15, 12, 20))
        draw = ImageDraw.Draw(bg)
        for y in range(HEIGHT):
            t = y / HEIGHT
            r = int(15 + (35 - 15) * t)
            g = int(12 + (25 - 12) * t)
            b = int(20 + (40 - 20) * t)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(bg)

    # Verse text — large serif, wrapped
    text_font_size = 64 if len(verse_text) > 120 else 78
    text_font = find_font(text_font_size)
    ref_font = find_font(38)
    wm_font = find_font_mono(22)

    # Wrap text to approx 22 chars per line
    wrapped = textwrap.fill(verse_text.strip().strip('"'), width=22)
    lines = wrapped.split("\n")

    # Measure
    line_heights = []
    total_h = 0
    for ln in lines:
        try:
            bbox = draw.textbbox((0, 0), ln, font=text_font)
            lh = bbox[3] - bbox[1] + 10
        except Exception:
            lh = text_font_size + 14
        line_heights.append(lh)
        total_h += lh

    # Vertical center the block
    y = (HEIGHT - total_h) // 2 - 60
    for ln, lh in zip(lines, line_heights):
        try:
            bbox = draw.textbbox((0, 0), ln, font=text_font)
            w = bbox[2] - bbox[0]
        except Exception:
            w = len(ln) * (text_font_size // 2)
        # Soft shadow
        x = (WIDTH - w) // 2
        draw.text((x + 3, y + 3), ln, font=text_font, fill=(0, 0, 0))
        draw.text((x, y), ln, font=text_font, fill=(237, 231, 219))
        y += lh

    # Reference line
    y += 24
    ref_text = "— " + verse_ref
    try:
        bbox = draw.textbbox((0, 0), ref_text, font=ref_font)
        rw = bbox[2] - bbox[0]
    except Exception:
        rw = len(ref_text) * 18
    draw.text(((WIDTH - rw) // 2, y), ref_text, font=ref_font, fill=(201, 168, 124))

    # Watermark bottom
    try:
        bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=wm_font)
        ww = bbox[2] - bbox[0]
    except Exception:
        ww = len(WATERMARK_TEXT) * 12
    draw.text(((WIDTH - ww) // 2, HEIGHT - 70), WATERMARK_TEXT, font=wm_font, fill=(180, 170, 189))

    bg.save(out_path, format="PNG")
    print(f"[wrote] {out_path}")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verse", help="Scripture reference, e.g. 'John 14:27'")
    ap.add_argument("--text", help="The verse text")
    ap.add_argument("--bg", help="Optional background image (PNG/JPG)")
    ap.add_argument("--out", help="Output PNG path")
    ap.add_argument("--from-hymns", action="store_true",
                    help="Batch: one pin per hymn (uses first scripture ref)")
    args = ap.parse_args()

    if args.from_hymns:
        hymns_json = REPO / "site" / "hymns.json"
        if not hymns_json.exists():
            print(f"[err] {hymns_json} not found; run tools/hymnary_scrape.py first")
            return 1
        blob = json.loads(hymns_json.read_text(encoding="utf-8"))
        n = 0
        for h in blob.get("hymns", []):
            ref = (h.get("scripture") or [None])[0]
            if not ref:
                continue
            first_verse = (h.get("text") or "").split("\n\n")[0].replace("\n", " ").strip()
            if len(first_verse) > 140:
                first_verse = first_verse[:140].rsplit(" ", 1)[0] + "…"
            out = OUT_DIR / f"hymn_{h['slug']}.png"
            if out.exists():
                continue
            # Background: use SD-generated cover if exists
            bg = REPO / "site" / "art" / f"{h['slug']}.png"
            if make_pin(ref, first_verse, out, background_image=bg if bg.exists() else None):
                n += 1
        print(f"\nGenerated {n} pin(s) -> {OUT_DIR}")
        return 0

    if not args.verse or not args.text:
        ap.print_help()
        return 0

    out = Path(args.out) if args.out else OUT_DIR / (args.verse.replace(" ", "_").replace(":", "_") + ".png")
    bg = Path(args.bg) if args.bg else None
    ok = make_pin(args.verse, args.text, out, background_image=bg)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
