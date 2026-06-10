"""FAST channel live HLS endpoint.

Serves a 24/7 looping HLS stream for each channel. Internally we have a VOD
playlist of a full day (day.m3u8 with seg_*.ts produced by fast_channel_hls.py).
The live endpoint:

  GET /channels/<channel_id>/live.m3u8
    - Computes current wall-clock playhead within the 24h cycle (modulo).
    - Emits a sliding window of ~6 segments centered on the playhead.
    - Uses HLS LIVE type so Plex/VLC/Roku treat it as a real broadcast.

  GET /channels/<channel_id>/seg_<n>.ts
    - Serves the segment file directly from site/channels/<ch>/hls/.

  GET /channels/<channel_id>/now.json
    - Returns the currently-playing item + next-up for client UIs.

The .ts segments are static files on disk. Only the m3u8 is generated per-request.
"""
from __future__ import annotations
import json, re, time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Response
    from fastapi.responses import FileResponse, PlainTextResponse
except Exception:  # FastAPI not yet imported in this context
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CHANNELS_DIR = REPO / "site" / "channels"
DATA_DIR = REPO / "data" / "channels"
WINDOW_SEG = 6  # segments visible in sliding window (~36s @ 6s segments)


# ----- pure helpers (importable in tests) ---------------------------------

def _segment_durations(m3u8_path: Path) -> list[float]:
    """Parse an HLS playlist and return per-segment durations."""
    durs = []
    if not m3u8_path.exists():
        return durs
    text = m3u8_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("#EXTINF:"):
            m = re.match(r"#EXTINF:([\d\.]+)", line)
            if m:
                durs.append(float(m.group(1)))
    return durs


def _find_current_day_playlist(channel_id: str) -> Optional[Path]:
    """Return the day.m3u8 file for today, or fall back to whatever exists."""
    hls_dir = CHANNELS_DIR / channel_id / "hls"
    if not hls_dir.exists():
        return None
    today = hls_dir / "day.m3u8"
    if today.exists():
        return today
    # Fallback: any day.m3u8 in this dir
    for cand in hls_dir.glob("*.m3u8"):
        return cand
    return None


def _compute_playhead(durations: list[float], now: Optional[datetime] = None) -> tuple[int, float]:
    """Given segment durations and current UTC time, return (segment_index, offset_within_segment)."""
    if not durations:
        return (0, 0.0)
    total = sum(durations)
    if total <= 0:
        return (0, 0.0)
    now = now or datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = (now - day_start).total_seconds()
    # Loop modulo total
    pos = elapsed % total
    # Walk durations to find which segment we're inside
    acc = 0.0
    for i, d in enumerate(durations):
        if acc + d > pos:
            return (i, pos - acc)
        acc += d
    return (len(durations) - 1, 0.0)


def _build_sliding_window(durations: list[float], current_idx: int,
                          window: int = WINDOW_SEG) -> tuple[int, list[int]]:
    """Return (sequence_number, list of segment indices for the window)."""
    n = len(durations)
    if n == 0:
        return (0, [])
    # Place window so playhead is near the front (so client buffers ahead)
    start = current_idx
    indices = [(start + i) % n for i in range(window)]
    # MEDIA-SEQUENCE: a monotonically-increasing number derived from epoch + index.
    # We use absolute seconds-since-epoch / segment-time to give clients a stable counter.
    sequence = int(time.time() // 6) + current_idx
    return (sequence, indices)


def _build_live_m3u8(durations: list[float], current_idx: int) -> str:
    """Compose the live sliding-window m3u8 body."""
    seq, indices = _build_sliding_window(durations, current_idx)
    target = int(max(durations[i] for i in indices)) + 1 if indices else 7
    lines = [
        "#EXTM3U",
        "#EXT-X-VERSION:6",
        f"#EXT-X-TARGETDURATION:{target}",
        f"#EXT-X-MEDIA-SEQUENCE:{seq}",
        "#EXT-X-PLAYLIST-TYPE:EVENT",
        "#EXT-X-INDEPENDENT-SEGMENTS",
    ]
    for idx in indices:
        d = durations[idx]
        lines.append(f"#EXTINF:{d:.3f},")
        lines.append(f"seg_{idx:05d}.ts")
    return "\n".join(lines) + "\n"


def _current_program(channel_id: str, now: Optional[datetime] = None) -> dict:
    """Look at today's schedule and report current + next item titles."""
    today_str = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    sched_path = DATA_DIR / channel_id / f"schedule_{today_str}.json"
    if not sched_path.exists():
        return {"current": None, "next": None, "channel_id": channel_id}
    sched = json.loads(sched_path.read_text(encoding="utf-8"))
    total = sched.get("total_duration_sec", 0) or 1
    now = now or datetime.now(timezone.utc)
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
    out = {
        "channel_id": channel_id,
        "channel_name": sched.get("channel_name"),
        "now_utc": now.isoformat(),
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
    return out


# ----- FastAPI router ------------------------------------------------------

def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/channels/{channel_id}/live.m3u8")
    def live_playlist(channel_id: str):
        m3u8 = _find_current_day_playlist(channel_id)
        if not m3u8:
            raise HTTPException(404, f"No day playlist for channel '{channel_id}'")
        durations = _segment_durations(m3u8)
        if not durations:
            raise HTTPException(503, "Empty playlist")
        idx, _ = _compute_playhead(durations)
        body = _build_live_m3u8(durations, idx)
        return Response(
            content=body,
            media_type="application/vnd.apple.mpegurl",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @router.get("/channels/{channel_id}/seg_{n}.ts")
    def segment(channel_id: str, n: str):
        p = CHANNELS_DIR / channel_id / "hls" / f"seg_{n}.ts"
        if not p.exists():
            raise HTTPException(404)
        return FileResponse(
            p,
            media_type="video/mp2t",
            headers={
                "Cache-Control": "public, max-age=31536000",
                "Access-Control-Allow-Origin": "*",
            },
        )

    @router.get("/channels/{channel_id}/now.json")
    def now(channel_id: str):
        return _current_program(channel_id)

    @router.get("/channels/now.json")
    def now_all():
        """Aggregator: current + next for every channel that has a schedule today."""
        from datetime import datetime, timezone
        now_dt = datetime.now(timezone.utc)
        out = {"generated": now_dt.isoformat(), "channels": []}
        if not DATA_DIR.exists():
            return out
        for ch_dir in sorted(DATA_DIR.iterdir()):
            if not ch_dir.is_dir():
                continue
            snapshot = _current_program(ch_dir.name, now_dt)
            if snapshot and snapshot.get("channel_name"):
                snapshot["hls_live"] = (CHANNELS_DIR / ch_dir.name / "hls" / "day.m3u8").exists()
                out["channels"].append(snapshot)
        return out

    return router


# ----- CLI for smoke-test --------------------------------------------------

def main():
    import argparse, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="nh-scifi-theatre")
    args = ap.parse_args()
    m3u8 = _find_current_day_playlist(args.channel)
    if not m3u8:
        print(f"[FATAL] no day.m3u8 for {args.channel}")
        sys.exit(1)
    durs = _segment_durations(m3u8)
    idx, off = _compute_playhead(durs)
    print(f"Channel: {args.channel}")
    print(f"  segments: {len(durs)} totalling {sum(durs)/3600:.2f}h")
    print(f"  current playhead: segment {idx}, +{off:.1f}s into it")
    print(f"  now.json: {_current_program(args.channel)}")
    print("\n--- live.m3u8 preview ---")
    print(_build_live_m3u8(durs, idx))


if __name__ == "__main__":
    main()
