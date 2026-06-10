"""Static snapshot of what's playing on each channel right now.

Reads each channel's schedule_<today>.json, computes the wall-clock playhead,
and emits site/channels/now.json — a single file the homepage / dashboard
fetches to render a "what's on" strip across all channels.

Designed to be run from a periodic cron (every minute). The FastAPI engine
also serves a live equivalent at /channels/now.json but the static snapshot
is the no-engine fallback.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SITE_CH = REPO / "site" / "channels"
DATA_CH = REPO / "data" / "channels"

# Only channels in this set get reported as currently-broadcasting in the
# cross-channel snapshot. Programming-source manifests still have schedules
# (for browsing) but they aren't surfaced as live channels.
# Source of truth: tools/fast_channel_index.py LIVE_CHANNEL_IDS.
LIVE_CHANNEL_IDS = {"narrow-highway"}


def current_for_channel(ch_id: str, now: datetime) -> dict | None:
    sched_path = DATA_CH / ch_id / f"schedule_{now.strftime('%Y-%m-%d')}.json"
    if not sched_path.exists():
        return None
    sched = json.loads(sched_path.read_text(encoding="utf-8"))
    total = sched.get("total_duration_sec", 0) or 1
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (now - day_start).total_seconds() % total
    cur, nxt = None, None
    acc = 0.0
    slots = sched["slots"]
    for i, s in enumerate(slots):
        if acc + s["duration_sec"] > elapsed:
            cur = s
            nxt = slots[(i + 1) % len(slots)]
            break
        acc += s["duration_sec"]
    return {
        "channel_id": ch_id,
        "channel_name": sched.get("channel_name"),
        "current": {
            "title": cur["title"], "kind": cur["kind"],
            "block": cur.get("block_name"),
            "remaining_sec": int(acc + cur["duration_sec"] - elapsed),
        } if cur else None,
        "next": {
            "title": nxt["title"], "kind": nxt["kind"],
            "block": nxt.get("block_name"),
        } if nxt else None,
    }


def main():
    now = datetime.now(timezone.utc)
    out = {
        "generated": now.isoformat(),
        "channels": [],
    }
    if not DATA_CH.exists():
        SITE_CH.mkdir(parents=True, exist_ok=True)
        (SITE_CH / "now.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("No data/channels/ — wrote empty now.json")
        return
    for ch_dir in sorted(DATA_CH.iterdir()):
        if not ch_dir.is_dir():
            continue
        snapshot = current_for_channel(ch_dir.name, now)
        if snapshot:
            # Tag with HLS-live status (i.e. day.m3u8 exists)
            snapshot["hls_live"] = (SITE_CH / ch_dir.name / "hls" / "day.m3u8").exists()
            snapshot["role"] = "live" if ch_dir.name in LIVE_CHANNEL_IDS else "programming-source"
            out["channels"].append(snapshot)
    # Also expose convenience subsets
    out["live"] = [c for c in out["channels"] if c.get("role") == "live"]
    out["programming_sources"] = [c for c in out["channels"] if c.get("role") == "programming-source"]
    SITE_CH.mkdir(parents=True, exist_ok=True)
    (SITE_CH / "now.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"Wrote {SITE_CH / 'now.json'} ({len(out['channels'])} channels)")
    for c in out["channels"]:
        cur = c.get("current") or {}
        live = "LIVE" if c.get("hls_live") else "----"
        print(f"  [{live}] {c['channel_id']:24} {cur.get('title','')[:50]}")


if __name__ == "__main__":
    main()
