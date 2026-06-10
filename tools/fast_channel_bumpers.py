"""Generate channel bumpers (station IDs, Up Next cards, pastoral cards) as MP4s.

A FAST channel needs short "bumpers" between content — like the 5-second
"You're watching..." stings that classic TV has every half hour. These are
rendered as short MP4s (6-15 sec each) and inserted between content in the
24h schedule.

Output: D:/library_files/_channel_bumpers/<channel_id>/<bumper_id>.mp4
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()

W, H = 1920, 1080
FPS = 30


def font(size: int, italic: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    if italic and bold:
        candidates = ["C:/Windows/Fonts/georgiaz.ttf"]
    elif italic:
        candidates = ["C:/Windows/Fonts/georgiai.ttf"]
    elif bold:
        candidates = ["C:/Windows/Fonts/georgiab.ttf"]
    else:
        candidates = ["C:/Windows/Fonts/georgia.ttf"]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def text_center(drw, xy_center, text, fnt, fill):
    bbox = drw.textbbox((0, 0), text, font=fnt)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    cx, cy = xy_center
    drw.text((cx - w // 2, cy - h // 2), text, font=fnt, fill=fill)


def render_card_png(bumper: dict, channel: dict, out_png: Path,
                    current_title: str = "", next_title: str = "", next_subtitle: str = ""):
    """Render one bumper card to PNG."""
    bg = Image.new("RGB", (W, H), color=channel.get("color_primary", "#1B4D8C"))
    drw = ImageDraw.Draw(bg)
    # Subtle radial gradient via overlay
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(overlay)
    for r in range(0, max(W, H), 40):
        ovd.ellipse([(W//2-r, H//2-r), (W//2+r, H//2+r)], outline=(255, 240, 200, max(0, 25 - r // 60)), width=1)
    composed = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    drw = ImageDraw.Draw(composed)
    # Channel name header
    text_center(drw, (W // 2, 240), "NARROW HIGHWAY", font(56, bold=True), (201, 180, 138))
    text_center(drw, (W // 2, 320), channel["name"].replace("Narrow Highway · ", ""),
                font(40, italic=True), (255, 240, 200))
    # Main body content per bumper type
    btype = bumper.get("type", "station_id")
    if btype == "station_id":
        text_center(drw, (W // 2, 540), bumper.get("text", channel["name"]),
                    font(64, bold=True), (255, 240, 200))
        if bumper.get("subtitle"):
            text_center(drw, (W // 2, 640), bumper["subtitle"], font(32, italic=True),
                        (201, 180, 138))
    elif btype == "up_next":
        text_center(drw, (W // 2, 480), "UP NEXT", font(48, bold=True), (201, 180, 138))
        text_center(drw, (W // 2, 580), next_title or "More science fiction", font(56, bold=True),
                    (255, 240, 200))
        if next_subtitle:
            text_center(drw, (W // 2, 660), next_subtitle, font(28, italic=True), (201, 180, 138))
    elif btype == "now_playing":
        text_center(drw, (W // 2, 480), "NOW PLAYING", font(48, bold=True), (201, 180, 138))
        text_center(drw, (W // 2, 580), current_title or "Sci-Fi Theatre", font(56, bold=True),
                    (255, 240, 200))
    elif btype == "pastoral":
        text_center(drw, (W // 2, 520), bumper.get("text", ""), font(44, italic=True),
                    (255, 240, 200))
        if bumper.get("subtitle"):
            text_center(drw, (W // 2, 620), bumper["subtitle"], font(28),
                        (201, 180, 138))
    # Footer
    text_center(drw, (W // 2, H - 100), "narrowhighway.com", font(28), (201, 180, 138))
    composed.save(out_png, "PNG", optimize=True)


def render_bumper_mp4(png: Path, duration_sec: int, out_mp4: Path):
    """Encode a still PNG into a duration_sec MP4 with silent audio at 1920x1080 30fps."""
    cmd = [FF, "-y",
           "-loop", "1", "-i", str(png),
           "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
           "-t", str(duration_sec),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
           "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
           "-shortest", "-movflags", "+faststart",
           str(out_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg bumper render failed: {r.stderr[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="path to channel manifest JSON")
    args = ap.parse_args()
    channel = json.loads(Path(args.channel).read_text(encoding="utf-8"))
    out_dir = Path(f"D:/library_files/_channel_bumpers/{channel['channel_id']}")
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Rendering bumpers for: {channel['name']}")
    for bumper in channel.get("bumpers", []):
        bid = bumper["id"]
        dur = bumper.get("duration_sec", 6)
        png = out_dir / f"{bid}.png"
        mp4 = out_dir / f"{bid}.mp4"
        if mp4.exists() and mp4.stat().st_size > 10000:
            print(f"  [SKIP] {bid} exists")
            continue
        render_card_png(bumper, channel, png)
        render_bumper_mp4(png, dur, mp4)
        size_kb = mp4.stat().st_size // 1024
        print(f"  [OK]   {bid:<20} {dur}s  {size_kb} KB  ->  {mp4}")
    print(f"\nDone. Bumpers at {out_dir}")


if __name__ == "__main__":
    main()
