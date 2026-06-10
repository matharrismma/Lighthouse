"""generate_platform_assets.py — Build the full platform asset pack from logo_master.png.

Output sizes for every platform Narrow Highway is targeting:
  - YouTube profile (800x800 square, emblem-only crop)
  - YouTube banner (2048x1152, full logo centered with mobile-safe zone)
  - YouTube watermark (150x150, emblem only)
  - Roku FHD poster (1920x1080)
  - Roku HD poster (1280x720)
  - Roku SD poster (540x405)
  - Roku channel icon HD (290x218)
  - Roku channel icon SD (248x140)
  - Roku splash (1920x1080)
  - LG TV Plus (1920x1080)
  - Samsung TV Plus (1920x1080)
  - Favicon (32x32 + 16x16)
  - Apple touch icon (180x180)
  - OG card (1200x630)

Strategy:
  Wide targets (16:9, 2:1)  → composite full logo on black canvas, centered
  Square targets            → crop to emblem-only (top ~64% of source), pad to square
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SRC = Path("D:/library_files/_channel_bumpers/narrow-highway/logo_master.png")
OUT_BRAND = Path("D:/library_files/_channel_bumpers/narrow-highway")
OUT_SITE = REPO / "site" / "img"
OUT_SITE.mkdir(parents=True, exist_ok=True)

BG = (10, 10, 10)  # near-black, matches source background


def emblem_only(img: Image.Image) -> Image.Image:
    """Crop the source to just the emblem (everything above the wordmark).
    The wordmark + tagline occupy roughly the bottom 36% of the master."""
    w, h = img.size
    # Empirically: emblem ends ~y=560 in a 1024-tall image (~55% height).
    # Keep some headroom; crop to top 60%.
    return img.crop((0, 0, w, int(h * 0.60)))


def fit_centered(src: Image.Image, target_w: int, target_h: int,
                 padding_frac: float = 0.08) -> Image.Image:
    """Composite the source onto a target-sized black canvas, scaled to fit
    inside (target_w * (1 - 2*padding_frac), target_h * (1 - 2*padding_frac))
    and centered."""
    canvas = Image.new("RGB", (target_w, target_h), BG)
    avail_w = int(target_w * (1 - 2 * padding_frac))
    avail_h = int(target_h * (1 - 2 * padding_frac))
    sw, sh = src.size
    scale = min(avail_w / sw, avail_h / sh)
    new_w, new_h = int(sw * scale), int(sh * scale)
    scaled = src.resize((new_w, new_h), Image.LANCZOS)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas.paste(scaled, (x, y))
    return canvas


def square_emblem(src: Image.Image, size: int) -> Image.Image:
    """Square canvas with just the emblem (no wordmark), centered."""
    em = emblem_only(src)
    # Pad to square first by adding black left/right (emblem is wider than tall)
    ew, eh = em.size
    side = max(ew, eh)
    sq = Image.new("RGB", (side, side), BG)
    sq.paste(em, ((side - ew) // 2, (side - eh) // 2))
    # Now resize to target with modest padding
    return fit_centered(sq, size, size, padding_frac=0.06)


def main():
    src = Image.open(SRC).convert("RGB")
    print(f"source: {src.size}")
    targets = [
        # ((width, height), output_filename, "crop_mode")
        # crop_mode: "full" = use whole logo; "emblem" = emblem-only square crop
        ((800, 800),   "youtube_profile.png",    "emblem"),
        ((2048, 1152), "youtube_banner.png",     "full"),
        ((150, 150),   "youtube_watermark.png",  "emblem"),
        ((1920, 1080), "roku_poster_fhd.png",    "full"),
        ((1280, 720),  "roku_poster_hd.png",     "full"),
        ((540, 405),   "roku_poster_sd.png",     "full"),
        ((290, 218),   "roku_icon_hd.png",       "full"),
        ((248, 140),   "roku_icon_sd.png",       "full"),
        ((1920, 1080), "roku_splash.png",        "full"),
        ((1920, 1080), "lg_tv_plus.png",         "full"),
        ((1920, 1080), "samsung_tv_plus.png",    "full"),
        ((1200, 630),  "og_card.png",            "full"),
        ((180, 180),   "apple_touch_icon.png",   "emblem"),
        ((32, 32),     "favicon_32.png",         "emblem"),
        ((16, 16),     "favicon_16.png",         "emblem"),
        # Public-site primary logo (same as input but re-saved at known size)
        ((1536, 1024), "channel-narrow-highway.png", "full"),
    ]
    for (w, h), fname, mode in targets:
        if mode == "emblem":
            out = square_emblem(src, max(w, h))
            if w != h:
                # rare case: rectangular emblem-only (unused here, but safe)
                out = out.resize((w, h), Image.LANCZOS)
        else:
            out = fit_centered(src, w, h, padding_frac=0.08)
        brand_path = OUT_BRAND / fname
        out.save(brand_path, "PNG", optimize=True)
        # Also drop site-facing assets into site/img/
        if fname in (
            "channel-narrow-highway.png",
            "og_card.png",
            "apple_touch_icon.png",
            "favicon_32.png",
            "favicon_16.png",
        ):
            (OUT_SITE / fname).write_bytes(brand_path.read_bytes())
        size_kb = brand_path.stat().st_size // 1024
        print(f"  {fname:<32}  {w}x{h}  {size_kb} KB")

    # ICO multi-resolution favicon for site root
    ico_path = OUT_SITE / "favicon.ico"
    ico_src = src.copy()
    em = emblem_only(ico_src)
    ew, eh = em.size
    side = max(ew, eh)
    sq = Image.new("RGB", (side, side), BG)
    sq.paste(em, ((side - ew) // 2, (side - eh) // 2))
    ico_img = sq.resize((256, 256), Image.LANCZOS)
    ico_img.save(ico_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    print(f"  favicon.ico                       multi-res  {ico_path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
