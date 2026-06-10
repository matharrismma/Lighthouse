"""Build a 24h HLS playlist + .ts segments for a FAST channel from its daily schedule.

Pipeline:
  schedule_<date>.json   →   resolve each slot to cached uniform MP4
                          →   ffmpeg concat into a continuous output
                          →   HLS muxer chops to 6s segments + day.m3u8
                          →   segments named like seg_00001.ts ... seg_NNNNN.ts
                          →   each segment carries channel-id metadata
                          →   total runtime should match schedule.total_duration_sec

Outputs (under site/channels/<ch_id>/hls/):
  day.m3u8                 — VOD-type playlist of the entire 24h day
  seg_<n>.ts               — segments

Distribution use:
  - Plex Live TV ingests an HLS feed from a stable URL.
  - YouTube Live can rebroadcast an HLS via OBS or direct RTMP push.
  - Roku Direct Publisher prefers MRSS for VOD; HLS is for live channel ingest.

Live behavior:
  This script produces VOD-style HLS (full day enumerated). The live endpoint
  (api/fast_live.py) computes the current playhead from wall-clock + 24h loop
  and emits a sliding HLS-EVENT window to clients in real time.
"""
from __future__ import annotations
import argparse, json, os, sys
from pathlib import Path
import subprocess, imageio_ffmpeg

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
SEGMENT_SEC = 6  # HLS spec recommends 6s segments for broad compatibility


def resolve_concat_paths(schedule: dict, cache_dir: Path) -> list[tuple[Path, float, str]]:
    """For each slot, find a usable uniform-MP4 path.

    Resolution order:
      1. The slot's own 'path' field, if it exists and points at a real file.
         This handles the unified-channel case where items are sourced from
         other channels' caches (e.g. nh-scifi-theatre/dimx_01.mp4).
      2. cache_dir / bumper_<stem>.mp4  (legacy bumper cache for per-channel encodes)
      3. cache_dir / <id>.mp4           (legacy content cache for per-channel encodes)
    """
    resolved = []
    for s in schedule["slots"]:
        kind = s["kind"]
        title = s.get("title", "")
        # 1. Direct path from the schedule, if valid
        direct = Path(s.get("path", ""))
        cached = None
        if direct.exists() and direct.suffix.lower() == ".mp4":
            cached = direct
        elif kind == "bumper":
            cached = cache_dir / f"bumper_{direct.stem}.mp4"
        else:
            iid = s.get("id") or direct.stem
            cached = cache_dir / f"{iid}.mp4"
        if not cached or not cached.exists():
            print(f"  [WARN missing cache] {kind} {title}  tried: {cached}")
            continue
        resolved.append((cached, float(s["duration_sec"]), title))
    return resolved


def write_concat_list(resolved: list, list_path: Path):
    with list_path.open("w", encoding="utf-8") as f:
        for path, dur, title in resolved:
            p = str(path).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{p}'\n")


def build_hls_day(channel_id: str, schedule_date: str,
                  schedule_path: Path, cache_dir: Path, out_dir: Path,
                  segment_sec: int = SEGMENT_SEC, copy_codec: bool = True):
    schedule = json.loads(schedule_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building HLS day for {channel_id} on {schedule_date}")
    print(f"  Cache:   {cache_dir}")
    print(f"  Out:     {out_dir}")
    print(f"  Slots:   {schedule['slot_count']}, total {schedule['total_duration_sec']/3600:.2f} h")

    resolved = resolve_concat_paths(schedule, cache_dir)
    if not resolved:
        print("  [FATAL] No cached sources resolved. Run fast_channel_encode.py first.")
        return None
    print(f"  Resolved {len(resolved)}/{len(schedule['slots'])} slots from cache.")

    # Clear out stale segments
    for old in out_dir.glob("seg_*.ts"):
        old.unlink()
    for old in out_dir.glob("day.m3u8"):
        old.unlink()

    # Write concat list
    concat_path = out_dir / "concat.txt"
    write_concat_list(resolved, concat_path)

    # ffmpeg: concat demux -> HLS muxer
    cmd = [
        FF, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
    ]
    if copy_codec:
        # Stream-copy when sources are uniform — much faster
        cmd += ["-c", "copy"]
    else:
        cmd += [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-ac", "2",
        ]
    cmd += [
        "-f", "hls",
        "-hls_time", str(segment_sec),
        "-hls_list_size", "0",  # full VOD playlist (every segment listed)
        "-hls_playlist_type", "vod",
        "-hls_segment_filename", str(out_dir / "seg_%05d.ts"),
        "-hls_flags", "independent_segments",
        str(out_dir / "day.m3u8"),
    ]

    print(f"  Running ffmpeg HLS mux (segment={segment_sec}s, copy={copy_codec})...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        # Stream-copy can fail if sources aren't perfectly concat-aligned.
        # The re-encode fallback is a full multi-hour libx264 pass — heavy
        # enough to OOM a small box — so it does NOT run automatically.
        # Re-run explicitly with --no-copy (ideally on the workshop machine).
        if copy_codec:
            print("  [stream-copy FAILED] sources not concat-aligned.")
            print(f"  ffmpeg tail: {r.stderr[-800:]}")
            print("  To re-encode, re-run with --no-copy "
                  "(heavy multi-hour encode — use the workshop machine, not the engine host).")
            return None
        print(f"  [FATAL ffmpeg] {r.stderr[-1500:]}")
        return None

    # Tally segments
    segs = sorted(out_dir.glob("seg_*.ts"))
    total_bytes = sum(s.stat().st_size for s in segs)
    print(f"  [OK] {len(segs)} segments, {total_bytes / (1024**3):.2f} GB total")
    print(f"  day.m3u8: {out_dir / 'day.m3u8'}")

    return {
        "channel_id": channel_id,
        "date": schedule_date,
        "segment_count": len(segs),
        "total_bytes": total_bytes,
        "playlist": str(out_dir / "day.m3u8"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True, help="channel manifest JSON")
    ap.add_argument("--date", required=True, help="schedule date (YYYY-MM-DD)")
    ap.add_argument("--segment-sec", type=int, default=SEGMENT_SEC)
    ap.add_argument("--no-copy", action="store_true",
                    help="Force re-encode instead of stream-copy")
    args = ap.parse_args()

    ch = json.loads(Path(args.channel).read_text(encoding="utf-8"))
    ch_id = ch["channel_id"]
    cache_dir = Path(f"D:/library_files/_channel_cache/{ch_id}")
    schedule_path = REPO / "data" / "channels" / ch_id / f"schedule_{args.date}.json"
    if not schedule_path.exists():
        print(f"[FATAL] No schedule at {schedule_path}. Run fast_channel_schedule.py first.")
        sys.exit(1)
    out_dir = REPO / "site" / "channels" / ch_id / "hls"

    result = build_hls_day(ch_id, args.date, schedule_path, cache_dir, out_dir,
                           segment_sec=args.segment_sec, copy_codec=not args.no_copy)
    if result:
        print("\n--- HLS DAY READY ---")
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
