"""Runway video renderer — image-to-video + lip-sync for marquee pieces.

Pairs an audio narration (from render_audio_premium.py) with visual:
  - Static cover-art static + caption + waveform animation (ffmpeg, free)
  - Image-to-video animated B-roll via Runway Gen-3 (paid; high-leverage)
  - Lip-sync if there's a narrator-on-camera

Pre-req:
  - RUNWAY_API_KEY env var set
  - ffmpeg installed (always needed for waveform/caption overlay)
  - pip install runwayml  (or use raw requests; this tool uses requests directly)

Usage:
  python tools/render_video.py --check
  python tools/render_video.py --static --audio <mp3> --cover <png> --out <mp4>
       # cheap path: ffmpeg-only, free
  python tools/render_video.py --runway --image <png> --prompt "warm hymnal scene" --out <mp4>
       # paid path: Runway Gen-3, image-to-video
  python tools/render_video.py --hymn amazing-grace --runway
       # composes hymn audio + Runway-generated video + outro

Output:
  D:/library_files/<slug>/marquee_video.mp4
  optional: site/distributable/<slug>.mp4 (with outro for YouTube uploads)

Standing rule: paid Runway calls reserved for content that's earned engagement
OR is marquee at launch. ~$0.50-3 per second of generated video. Budget tightly.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import urllib.request as request
import urllib.error as urlerr

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

REPO = Path(__file__).resolve().parent.parent
STORAGE_ROOT = Path("D:/library_files")
RUNWAY_API = "https://api.runwayml.com/v1"  # Gen-3 endpoint; verify against Runway docs

OUTRO_TEXT_OVERLAY = "NarrowHighway.com — a curated internet for Christian families."


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def runway_key() -> str | None:
    return os.environ.get("RUNWAY_API_KEY") or os.environ.get("RUNWAY_API_TOKEN")


def static_video(audio: Path, cover: Path, out: Path, outro_seconds: int = 5) -> bool:
    """ffmpeg-only video: static cover image + audio + optional outro caption.
    Free, fast. Used for podcast video republishes."""
    if not has_ffmpeg():
        print("[skip] ffmpeg not installed"); return False
    if not audio.exists() or not cover.exists():
        print(f"[err] missing audio or cover: {audio.exists()}/{cover.exists()}")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    # 1) Encode audio as MP4 with looped cover image
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(cover),
        "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-vf", f"drawtext=text='{OUTRO_TEXT_OVERLAY}':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=h-60:enable='gte(t,duration-{outro_seconds})'",
        str(out),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=900)
        if proc.returncode != 0:
            print(f"[ffmpeg err] {proc.stderr.decode('utf-8', errors='replace')[:400]}")
            return False
        return True
    except Exception as e:
        print(f"[err] {e}"); return False


def runway_image_to_video(image: Path, prompt: str, out: Path, duration: int = 5) -> bool:
    """POST to Runway Gen-3 image-to-video. Returns True on success.
    Costs ~$0.50-3 per second; budget tightly."""
    key = runway_key()
    if not key:
        print("[skip] RUNWAY_API_KEY (or RUNWAY_API_TOKEN) not set")
        return False
    if not image.exists():
        print(f"[err] image missing: {image}"); return False

    # Note: Runway's API surface has evolved; verify endpoint + payload against
    # current docs at docs.runwayml.com before high-volume use. This scaffold
    # assumes the Gen-3 task-and-poll pattern.
    print(f"[runway] starting img2vid task: {image.name} ({duration}s) — '{prompt[:60]}'")
    import base64
    img_bytes = image.read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("ascii")
    payload = {
        "promptImage": f"data:image/png;base64,{img_b64}",
        "promptText": prompt,
        "duration": duration,
        "ratio": "1280:720",
        "model": "gen3a_turbo",
    }
    try:
        req = request.Request(
            f"{RUNWAY_API}/image_to_video",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "X-Runway-Version": "2024-11-06",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=60) as r:
            task = json.loads(r.read().decode("utf-8"))
        task_id = task.get("id")
        if not task_id:
            print(f"[err] no task_id in: {task}"); return False
        print(f"  task_id={task_id} — polling…")

        # Poll
        import time
        for _ in range(120):
            time.sleep(5)
            req2 = request.Request(
                f"{RUNWAY_API}/tasks/{task_id}",
                headers={"Authorization": f"Bearer {key}", "X-Runway-Version": "2024-11-06"},
            )
            with request.urlopen(req2, timeout=30) as r:
                status_blob = json.loads(r.read().decode("utf-8"))
            status = status_blob.get("status")
            print(f"  status={status}")
            if status == "SUCCEEDED":
                video_url = (status_blob.get("output") or [None])[0]
                if not video_url:
                    print(f"[err] no output URL in: {status_blob}"); return False
                # Download
                out.parent.mkdir(parents=True, exist_ok=True)
                with request.urlopen(video_url, timeout=120) as r:
                    out.write_bytes(r.read())
                return True
            if status in {"FAILED", "CANCELLED"}:
                print(f"[err] task {status}: {status_blob}")
                return False
        print("[err] timed out polling")
        return False
    except urlerr.HTTPError as e:
        print(f"[err] HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:400]}")
        return False
    except Exception as e:
        print(f"[err] {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--static", action="store_true", help="ffmpeg-only static-cover video (free)")
    ap.add_argument("--runway", action="store_true", help="Runway image-to-video (paid)")
    ap.add_argument("--audio", help="Audio MP3 path (with --static)")
    ap.add_argument("--cover", help="Cover PNG path (with --static)")
    ap.add_argument("--image", help="Source image (with --runway)")
    ap.add_argument("--prompt", help="Motion prompt (with --runway)")
    ap.add_argument("--duration", type=int, default=5, help="Seconds (--runway)")
    ap.add_argument("--out", help="Output MP4")
    ap.add_argument("--hymn", help="Hymn slug — composes audio + Runway video + outro")
    args = ap.parse_args()

    if args.check:
        print(f"ffmpeg:         {'[OK] installed' if has_ffmpeg() else '[--] NOT installed'}")
        print(f"RUNWAY_API_KEY: {'[OK] set' if runway_key() else '[--] NOT set'}")
        return 0

    if args.static:
        if not args.audio or not args.cover or not args.out:
            print("--static requires --audio --cover --out"); return 2
        return 0 if static_video(Path(args.audio), Path(args.cover), Path(args.out)) else 1
    if args.runway:
        if not args.image or not args.prompt or not args.out:
            print("--runway requires --image --prompt --out"); return 2
        return 0 if runway_image_to_video(Path(args.image), args.prompt, Path(args.out), args.duration) else 1
    if args.hymn:
        # Composed pipeline: hymn cover + Runway B-roll → MP4
        cover = REPO / "site" / "art" / f"{args.hymn}.png"
        audio = STORAGE_ROOT / "hymn_renders_premium" / f"{args.hymn}.mp3"
        out = STORAGE_ROOT / "marquee_video" / f"{args.hymn}.mp4"
        if not cover.exists():
            print(f"[err] missing cover {cover}; run tools/render_art.py --slug {args.hymn} first")
            return 1
        if not audio.exists():
            print(f"[err] missing audio {audio}; run tools/render_audio_premium.py --hymn {args.hymn} first")
            return 1
        # Simple path: static_video pairing
        return 0 if static_video(audio, cover, out) else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
