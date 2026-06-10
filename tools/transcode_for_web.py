"""Transcode acquired video files to web-playable MP4 (H.264 + AAC).

Browsers reliably play MP4 (H.264/AAC). They can't reliably demux AVI/MKV/etc.
This tool walks D:/library_files/<slug>/ and produces <basename>.web.mp4
beside each non-MP4 source. The web players prefer .web.mp4 when available.

Uses ffmpeg via imageio-ffmpeg (Python-bundled binary) — no manual install.

Usage:
  python tools/transcode_for_web.py --check
  python tools/transcode_for_web.py --slug tv_beverly_hillbillies_clampetts_strike_oil
  python tools/transcode_for_web.py --category pd_tv          # all video slugs in pd_tv
  python tools/transcode_for_web.py --all-video --limit 20    # batch; cap at 20
  python tools/transcode_for_web.py --dry-run                 # just list what would happen
"""
from __future__ import annotations
import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STORAGE = Path("D:/library_files")
ACQ = REPO / "data" / "library_inventory" / "acquired"

NON_WEB_EXTS = {".avi", ".mkv", ".mpeg", ".mpg", ".mov", ".wmv", ".flv", ".m4v", ".ogv", ".webm"}
ALREADY_WEB_EXT = ".web.mp4"
# Files smaller than this are likely thumbnails/metadata, skip
MIN_BYTES = 1_000_000  # 1 MB


def get_ffmpeg() -> str | None:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg")


def collect_video_files(slug_filter: str | None, category_filter: str | None, limit: int | None) -> list[Path]:
    """Walk acquired manifests, find their on-disk video files that need transcoding."""
    if not ACQ.exists(): return []
    files = []
    for m in sorted(ACQ.glob("*.json")):
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except Exception:
            continue
        slug = data.get("slug")
        cat = data.get("category", "")
        if slug_filter and slug != slug_filter: continue
        if category_filter and cat != category_filter: continue
        for item in data.get("items", []):
            lp = item.get("local_path")
            if not lp: continue
            p = Path(lp)
            if not p.exists(): continue
            if p.suffix.lower() not in NON_WEB_EXTS: continue
            # Skip if already-transcoded sibling exists
            web = p.with_suffix(ALREADY_WEB_EXT)
            if web.exists() and web.stat().st_size > MIN_BYTES: continue
            if p.stat().st_size < MIN_BYTES: continue
            files.append(p)
            if limit and len(files) >= limit: return files
    return files


def transcode(src: Path, ffmpeg: str, crf: int = 23, preset: str = "veryfast") -> bool:
    """ffmpeg-encode to H.264 + AAC mp4 with faststart for streaming."""
    dst = src.with_suffix(ALREADY_WEB_EXT)
    tmp = dst.with_suffix(".tmp.mp4")
    if tmp.exists(): tmp.unlink()
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-pix_fmt", "yuv420p",
        "-max_muxing_queue_size", "9999",
        str(tmp),
    ]
    print(f"[transcode] {src.name} -> {dst.name}")
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=3600)
        if proc.returncode != 0:
            err = proc.stderr.decode("utf-8", errors="replace")[-600:]
            print(f"[ffmpeg err] {err}")
            tmp.unlink(missing_ok=True)
            return False
        # Move tmp -> final
        if dst.exists(): dst.unlink()
        tmp.rename(dst)
        dur = time.time() - t0
        src_mb = src.stat().st_size / 1024 / 1024
        dst_mb = dst.stat().st_size / 1024 / 1024
        print(f"  ok ({dur:.1f}s · {src_mb:.0f} MB -> {dst_mb:.0f} MB)")
        return True
    except Exception as e:
        print(f"[err] {e}")
        tmp.unlink(missing_ok=True)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--slug", help="Single slug")
    ap.add_argument("--category", help="Filter by manifest category")
    ap.add_argument("--all-video", action="store_true", help="All video slugs (pd_tv, vegas, sports, etc.)")
    ap.add_argument("--limit", type=int, help="Cap on number of files")
    ap.add_argument("--crf", type=int, default=23, help="H.264 CRF (lower=higher quality, 23 is default)")
    ap.add_argument("--preset", default="veryfast", help="ffmpeg preset (ultrafast/superfast/veryfast/fast/medium/slow)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ffmpeg = get_ffmpeg()
    if args.check:
        print(f"ffmpeg: {'[OK] ' + ffmpeg if ffmpeg else '[--] NOT installed (pip install imageio-ffmpeg)'}")
        return 0
    if not ffmpeg:
        print("[err] ffmpeg not available; pip install imageio-ffmpeg")
        return 1

    if not (args.slug or args.category or args.all_video):
        ap.print_help()
        return 0

    files = collect_video_files(args.slug, args.category, args.limit)
    if not files:
        print("Nothing to transcode (everything already in MP4 or no matching files).")
        return 0
    print(f"Will transcode {len(files)} file(s):")
    for f in files[:20]:
        print(f"  {f.name}  ({f.stat().st_size//1024//1024} MB)")
    if len(files) > 20:
        print(f"  ... and {len(files)-20} more")

    if args.dry_run:
        return 0

    ok = 0
    for f in files:
        if transcode(f, ffmpeg, crf=args.crf, preset=args.preset):
            ok += 1
    print(f"\nDone. {ok}/{len(files)} successful.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
