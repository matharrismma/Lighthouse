"""Render each hymn in site/hymns.json as a 1080p video for the Hymns 24/7 channel.

Per hymn:
  1. Render lyric cards (PNG per verse) — verse text centered, title at top,
     scripture refs in footer, subtle radial vignette.
  2. Use Piper TTS to read the verses aloud (en_US-lessac-medium).
  3. Concat: 4s title card → [verse audio + matching card] per verse → 4s outro
     with scripture references.
  4. Output 1920x1080 H.264 + AAC stereo MP4.

Output: D:/library_files/_channel_cache/nh-hymns-247/<slug>.mp4
        (the uniform-channel-cache path, ready to ingest into the channel scheduler)

Idempotent: skips slugs whose cached MP4 already exists with non-zero size.

Requires:
  - Piper at C:/Tools/piper/piper.exe with en_US-lessac-medium.onnx
  - ffmpeg via imageio_ffmpeg
"""
from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
PIPER_EXE = Path("C:/Tools/piper/piper.exe")
PIPER_VOICE = Path("C:/Tools/piper/voices/en_US-lessac-medium.onnx")
W, H, FPS = 1920, 1080, 30


def font(size: int, bold=False, italic=False):
    if bold and italic:
        cand = "C:/Windows/Fonts/georgiaz.ttf"
    elif bold:
        cand = "C:/Windows/Fonts/georgiab.ttf"
    elif italic:
        cand = "C:/Windows/Fonts/georgiai.ttf"
    else:
        cand = "C:/Windows/Fonts/georgia.ttf"
    return ImageFont.truetype(cand, size) if Path(cand).exists() else ImageFont.load_default()


def _multiline_center(drw, xy, text, fnt, fill, max_width):
    lines = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            lines.append("")
            continue
        words = paragraph.split()
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            bbox = drw.textbbox((0, 0), trial, font=fnt)
            if bbox[2] - bbox[0] > max_width and cur:
                lines.append(cur)
                cur = w
            else:
                cur = trial
        if cur:
            lines.append(cur)
    bbox_h = drw.textbbox((0, 0), "Mg", font=fnt)
    lh = (bbox_h[3] - bbox_h[1]) + 12
    total = lh * len(lines)
    y = xy[1] - total // 2
    for ln in lines:
        bbox = drw.textbbox((0, 0), ln, font=fnt)
        w = bbox[2] - bbox[0]
        drw.text((xy[0] - w // 2, y), ln, font=fnt, fill=fill)
        y += lh


def _center(drw, xy, text, fnt, fill):
    bbox = drw.textbbox((0, 0), text, font=fnt)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    drw.text((xy[0] - w // 2, xy[1] - h // 2), text, font=fnt, fill=fill)


def render_title_card(hymn: dict, out_png: Path):
    bg = Image.new("RGB", (W, H), color="#3a5530")
    drw = ImageDraw.Draw(bg)
    # subtle pattern
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(overlay)
    for r in range(0, max(W, H), 50):
        ovd.ellipse([(W//2-r, H//2-r), (W//2+r, H//2+r)],
                    outline=(255, 240, 200, max(0, 25 - r // 60)), width=1)
    composed = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    drw = ImageDraw.Draw(composed)
    _center(drw, (W // 2, 200), "NARROW HIGHWAY", font(48, bold=True), (201, 180, 138))
    _center(drw, (W // 2, 270), "Hymns 24/7", font(36, italic=True), (255, 240, 200))
    _multiline_center(drw, (W // 2, 520), hymn["title"], font(72, bold=True),
                      (255, 240, 200), max_width=1500)
    _center(drw, (W // 2, 720), f"{hymn['author']} · {hymn['year']}",
            font(32, italic=True), (201, 180, 138))
    _center(drw, (W // 2, H - 80), "narrowhighway.com", font(24), (201, 180, 138))
    composed.save(out_png, "PNG", optimize=True)


def render_verse_card(hymn: dict, verse_text: str, verse_num: int,
                      total_verses: int, out_png: Path):
    bg = Image.new("RGB", (W, H), color="#3a5530")
    drw = ImageDraw.Draw(bg)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(overlay)
    for r in range(0, max(W, H), 50):
        ovd.ellipse([(W//2-r, H//2-r), (W//2+r, H//2+r)],
                    outline=(255, 240, 200, max(0, 20 - r // 70)), width=1)
    composed = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    drw = ImageDraw.Draw(composed)
    _center(drw, (W // 2, 90), hymn["title"], font(34, bold=True), (201, 180, 138))
    _center(drw, (W // 2, 140), f"Verse {verse_num} of {total_verses}",
            font(20, italic=True), (180, 165, 130))
    _multiline_center(drw, (W // 2, H // 2 + 30), verse_text, font(44),
                      (255, 240, 200), max_width=1500)
    _center(drw, (W // 2, H - 80), "narrowhighway.com · Hymns 24/7",
            font(22), (201, 180, 138))
    composed.save(out_png, "PNG", optimize=True)


def render_scripture_card(hymn: dict, out_png: Path):
    bg = Image.new("RGB", (W, H), color="#3a5530")
    drw = ImageDraw.Draw(bg)
    composed = bg.convert("RGB")
    drw = ImageDraw.Draw(composed)
    _center(drw, (W // 2, 200), "Scripture", font(36, italic=True), (201, 180, 138))
    refs = " · ".join(hymn.get("scripture", []))
    _multiline_center(drw, (W // 2, H // 2), refs, font(56, bold=True),
                      (255, 240, 200), max_width=1500)
    _center(drw, (W // 2, H - 200), f"Hymn: {hymn['title']}",
            font(30, italic=True), (201, 180, 138))
    _center(drw, (W // 2, H - 80), "narrowhighway.com", font(24), (201, 180, 138))
    composed.save(out_png, "PNG", optimize=True)


def piper_synth(text: str, out_wav: Path) -> bool:
    """Synthesize text -> WAV with Piper. Returns True on success."""
    if not PIPER_EXE.exists() or not PIPER_VOICE.exists():
        return False
    try:
        proc = subprocess.run(
            [str(PIPER_EXE), "--model", str(PIPER_VOICE),
             "--output_file", str(out_wav)],
            input=text, capture_output=True, text=True, timeout=120,
            encoding="utf-8",
        )
        return proc.returncode == 0 and out_wav.exists() and out_wav.stat().st_size > 1000
    except Exception as e:
        print(f"  [piper error] {e}")
        return False


def encode_segment(png: Path, audio_wav: Path | None, duration_sec: float,
                   out_mp4: Path, fps: int = FPS):
    """Encode a still+audio (or still+silence) segment."""
    if audio_wav and audio_wav.exists():
        cmd = [
            FF, "-y",
            "-loop", "1", "-framerate", str(fps), "-i", str(png),
            "-i", str(audio_wav),
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
            "-preset", "superfast",
            "-crf", "30", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-g", str(fps * 2), "-keyint_min", str(fps * 2), "-sc_threshold", "0",
            "-b:v", "300k",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(out_mp4),
        ]
    else:
        cmd = [
            FF, "-y",
            "-loop", "1", "-framerate", str(fps), "-i", str(png),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration_sec),
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
            "-preset", "superfast",
            "-crf", "30", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-g", str(fps * 2), "-keyint_min", str(fps * 2), "-sc_threshold", "0",
            "-b:v", "300k",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-shortest", "-movflags", "+faststart",
            str(out_mp4),
        ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg segment encode failed: {r.stderr[-600:]}")


def concat_mp4s(segments: list[Path], out_mp4: Path):
    """Concat a list of uniform MP4s via ffmpeg concat demuxer."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        for s in segments:
            p = str(s).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{p}'\n")
        listf = f.name
    cmd = [FF, "-y", "-f", "concat", "-safe", "0", "-i", listf,
           "-c", "copy", "-movflags", "+faststart", str(out_mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    Path(listf).unlink(missing_ok=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {r.stderr[-600:]}")


def render_one_hymn(hymn: dict, out_dir: Path, work_dir: Path) -> Path:
    slug = hymn["slug"]
    out = out_dir / f"hymn_{slug}.mp4"
    if out.exists() and out.stat().st_size > 50000:
        print(f"  [SKIP cached] {slug}")
        return out

    work = work_dir / slug
    work.mkdir(parents=True, exist_ok=True)

    # Split text into verses (paragraphs separated by blank lines)
    raw = hymn["text"]
    verses = [v.strip() for v in raw.split("\n\n") if v.strip()]
    if not verses:
        verses = [raw]

    segments = []

    # 1. Title card (5s)
    title_png = work / "title.png"
    title_seg = work / "title.mp4"
    render_title_card(hymn, title_png)
    encode_segment(title_png, None, 5.0, title_seg)
    segments.append(title_seg)

    # 2. Verse cards with Piper narration
    for i, vt in enumerate(verses, start=1):
        png = work / f"verse_{i}.png"
        wav = work / f"verse_{i}.wav"
        seg = work / f"verse_{i}.mp4"
        render_verse_card(hymn, vt, i, len(verses), png)
        spoken = piper_synth(vt + "\n\n", wav)
        if spoken:
            encode_segment(png, wav, 0.0, seg)
        else:
            # Fall back to silent verse display, 12 seconds per verse
            encode_segment(png, None, 12.0, seg)
        segments.append(seg)

    # 3. Scripture closing card (6s)
    scrip_png = work / "scripture.png"
    scrip_seg = work / "scripture.mp4"
    render_scripture_card(hymn, scrip_png)
    encode_segment(scrip_png, None, 6.0, scrip_seg)
    segments.append(scrip_seg)

    # 4. Concat
    concat_mp4s(segments, out)

    # Cleanup work dir
    for s in segments:
        try: s.unlink()
        except: pass
    for p in work.glob("*"):
        try: p.unlink()
        except: pass
    try: work.rmdir()
    except: pass

    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hymns-json", default=str(REPO / "site" / "hymns.json"))
    ap.add_argument("--channel-id", default="nh-hymns-247")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    data = json.loads(Path(args.hymns_json).read_text(encoding="utf-8"))
    out_dir = Path(f"D:/library_files/_channel_cache/{args.channel_id}")
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = Path("D:/library_files/_hymn_work")
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"Rendering {data['total']} hymns to {out_dir}")
    n = 0
    for hymn in data["hymns"]:
        if args.limit and n >= args.limit:
            break
        try:
            out = render_one_hymn(hymn, out_dir, work_dir)
            print(f"  [OK] {hymn['slug']}  ->  {out.stat().st_size // 1024} KB")
        except Exception as e:
            print(f"  [ERR] {hymn['slug']}: {e}")
        n += 1
    print(f"\nDone. {n} hymns processed.")


if __name__ == "__main__":
    main()
