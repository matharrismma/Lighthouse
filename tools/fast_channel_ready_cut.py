"""Produce a "ready cut" schedule: only the slots whose encoded MP4 is ALREADY
cached, re-timed into one continuous loop.

Why: a FAST channel does not have to wait for a full 24h of content to go live.
It can ship the subset that is already encoded NOW and grow as more slots encode.
This is the "ship one episode tonight, prove the pipeline, then automate" path --
operationalized. The live endpoint (api/fast_live.py) loops the day on wall-clock,
so a 10h ready-cut simply repeats ~2.4x/day until the schedule is filled out.

It reuses the SAME resolver as the HLS builder (fast_channel_hls.resolve_concat_paths)
so "ready" here means exactly "what fast_channel_hls.py would concat" -- no second,
drifting definition of resolvable.

Read-only on all sources. Writes exactly one JSON (the ready-cut schedule).

Usage:
  python tools/fast_channel_ready_cut.py --channel nh-scifi-theatre --date 2026-05-18
  -> data/channels/<ch>/schedule_ready.json   (resolves 100% against the cache)

Then, on the workshop machine (this box), once the segments are wanted:
  python tools/fast_channel_hls.py --channel <manifest.json> --date ready
  (point --date at the ready cut, or copy schedule_ready.json to schedule_ready.json)
"""
from __future__ import annotations
import argparse
import contextlib
import io
import json
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
from fast_channel_hls import resolve_concat_paths  # the ONE resolver  # noqa: E402


def _resolves(slot: dict, cache_dir: Path) -> bool:
    """True iff fast_channel_hls would find a cached MP4 for this slot. Quiet:
    the resolver prints a WARN for misses, which we swallow here."""
    with contextlib.redirect_stdout(io.StringIO()):
        return bool(resolve_concat_paths({"slots": [slot]}, cache_dir))


def ready_cut(schedule: dict, cache_dir: Path) -> dict:
    """Return a new schedule keeping only cache-resolved slots, re-timed so
    start_sec is continuous and total_duration_sec matches the kept runtime."""
    kept = []
    t = 0.0
    for s in schedule.get("slots", []):
        if not _resolves(s, cache_dir):
            continue
        ns = dict(s)
        ns["start_sec"] = round(t, 2)
        t += float(s.get("duration_sec") or 0.0)
        kept.append(ns)
    out = dict(schedule)
    out["slots"] = kept
    out["slot_count"] = len(kept)
    out["total_duration_sec"] = round(t, 2)
    out["cut"] = "ready"  # marker: only already-encoded slots, re-timed
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="channel id, e.g. nh-scifi-theatre")
    ap.add_argument("--date", required=True, help="source schedule date (YYYY-MM-DD)")
    ap.add_argument("--cache", default=None,
                    help="override cache dir (default D:/library_files/_channel_cache/<ch>)")
    ap.add_argument("--out", default=None,
                    help="output path (default data/channels/<ch>/schedule_ready.json)")
    args = ap.parse_args()

    ch = args.channel
    src = REPO / "data" / "channels" / ch / f"schedule_{args.date}.json"
    if not src.exists():
        print(f"[FATAL] no schedule at {src}")
        return 1
    cache_dir = Path(args.cache) if args.cache else Path(f"D:/library_files/_channel_cache/{ch}")
    out_path = Path(args.out) if args.out else (REPO / "data" / "channels" / ch / "schedule_ready.json")

    schedule = json.loads(src.read_text(encoding="utf-8"))
    cut = ready_cut(schedule, cache_dir)

    total_in = len(schedule.get("slots", []))
    content = sum(1 for s in cut["slots"] if s.get("kind") == "content")
    bumpers = sum(1 for s in cut["slots"] if s.get("kind") == "bumper")
    out_path.write_text(json.dumps(cut, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"ready cut: {cut['slot_count']}/{total_in} slots resolved "
          f"({content} content + {bumpers} bumper)")
    print(f"ready runtime: {cut['total_duration_sec']/3600:.2f}h "
          f"of {schedule.get('total_duration_sec', 0)/3600:.2f}h scheduled")
    print(f"wrote: {out_path}")
    if not cut["slot_count"]:
        print("[WARN] nothing resolved -- run fast_channel_encode.py first")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
