"""duration_cache.py — Cache ffmpeg duration probes so daily schedule rebuilds
are seconds instead of minutes.

Without a cache, tools/fast_channel_schedule.py runs ffmpeg on every pool item
(3k+ items, ~50-100ms each = 5-15 minutes of probing per daily rebuild). With
this cache, the second run reuses the durations.

Cache shape (data/channels/durations.json):
  {
    "items": {
      "<sha256-of-absolute-path>": {
        "path": "<absolute path>",
        "size_bytes": 123456789,
        "mtime": 1779271234.5,
        "duration_sec": 540.123,
        "probed_at": "ISO timestamp"
      }, ...
    }
  }

Invalidation: an entry is reused only if (path, size, mtime) all match.
That catches file replacements and re-encodes.

Run:
  python tools/duration_cache.py --warm                 # probe every pool item once
  python tools/duration_cache.py --warm --channel-manifest content/channels/narrow_highway.json
  python tools/duration_cache.py --status               # show cache hit-rate / coverage
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
import imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
CACHE_DIR = REPO / "data" / "channels"
CACHE_PATH = CACHE_DIR / "durations.json"


def _key(p: Path) -> str:
    return hashlib.sha256(str(p.resolve()).encode("utf-8")).hexdigest()[:16]


def load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"items": {}}
    return {"items": {}}


def save_cache(c: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(c, indent=2), encoding="utf-8")


def probe_duration(p: Path) -> float:
    """Run ffmpeg to read Duration: from the file. Single subprocess; ~50-100ms.

    Captures stderr as raw bytes and decodes with errors='replace' — Windows
    cp1252 codec will choke on any filename byte > 0x7F, so we go around it."""
    if not p.exists():
        return 0.0
    try:
        r = subprocess.run([FF, "-hide_banner", "-i", str(p)],
                           capture_output=True, text=False)
    except Exception:
        return 0.0
    stderr_text = (r.stderr or b"").decode("utf-8", errors="replace")
    for line in stderr_text.splitlines():
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            try:
                h, m, s = t.split(":")
                return int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                return 0.0
    return 0.0


def get_duration(p: Path, cache: dict) -> float:
    """Public API: returns duration in seconds. Uses cache if valid."""
    if not p.exists():
        return 0.0
    key = _key(p)
    entry = cache["items"].get(key)
    try:
        st = p.stat()
    except Exception:
        return 0.0
    if entry and entry.get("size_bytes") == st.st_size and abs(entry.get("mtime", 0) - st.st_mtime) < 1.0:
        return entry.get("duration_sec", 0.0)
    # Miss — probe and store
    d = probe_duration(p)
    cache["items"][key] = {
        "path": str(p.resolve()),
        "size_bytes": st.st_size,
        "mtime": st.st_mtime,
        "duration_sec": d,
        "probed_at": datetime.now(timezone.utc).isoformat(),
    }
    return d


def warm_from_manifest(manifest_path: Path) -> dict:
    """Walk a channel manifest's content_pool and probe every item.

    For each item, try the `video` field first (preferred for the muxed
    channel-cache mp4); if that file doesn't exist on disk, fall back to
    `audio`. If neither exists, count as missing. This lets us probe
    items where the original audio is on disk but the channel-cache
    video mux hasn't been generated yet (most OTR / sermon items)."""
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    pool = m.get("content_pool", {})
    cache = load_cache()
    stats = {"checked": 0, "cache_hit": 0, "newly_probed": 0, "missing": 0,
             "video_used": 0, "audio_used": 0}
    t0 = time.time()
    for key, items in pool.items():
        for it in items:
            candidates = [c for c in (it.get("video"), it.get("audio")) if c]
            chosen = None
            chosen_kind = None
            for c, kind in [(it.get("video"), "video"), (it.get("audio"), "audio")]:
                if c and Path(c).exists():
                    chosen = c
                    chosen_kind = kind
                    break
            if not chosen:
                stats["missing"] += 1
                continue
            p = Path(chosen)
            if chosen_kind == "video":
                stats["video_used"] += 1
            else:
                stats["audio_used"] += 1
            stats["checked"] += 1
            cache_key = _key(p)
            had = cache_key in cache["items"]
            d = get_duration(p, cache)
            if had and d > 0:
                stats["cache_hit"] += 1
            else:
                stats["newly_probed"] += 1
            # Inline annotate the pool item with duration_sec so the scheduler can read it
            if d > 0 and not it.get("duration_sec"):
                it["duration_sec"] = round(d, 3)
            # Also record which source we used (for the scheduler's resolve step)
            if d > 0 and chosen_kind:
                it["resolved_source"] = chosen_kind
            # Save every 100 items so a crash doesn't lose work
            if stats["checked"] % 100 == 0:
                save_cache(cache)
                print(f"  [{stats['checked']}] probed, "
                      f"hits={stats['cache_hit']} new={stats['newly_probed']} "
                      f"elapsed={time.time()-t0:.1f}s", flush=True)
    save_cache(cache)
    # Write back the annotated manifest so the scheduler picks up duration_sec
    manifest_path.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
    stats["elapsed_sec"] = round(time.time() - t0, 1)
    return stats


def cache_status() -> dict:
    c = load_cache()
    items = c.get("items", {})
    total = len(items)
    if not total:
        return {"total_entries": 0}
    durations = [v.get("duration_sec", 0) for v in items.values()]
    total_sec = sum(durations)
    return {
        "total_entries": total,
        "total_runtime_hours": round(total_sec / 3600, 1),
        "avg_duration_sec": round(total_sec / total, 1),
        "cache_file": str(CACHE_PATH),
        "cache_size_kb": CACHE_PATH.stat().st_size // 1024 if CACHE_PATH.exists() else 0,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--warm", action="store_true", help="Probe every item in the channel manifest")
    p.add_argument("--channel-manifest",
                   default=str(REPO / "content" / "channels" / "narrow_highway.json"))
    p.add_argument("--status", action="store_true", help="Show cache stats and exit")
    args = p.parse_args()

    if args.status:
        print(json.dumps(cache_status(), indent=2))
        return

    if args.warm:
        manifest = Path(args.channel_manifest)
        if not manifest.exists():
            raise SystemExit(f"manifest not found: {manifest}")
        print(f"warming durations from {manifest.name}...")
        stats = warm_from_manifest(manifest)
        print()
        print(json.dumps(stats, indent=2))
        print()
        print(json.dumps(cache_status(), indent=2))
        return

    p.print_help()


if __name__ == "__main__":
    main()
