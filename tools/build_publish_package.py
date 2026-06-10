"""Build a one-stop publish package for a pilot.

Generates everything needed to post a pilot across platforms:
  data/publish/<pilot>/
    video.mp4                  -- copy of the final
    audio_podcast.mp3          -- audio-only cut for Apple Podcasts / Spotify
    thumbnail_youtube.png      -- 1920x1080 PNG for YouTube
    pinterest_pin.png          -- 1080x1920 PNG for Pinterest
    title.txt                  -- one-line title (paste into YouTube/etc.)
    description.txt            -- full description (with deep-link to /watch.html)
    tags.txt                   -- comma-separated tags
    instructions.md            -- step-by-step manual upload guide for each platform
"""
from __future__ import annotations
import argparse, shutil
from pathlib import Path
import imageio_ffmpeg, subprocess
from PIL import Image, ImageDraw, ImageFont

FF = imageio_ffmpeg.get_ffmpeg_exe()
REPO = Path(__file__).resolve().parent.parent


def font(size: int, italic: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    cands = []
    if italic and bold:
        cands = ["C:/Windows/Fonts/georgiaz.ttf", "C:/Windows/Fonts/georgiabi.ttf"]
    elif italic:
        cands = ["C:/Windows/Fonts/georgiai.ttf"]
    elif bold:
        cands = ["C:/Windows/Fonts/georgiab.ttf"]
    else:
        cands = ["C:/Windows/Fonts/georgia.ttf"]
    for c in cands:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def extract_audio(video: Path, out: Path):
    cmd = [FF, "-y", "-i", str(video), "-vn", "-c:a", "libmp3lame", "-b:a", "192k",
           "-id3v2_version", "3", str(out)]
    subprocess.run(cmd, capture_output=True, text=True, check=True)


def wrap_to_width(text: str, fnt: ImageFont.FreeTypeFont, max_px: int) -> list[str]:
    """Greedy word-wrap so each line fits within max_px when rendered with fnt."""
    if not text: return []
    words = text.split()
    lines = []
    cur = []
    for w in words:
        trial = " ".join(cur + [w])
        bbox = fnt.getbbox(trial)
        if bbox[2] - bbox[0] <= max_px:
            cur.append(w)
        else:
            if cur:
                lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def make_youtube_thumbnail(hero_frame: Path, title: str, subtitle: str, out: Path):
    base = Image.open(hero_frame).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    drw = ImageDraw.Draw(overlay)
    title_fnt = font(78, bold=True)
    sub_fnt = font(36, italic=True)
    # Wrap title to fit within 1820 px (24 px margin each side)
    lines = wrap_to_width(title, title_fnt, 1820)
    box_top = 1080 - 80 - (len(lines) * 92) - 60 - 30  # subtitle + padding
    drw.rectangle([(0, box_top), (1920, 1080)], fill=(20, 30, 50, 220))
    y = box_top + 30
    for line in lines:
        drw.text((48, y), line, font=title_fnt, fill=(255, 240, 200))
        y += 92
    drw.text((48, y + 10), subtitle, font=sub_fnt, fill=(201, 180, 138))
    composed = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")
    composed.save(out, "PNG", optimize=True)


def make_pinterest_pin(hero_frame: Path, title: str, subtitle: str, out: Path):
    # 1080x1920 vertical pin
    base = Image.open(hero_frame).convert("RGB")
    # Resize hero to fill width, center crop
    base = base.resize((1080, int(base.size[1] * 1080 / base.size[0])), Image.LANCZOS)
    pin = Image.new("RGB", (1080, 1920), (250, 250, 246))
    pin.paste(base, (0, 200))
    drw = ImageDraw.Draw(pin)
    # Top bar — narrowhighway.com
    drw.rectangle([(0, 0), (1080, 200)], fill=(26, 58, 82))
    drw.text((40, 60), "Narrow Highway", font=font(48, bold=True), fill=(255, 240, 200))
    drw.text((40, 130), "Sci-Fi Theatre · Pilot", font=font(28, italic=True), fill=(201, 180, 138))
    # Bottom — title + URL (wrap if needed)
    title_fnt = font(60, bold=True)
    sub_fnt = font(34, italic=True)
    y_bot = 200 + base.size[1] + 60
    lines = wrap_to_width(title, title_fnt, 1000)
    for line in lines:
        drw.text((40, y_bot), line, font=title_fnt, fill=(26, 58, 82))
        y_bot += 72
    drw.text((40, y_bot + 20), subtitle, font=sub_fnt, fill=(108, 90, 58))
    drw.text((40, 1850), "narrowhighway.com", font=font(28), fill=(108, 90, 58))
    pin.save(out, "PNG", optimize=True)


def build(pilot: str, video_path: Path, hero_frame: Path,
          title: str, subtitle: str, description: str, tags: list[str]):
    out = REPO / "data" / "publish" / pilot
    out.mkdir(parents=True, exist_ok=True)
    print(f"=== Publish package: {pilot} ===")
    print(f"Output dir: {out}")
    # Copy video
    video_dest = out / "video.mp4"
    if not video_dest.exists() or video_dest.stat().st_size != video_path.stat().st_size:
        shutil.copy2(video_path, video_dest)
        print(f"  copied video: {video_dest.stat().st_size // 1024 // 1024} MB")
    # Audio extract
    audio_dest = out / "audio_podcast.mp3"
    if not audio_dest.exists():
        extract_audio(video_path, audio_dest)
        print(f"  extracted audio: {audio_dest.stat().st_size // 1024} KB")
    # YouTube thumbnail
    thumb_dest = out / "thumbnail_youtube.png"
    make_youtube_thumbnail(hero_frame, title, subtitle, thumb_dest)
    print(f"  YouTube thumbnail: {thumb_dest.stat().st_size // 1024} KB")
    # Pinterest pin
    pin_dest = out / "pinterest_pin.png"
    make_pinterest_pin(hero_frame, title, subtitle, pin_dest)
    print(f"  Pinterest pin: {pin_dest.stat().st_size // 1024} KB")
    # Text assets
    (out / "title.txt").write_text(title, encoding="utf-8")
    (out / "description.txt").write_text(description, encoding="utf-8")
    (out / "tags.txt").write_text(", ".join(tags), encoding="utf-8")
    # Instructions
    instructions = f"""# Publish checklist — {title}

## YouTube (~5 min)
1. Open https://studio.youtube.com → Create → Upload videos
2. Drag `video.mp4` (from this folder) into the uploader
3. Fields:
   - Title: paste from `title.txt`
   - Description: paste from `description.txt`
   - Thumbnail: upload `thumbnail_youtube.png`
   - Tags: paste from `tags.txt`
   - Audience: NOT made for kids (let kids decide — content is family-safe regardless)
   - Visibility: Public
4. After upload, copy the YouTube video URL and tell Claude — it'll embed it on the homepage.

## Apple Podcasts (audio-only)
The audio is `audio_podcast.mp3`. The site already has /podcast.rss — Claude will add this episode automatically when it sees the publish package. If you want it on Apple Podcasts as a standalone, the existing RSS feed (already submitted) handles it.

## Spotify
Same audio. If your Spotify for Creators submission is approved, the RSS feed pulls it in automatically.

## Pinterest (~2 min)
1. Open https://pinterest.com → Create Pin
2. Upload `pinterest_pin.png`
3. Title: {title}
4. Description: short version of `description.txt` (under 500 chars)
5. Link: https://narrowhighway.com/watch.html
6. Board: Sci-Fi Theatre (create if doesn't exist)

## Twitter/X, Threads, Bluesky
Compose: First 240 chars of `description.txt` + YouTube link.

## Internet Archive (optional, free)
1. https://archive.org/create → Upload to community videos
2. Title + description + tags from text files
3. Adds permanent free hosting + searchable backup.
"""
    (out / "instructions.md").write_text(instructions, encoding="utf-8")
    print(f"  instructions: {out / 'instructions.md'}")
    print()
    print("READY TO PUBLISH:")
    print(f"  Open the folder: {out}")
    print(f"  Then follow instructions.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True, help="e.g. soft_rains_v4")
    args = ap.parse_args()

    if args.pilot == "soft_rains_v4":
        build(
            pilot="soft_rains_v4",
            video_path=Path("D:/library_files/_pilots/soft_rains_v4/final.mp4"),
            hero_frame=Path("D:/library_files/_hero_frames/scifi_softrains_14_falling_oak.png"),
            title="There Will Come Soft Rains — Bradbury, Animated (1956 X Minus One)",
            subtitle="Ray Bradbury · Sci-Fi Theatre Pilot",
            description=(
                "There Will Come Soft Rains — Ray Bradbury's 1950 short story, broadcast on NBC's X Minus One in 1956, "
                "now rendered with new eyes for you. The audio is the original 1956 NBC broadcast. The visuals are 1950s-pulp-magazine-illustration "
                "animation rendered by AI in the Hanna-Barbera limited-animation tradition.\n\n"
                "This is the pilot episode of Sci-Fi Theatre — a series adapting public-domain golden-age sci-fi radio drama (Dimension X, X Minus One, "
                "Mercury Theatre) into illustrated short films, with a pastoral observation at the close of each episode.\n\n"
                "From narrowhighway.com — a curated internet for Christian families. The good ole days in a box.\n\n"
                "Original story: Ray Bradbury, 1950 (Collier's). Original broadcast: NBC X Minus One, December 5, 1956. "
                "Audio is public domain by non-renewal. New illustration: 2026.\n\n"
                "Pastoral observation by M.R. Harris: \"Bradbury wrote this story in 1950, five years after Hiroshima. Sara Teasdale wrote her poem in 1918, "
                "six months before she died. She was right about the trees and the birds. They do not need us. But she was wrong about one thing. There is One who hung the trees, "
                "and He weeps when His children are gone. He sent His Son into the burning house, that not one of us should be left behind.\"\n\n"
                "→ More episodes at https://narrowhighway.com/watch.html\n"
                "→ Substrate / source at https://narrowhighway.com/canon.html\n"
                "→ Pitch a show you'd like adapted: https://narrowhighway.com/pitch.html"
            ),
            tags=[
                "Ray Bradbury", "There Will Come Soft Rains", "X Minus One", "Dimension X",
                "old time radio", "OTR", "animated sci-fi", "public domain sci-fi",
                "classic science fiction", "1950s sci-fi", "post-apocalyptic",
                "Christian family content", "AI animation", "limited animation",
                "Hanna-Barbera style", "Sara Teasdale", "Soft Rains",
                "narrow highway", "good ole days",
            ],
        )
    elif args.pilot == "hundred_acre":
        build(
            pilot="hundred_acre",
            video_path=Path("D:/library_files/_pilots/hundred_acre/final.mp4"),
            hero_frame=Path("D:/library_files/_hero_frames/pooh_02_treetop_bee.png"),
            title="In Which We Are Introduced to Winnie-the-Pooh — Milne 1926",
            subtitle="A.A. Milne · Hundred Acre Theatre Pilot",
            description=(
                "Winnie-the-Pooh Chapter 1 — A.A. Milne's 1926 original, illustrated as Mr. Shepard first drew it, "
                "one hundred years ago. Pilot of Hundred Acre Theatre — a series dramatizing the original Milne stories "
                "for families.\n\n"
                "From narrowhighway.com — a curated internet for Christian families.\n\n"
                "Original text: A.A. Milne, 1926. Public domain as of January 1, 2022 (US). Original illustrations: E.H. Shepard. "
                "Audio: LibriVox volunteer reading (CC0). New illustration: 2026.\n\n"
                "Pastoral observation: \"There is a kind of love that does not need its object to be clever, or useful, or even sensible. "
                "A small boy can love a foolish bear. There is one Father who loves us like that, while we are yet foolish — and while we are yet covered in mud. "
                "He sent His Son to lower us from the balloon.\"\n\n"
                "→ More episodes at https://narrowhighway.com/watch.html\n"
                "→ Kids deck: https://narrowhighway.com/kids.html\n"
                "→ Pitch a show: https://narrowhighway.com/pitch.html"
            ),
            tags=[
                "Winnie the Pooh", "A.A. Milne", "Milne 1926", "Hundred Acre Wood",
                "children's audiobook", "Christopher Robin", "E.H. Shepard",
                "Christian children", "Christian family", "public domain", "PD 2022",
                "classic children's stories", "animated Pooh", "AI animation",
                "narrow highway", "good ole days",
            ],
        )
    else:
        print(f"Unknown pilot: {args.pilot}")
