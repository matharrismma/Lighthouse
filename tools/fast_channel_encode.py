"""Pre-encode every source asset referenced by a channel manifest to a uniform HLS-ready MP4.

FAST channels need consistent codecs/resolution/audio to concat cleanly into HLS segments.
Audio dramas are MP3 (no video); we render them with a still card overlay so they play as video.
Animated pilots are already MP4 but may have varied keyframe spacing — re-encode for 2s GOP.

Cache: D:/library_files/_channel_cache/<channel_id>/<id>.mp4
Idempotent — skips items whose cache already exists with non-zero size.

Output spec (HLS-friendly):
  video: H.264 high@4.0, 1920x1080, 30fps, 2s GOP (keyframe every 60 frames), CRF 22
  audio: AAC-LC, 128k, 44100Hz, stereo
  container: MP4 with +faststart, BUT we also emit raw .ts ready for HLS

This script just produces the uniform MP4. The HLS segmenter consumes these.
"""
from __future__ import annotations
import argparse, json, os, sys, time, atexit
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import subprocess, imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
W, H, FPS = 1920, 1080, 30

# ── Encoder guard ───────────────────────────────────────────────────────
# Running two encoders at once once OOM-ed the box (8 GB) and took the
# whole site down. This is a hard rule now: ONE encoder at a time, and it
# runs at BelowNormal priority so the engine always wins CPU.
_LOCK_PATH = Path("D:/library_files/_channel_cache/.encode.lock")


def _pid_alive(pid: int) -> bool:
    """True if a process with this PID is running. Windows-safe — never
    sends a signal (os.kill on Windows would *terminate* the process)."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k = ctypes.windll.kernel32
        h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            ok = k.GetExitCodeProcess(h, ctypes.byref(code))
            return bool(ok) and code.value == STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _release_encoder_lock() -> None:
    try:
        if _LOCK_PATH.exists():
            owner = int(_LOCK_PATH.read_text(encoding="utf-8").strip().split()[0])
            if owner == os.getpid():
                _LOCK_PATH.unlink()
    except Exception:
        pass


def _acquire_encoder_lock() -> bool:
    """Refuse to start if another encoder is already running. Returns True
    if this process may proceed."""
    try:
        _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        if _LOCK_PATH.exists():
            try:
                other = int(_LOCK_PATH.read_text(encoding="utf-8").strip().split()[0])
            except Exception:
                other = -1
            if other > 0 and other != os.getpid() and _pid_alive(other):
                print(f"REFUSING TO START — another encoder is already running (PID {other}).")
                print(f"One encoder at a time: two at once OOM-ed the box before.")
                print(f"If you are certain it is dead, delete the lock and retry:")
                print(f"  {_LOCK_PATH}")
                return False
            # stale lock — the previous encoder exited without cleanup
        _LOCK_PATH.write_text(f"{os.getpid()} {int(time.time())}\n", encoding="utf-8")
        atexit.register(_release_encoder_lock)
        return True
    except Exception as e:
        # The guard must never block a legitimate run on its own bug.
        print(f"(encoder-lock check skipped: {e})")
        return True


def _set_below_normal_priority() -> None:
    """Run gently — the engine must always win CPU. ffmpeg children spawned
    via subprocess inherit this priority class."""
    try:
        if sys.platform == "win32":
            import ctypes
            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            ctypes.windll.kernel32.SetPriorityClass(
                ctypes.windll.kernel32.GetCurrentProcess(),
                BELOW_NORMAL_PRIORITY_CLASS)
        else:
            os.nice(10)
    except Exception:
        pass


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


def render_still_card(channel: dict, item: dict, out_png: Path):
    """Render a still card used as the video layer for audio-only items."""
    primary = channel.get("color_primary", "#1B4D8C")
    bg = Image.new("RGB", (W, H), color=primary)
    drw = ImageDraw.Draw(bg)
    # Subtle radial pattern
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ovd = ImageDraw.Draw(overlay)
    for r in range(0, max(W, H), 50):
        ovd.ellipse(
            [(W // 2 - r, H // 2 - r), (W // 2 + r, H // 2 + r)],
            outline=(255, 240, 200, max(0, 22 - r // 60)),
            width=1,
        )
    composed = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")
    drw = ImageDraw.Draw(composed)

    # Channel chrome
    _center(drw, (W // 2, 200), "NARROW HIGHWAY", font(48, bold=True), (201, 180, 138))
    _center(
        drw,
        (W // 2, 270),
        channel["name"].replace("Narrow Highway · ", ""),
        font(34, italic=True),
        (255, 240, 200),
    )

    # Episode title (may wrap)
    title = item["title"]
    f_title = font(72, bold=True)
    _multiline_center(drw, (W // 2, 520), title, f_title, (255, 240, 200), max_width=1500)

    # "Audio Drama" tag if no video
    if not item.get("video"):
        _center(drw, (W // 2, 760), "AUDIO DRAMA", font(28, bold=True), (201, 180, 138))

    # Footer
    _center(drw, (W // 2, H - 80), "narrowhighway.com", font(24), (201, 180, 138))
    composed.save(out_png, "PNG", optimize=True)


def _center(drw, xy, text, fnt, fill):
    bbox = drw.textbbox((0, 0), text, font=fnt)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    drw.text((xy[0] - w // 2, xy[1] - h // 2), text, font=fnt, fill=fill)


def _multiline_center(drw, xy, text, fnt, fill, max_width):
    words = text.split()
    lines, cur = [], ""
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
    lh = (bbox_h[3] - bbox_h[1]) + 18
    total = lh * len(lines)
    y = xy[1] - total // 2
    for ln in lines:
        bbox = drw.textbbox((0, 0), ln, font=fnt)
        w = bbox[2] - bbox[0]
        drw.text((xy[0] - w // 2, y), ln, font=fnt, fill=fill)
        y += lh


def probe_video(src: Path) -> dict:
    """Probe basic stream params. Returns dict with width, height, fps, vcodec, acodec, achannels, asr."""
    r = subprocess.run([FF, "-hide_banner", "-i", str(src)], capture_output=True, text=True)
    info = {}
    import re
    for line in r.stderr.splitlines():
        if "Video:" in line:
            m = re.search(r"Video: (\w+).*?(\d+)x(\d+).*?(\d+(?:\.\d+)?) fps", line)
            if m:
                info["vcodec"] = m.group(1)
                info["w"] = int(m.group(2))
                info["h"] = int(m.group(3))
                info["fps"] = float(m.group(4))
        if "Audio:" in line:
            m = re.search(r"Audio: (\w+).*?(\d+) Hz, (\w+)", line)
            if m:
                info["acodec"] = m.group(1)
                info["asr"] = int(m.group(2))
                info["alayout"] = m.group(3)
    return info


def is_uniform(info: dict) -> bool:
    """True if probed video already matches our target spec exactly."""
    return (
        info.get("vcodec") == "h264"
        and info.get("w") == W
        and info.get("h") == H
        and abs(info.get("fps", 0) - FPS) < 0.5
        and info.get("acodec") == "aac"
        and info.get("asr") == 44100
        and info.get("alayout") == "stereo"
    )


def encode_video_uniform(src: Path, out: Path):
    """Re-encode existing video to uniform HLS-friendly specs.
    If src already matches target spec, stream-copy (dramatically faster).
    """
    info = probe_video(src)
    if is_uniform(info):
        # Stream-copy with keyframe alignment re-imposed via -force_key_frames
        # Actually, stream-copy preserves existing keyframes; if those aren't 2s-aligned
        # the HLS muxer may need to re-encode anyway. Try stream-copy first.
        cmd = [
            FF, "-y", "-i", str(src),
            "-c", "copy",
            "-movflags", "+faststart",
            str(out),
        ]
    else:
        cmd = [
            FF, "-y", "-i", str(src),
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,fps={FPS}",
            "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
            "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p",
            "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(out),
        ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg video re-encode failed for {src.name}: {r.stderr[-800:]}")


def encode_audio_with_still(src_audio: Path, png: Path, out: Path):
    """Combine still PNG + audio into uniform HLS-friendly MP4.

    Approach: read the still at 1 fps (one unique frame per second), then
    output at 30 fps via -r so x264 only encodes ~1 unique frame per second
    rather than 30 duplicates. This brings encode time from ~realtime to
    ~5-10% of realtime.

    We force High profile + 2s keyframe spacing so the cache MP4 concats
    cleanly with the bumpers (also High profile) in the HLS muxer.
    """
    cmd = [
        FF, "-y",
        "-loop", "1", "-framerate", "1", "-i", str(png),
        "-i", str(src_audio),
        "-c:v", "libx264", "-profile:v", "high", "-level", "4.0",
        "-preset", "superfast",
        "-crf", "30", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        # Keyframe every 2s @ 30fps output
        "-g", str(FPS * 2), "-keyint_min", str(FPS * 2), "-sc_threshold", "0",
        "-b:v", "300k", "-maxrate", "400k", "-bufsize", "800k",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        "-shortest", "-movflags", "+faststart",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg audio+still failed for {src_audio.name}: {r.stderr[-800:]}")


def encode_bumpers_uniform(channel: dict, cache_dir: Path):
    """Re-encode bumpers to the same uniform spec so concat is clean."""
    bumper_src_dir = Path(f"D:/library_files/_channel_bumpers/{channel['channel_id']}")
    for b in channel.get("bumpers", []):
        bid = b["id"]
        src = bumper_src_dir / f"{bid}.mp4"
        if not src.exists():
            print(f"  [SKIP bumper missing] {bid}")
            continue
        out = cache_dir / f"bumper_{bid}.mp4"
        if out.exists() and out.stat().st_size > 10000:
            continue
        print(f"  [BUMPER] {bid} -> {out.name}")
        encode_video_uniform(src, out)


def iter_content_pool(pool: dict):
    for category, items in pool.items():
        for it in items:
            yield category, it


def _encode_one(channel, item, cache_dir):
    """Worker function: encode a single item. Returns (id, status, msg)."""
    iid = item["id"]
    out = cache_dir / f"{iid}.mp4"
    if out.exists() and out.stat().st_size > 50000:
        return (iid, "SKIP", "cached")
    video = item.get("video")
    audio = item.get("audio")
    try:
        if video and Path(video).exists():
            encode_video_uniform(Path(video), out)
            kind = "VIDEO"
        elif audio and Path(audio).exists():
            png = cache_dir / f"{iid}.png"
            render_still_card(channel, item, png)
            encode_audio_with_still(Path(audio), png, out)
            kind = "AUDIO"
        else:
            return (iid, "MISSING", "no source")
        size_mb = out.stat().st_size // (1024 * 1024)
        return (iid, "OK", f"{kind} {size_mb}MB")
    except Exception as e:
        return (iid, "ERROR", str(e)[:200])


def main():
    import concurrent.futures as cf
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--limit", type=int, default=None, help="Cap items processed (for testing)")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel encode workers (default 1; try 2-3 for multi-core)")
    args = ap.parse_args()

    # One encoder at a time, and run it gently. This is the hard rule that
    # prevents the duplicate-encoder OOM that crashed the box.
    _set_below_normal_priority()
    if not _acquire_encoder_lock():
        sys.exit(1)
    if args.workers > 2:
        print(f"  WARNING: {args.workers} workers is heavy for a small box — "
              f"encoding belongs on the workshop machine, not the engine host.")

    channel = json.loads(Path(args.channel).read_text(encoding="utf-8"))
    ch_id = channel["channel_id"]
    cache_dir = Path(f"D:/library_files/_channel_cache/{ch_id}")
    cache_dir.mkdir(parents=True, exist_ok=True)

    print(f"Uniform-encoding channel: {channel['name']}")
    print(f"  Cache dir: {cache_dir}")
    print(f"  Workers:   {args.workers}")

    # Bumpers first (always serial — they're tiny)
    print("\nBumpers:")
    encode_bumpers_uniform(channel, cache_dir)

    # Content pool
    print("\nContent pool:")
    items = []
    n_seen = 0
    for category, item in iter_content_pool(channel["content_pool"]):
        if args.limit is not None and n_seen >= args.limit:
            break
        items.append(item)
        n_seen += 1

    if args.workers <= 1:
        # Serial path — keeps log output orderly
        for item in items:
            iid, status, msg = _encode_one(channel, item, cache_dir)
            print(f"  [{status}] {iid:40} {msg}")
    else:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            futures = {ex.submit(_encode_one, channel, it, cache_dir): it for it in items}
            for fut in cf.as_completed(futures):
                iid, status, msg = fut.result()
                print(f"  [{status}] {iid:40} {msg}", flush=True)

    print(f"\nDone. {len(items)} items processed. Cache at {cache_dir}")


if __name__ == "__main__":
    main()
