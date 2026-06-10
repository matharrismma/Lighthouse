"""Build a concat-demuxer list of every MP4 already encoded into the channel
caches, so the FAST channel can stream NOW from what exists — no waiting for
the whole library, no multi-GB HLS day baked to disk.

Items are round-robined across the channel caches so the stream alternates
kinds (a devotional, then a cartoon, then a radio play...) instead of playing
137 sermons back to back. Half-written / unreadable files are probed out.

Durations are cached in .probe_cache.json keyed by size+mtime, so re-runs stay
fast even once the cache holds thousands of items — only new/changed files are
re-probed. That keeps the scheduled refresh (local/refresh_channel.ps1) cheap.

  python tools/fast_channel_cache_concat.py

Writes data/channels/narrow-highway/cache_concat.txt. Re-run whenever the
encoder has added more, then restart the push:

  python tools/fast_channel_youtube_live.py --channel narrow-highway \
      --concat data/channels/narrow-highway/cache_concat.txt --supervise
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path
import imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
CACHE_ROOT = Path("D:/library_files/_channel_cache")
OUT = REPO / "data" / "channels" / "narrow-highway" / "cache_concat.txt"
PROBE_CACHE = REPO / "data" / "channels" / "narrow-highway" / ".probe_cache.json"


def _load_probe_cache() -> dict:
    try:
        return json.loads(PROBE_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _probe(path: Path) -> float:
    """Probe duration in seconds. 0.0 if the file can't be read (corrupt, or
    still being written by the encoder right now)."""
    try:
        r = subprocess.run([FF, "-hide_banner", "-i", str(path)],
                           capture_output=True, text=True, timeout=40)
    except Exception:
        return 0.0
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def main() -> None:
    if not CACHE_ROOT.is_dir():
        print(f"[FATAL] No cache root at {CACHE_ROOT}")
        sys.exit(1)

    probe_cache = _load_probe_cache()
    new_cache: dict[str, dict] = {}
    probed = reused = 0

    per_channel: dict[str, list[Path]] = {}
    total = 0.0
    for chdir in sorted(CACHE_ROOT.iterdir()):
        if not chdir.is_dir() or chdir.name.startswith("."):
            continue
        good: list[Path] = []
        ch_secs = 0.0
        for f in sorted(chdir.glob("*.mp4")):
            try:
                st = f.stat()
            except OSError:
                continue
            if st.st_size < 50_000:
                continue
            key = str(f)
            sig = f"{st.st_size}:{int(st.st_mtime)}"
            hit = probe_cache.get(key)
            if hit and hit.get("sig") == sig:
                d = float(hit.get("dur", 0.0))
                reused += 1
            else:
                d = _probe(f)
                probed += 1
            new_cache[key] = {"sig": sig, "dur": d}
            if d < 1.0:
                print(f"  skip (unreadable/incomplete): {f.name}")
                continue
            good.append(f)
            ch_secs += d
        if good:
            per_channel[chdir.name] = good
            total += ch_secs
            print(f"  {chdir.name}: {len(good)} items, {ch_secs / 3600:.1f}h")

    if not per_channel:
        print("[FATAL] No encoded MP4s found — nothing to stream yet.")
        sys.exit(1)

    # round-robin interleave across channels
    queues = {k: list(v) for k, v in per_channel.items()}
    order: list[Path] = []
    while any(queues.values()):
        for k in list(queues):
            if queues[k]:
                order.append(queues[k].pop(0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for f in order:
            p = str(f).replace("\\", "/").replace("'", "'\\''")
            fh.write(f"file '{p}'\n")
    try:
        PROBE_CACHE.write_text(json.dumps(new_cache), encoding="utf-8")
    except Exception:
        pass

    print(f"\nWROTE {OUT}")
    print(f"  {len(order)} items - {total / 3600:.2f}h of content (the push loops it)")
    print(f"  ({reused} durations reused from cache, {probed} freshly probed)")


if __name__ == "__main__":
    main()
