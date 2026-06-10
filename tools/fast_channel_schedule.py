"""Build a 24-hour programming schedule for a FAST channel.

Takes a channel manifest, walks its programming_block_pattern, fills each block
with content from the pool, inserts bumpers every N minutes, and emits:

  data/channels/<channel_id>/schedule_<date>.json   — slot-by-slot manifest
  data/channels/<channel_id>/schedule_<date>.m3u    — flat playlist of file paths
  site/channels/<channel_id>/epg.xml                — XMLTV format for Plex/Roku EPG
  site/channels/<channel_id>/now.json               — current + next 4 hours (for player UI)

The HLS encoder uses the .m3u to concat-pipe the day into segments.
"""
from __future__ import annotations
import argparse, json, random
from pathlib import Path
from datetime import datetime, timedelta, timezone
import subprocess, imageio_ffmpeg
from xml.sax.saxutils import escape as xml_escape

REPO = Path(__file__).resolve().parent.parent
FF = imageio_ffmpeg.get_ffmpeg_exe()


def get_duration_sec(path: Path) -> float:
    """Probe a media file for its duration. Uses tools/duration_cache.py to
    avoid re-probing 3k+ files on every daily rebuild."""
    if not path.exists():
        return 0.0
    # Cached path — drop in lazily so this file still imports on its own
    try:
        import sys
        sys.path.insert(0, str(REPO / "tools"))
        from duration_cache import load_cache, get_duration as _cached_get  # type: ignore
        cache = load_cache()
        d = _cached_get(path, cache)
        # Don't write the cache here — too noisy on every call. The warmer
        # (tools/duration_cache.py --warm) is responsible for persistence.
        return d
    except Exception:
        # Fallback: direct probe (preserves original behavior)
        pass
    r = subprocess.run([FF, "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    for line in r.stderr.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 0.0


def hms_to_seconds(hms: str) -> int:
    parts = hms.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 3600 + int(parts[1]) * 60
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


# ── Sequential programming ──────────────────────────────────────────────
# Each block cycles through its pool in series/episode order (appointment
# TV) rather than random.choice. This (a) makes every item air — including
# the flagship pilots, which a random draw from a 600-item pool buried —
# and (b) means a block never runs dry, so the scheduler stops wall-
# papering underfilled time with endless station-ID bumpers.
_BLOCK_LINEUP_CACHE: dict = {}


def _ordered_pool_for_block(btype: str, candidates: list) -> dict:
    """Return {'items': ordered list, 'idx': cursor} for a block type.
    Items are clustered into series and ordered by episode (via
    episode_sequencer.build_lineup); the cursor persists across every
    block of the same type within one daily build."""
    cached = _BLOCK_LINEUP_CACHE.get(btype)
    if cached is not None:
        return cached
    ordered = []
    try:
        import sys
        sys.path.insert(0, str(REPO / "tools"))
        from episode_sequencer import build_lineup  # type: ignore
        for series in build_lineup(candidates):
            ordered.extend(series["episodes"])
    except Exception:
        ordered = list(candidates)
    state = {"items": ordered, "idx": 0}
    _BLOCK_LINEUP_CACHE[btype] = state
    return state


def pick_content_for_block(block, channel, used_ids):
    """Pick content matching the block's type, avoiding recently-used.

    Resolution order:
      1. Use channel['_pool_to_block_map'] if present — generic mapping from
         block.type -> pool-key (or list of pool-keys).
      2. Fall back to hard-coded Sci-Fi Theatre mappings for backwards compat.

    Witness gate (Deut 19:15): only items with witness_status == "passed"
    are eligible for scheduling. Items missing witnesses, or marked
    "gov_only" / "self_only" / "insufficient" are silently filtered out.
    Set FAST_CHANNEL_BYPASS_WITNESSES=1 to disable (dev only).
    """
    import os
    pool = channel["content_pool"]
    btype = block["type"]
    candidates = []

    # Try generic pool map first
    pool_map = channel.get("_pool_to_block_map", {})
    if btype in pool_map:
        keys = pool_map[btype]
        if isinstance(keys, str):
            keys = [keys]
        for k in keys:
            candidates.extend(pool.get(k, []))
    else:
        # Backwards-compat fallback for Sci-Fi Theatre
        if btype == "animated_pilot":
            candidates = pool.get("animated_pilots", [])
        elif btype == "audio_drama":
            candidates = (pool.get("audio_dramas_dimension_x", [])
                          + pool.get("audio_dramas_xminus_one", [])
                          + pool.get("audio_dramas_mercury_theatre", []))

    # WITNESS GATE — only schedule witnessed content
    if not os.environ.get("FAST_CHANNEL_BYPASS_WITNESSES"):
        witnessed = [c for c in candidates if c.get("witness_status") == "passed"]
        rejected = len(candidates) - len(witnessed)
        if rejected:
            print(f"[witness-gate] block {btype!r}: {rejected} candidates rejected (not witnessed), {len(witnessed)} eligible",
                  flush=True)
        candidates = witnessed

    # ON-DISK FILTER — only schedule items the duration-cache could probe
    # (duration_sec > 0 means the file exists). Skips ghost catalog entries
    # without forcing every concat step to discover the gap.
    on_disk = [c for c in candidates if (c.get("duration_sec") or 0) > 0]
    ghosts = len(candidates) - len(on_disk)
    if ghosts:
        print(f"[on-disk] block {btype!r}: {ghosts} ghost entries skipped, {len(on_disk)} ready",
              flush=True)
    candidates = on_disk

    # Sequential rotation (appointment TV). Replaces random.choice: every
    # item airs in series/episode order — including the flagship pilots a
    # random draw used to bury — and the lineup loops, so the block never
    # runs dry. That is what eliminates the 14h of bumper wall-papering.
    if not candidates:
        return None
    state = _ordered_pool_for_block(btype, candidates)
    items = state["items"]
    if not items:
        return None
    pick = items[state["idx"] % len(items)]
    state["idx"] += 1
    return pick


def _filter_weekly_pattern(weekly_pattern: list, date: str) -> list:
    """Given a weekly_programming_pattern (entries with 'day': 'monday', etc.),
    return just the entries for the day-of-week that 'date' falls on, stripped
    of the 'day' field so the rest of the scheduler treats them like a 24h pattern.
    """
    dt = datetime.fromisoformat(date + "T00:00:00+00:00")
    dow = dt.strftime("%A").lower()  # 'monday', 'tuesday', ...
    todays = [{k: v for k, v in blk.items() if k != "day"}
              for blk in weekly_pattern
              if blk.get("day", "").lower() == dow]
    return todays


def build_schedule(channel_path: Path, date: str, output_dir: Path,
                   site_channel_dir: Path):
    channel = json.loads(channel_path.read_text(encoding="utf-8"))
    ch_id = channel["channel_id"]
    bumper_dir = Path(f"D:/library_files/_channel_bumpers/{ch_id}")
    # Prefer weekly pattern (filter to today's day-of-week); fall back to legacy daily pattern.
    if "weekly_programming_pattern" in channel:
        pattern = _filter_weekly_pattern(channel["weekly_programming_pattern"], date)
        if not pattern:
            raise RuntimeError(
                f"weekly_programming_pattern has no entries for {datetime.fromisoformat(date + 'T00:00:00+00:00').strftime('%A')}"
            )
    else:
        pattern = channel["programming_block_pattern"]
    bumper_cadence_min = channel.get("bumper_cadence_minutes", 30)

    used = set()
    slots = []
    day_start = datetime.fromisoformat(date + "T00:00:00+00:00")
    cursor = day_start

    # Sort blocks by start time first, then compute each block's duration as
    # (next_block.start - this.start), with the LAST block clamped to 24h
    # rather than wrapping cyclically — that would extend the day past 24h.
    sorted_blocks = sorted(pattern, key=lambda b: hms_to_seconds(b["hour"]))
    block_durations = []
    for i, blk in enumerate(sorted_blocks):
        start_sec = hms_to_seconds(blk["hour"])
        if i + 1 < len(sorted_blocks):
            next_sec = hms_to_seconds(sorted_blocks[i + 1]["hour"])
        else:
            next_sec = 24 * 3600  # last block — clamp at midnight
        if next_sec <= start_sec:
            next_sec = 24 * 3600
        block_durations.append((blk, start_sec, next_sec - start_sec))

    cursor_sec = 0
    last_bumper_sec = 0
    for blk, blk_start_sec, blk_duration_sec in block_durations:
        # Cursor catches up to block start with a station ID if there's a gap
        if cursor_sec < blk_start_sec:
            sid_bumper_path = bumper_dir / f"{channel.get('block_transition_bumper','station_id_1')}.mp4"
            if sid_bumper_path.exists():
                bump_dur = get_duration_sec(sid_bumper_path)
                slots.append({"start_sec": cursor_sec, "duration_sec": bump_dur,
                              "kind": "bumper", "path": str(sid_bumper_path),
                              "title": "Station ID"})
                cursor_sec += bump_dur
            # Pad to block start with another station ID if still short
            while cursor_sec < blk_start_sec - 5:
                bumper = random.choice([b for b in channel["bumpers"] if b["type"] in ("station_id", "pastoral")])
                bumper_path = bumper_dir / f"{bumper['id']}.mp4"
                if bumper_path.exists():
                    d = get_duration_sec(bumper_path)
                    slots.append({"start_sec": cursor_sec, "duration_sec": d,
                                  "kind": "bumper", "path": str(bumper_path),
                                  "title": bumper.get("text", "Bumper")})
                    cursor_sec += d
                else:
                    cursor_sec = blk_start_sec
                    break

        # Fill the block with content
        block_end_sec = blk_start_sec + blk_duration_sec
        # Safety: cap attempts per block to prevent infinite loops if all source
        # files are missing/zero-duration (e.g. cache not yet built).
        attempts_remaining = 64
        while cursor_sec < block_end_sec - 60 and attempts_remaining > 0:
            attempts_remaining -= 1
            picked = pick_content_for_block(blk, channel, used)
            if not picked:
                break
            used.add(picked["id"])
            # Prefer video, fall back to audio with a still-card overlay (simplified: just use audio MP3 here)
            media_path = picked.get("video") or picked.get("audio")
            if not media_path:
                continue
            # Use the pool item's own duration_sec (stamped at acquisition /
            # encode time). Re-probing the file here failed silently for most
            # items — their video/audio fields are bare/relative paths that
            # don't resolve from the scheduler's CWD — so the fill loop
            # skipped them, underfilled the block, and padded it with bumpers.
            dur = float(picked.get("duration_sec") or 0)
            if dur <= 0:
                dur = get_duration_sec(Path(media_path))
            if dur <= 0:
                continue
            # Successful add — reset attempt budget for this block
            attempts_remaining = 64
            slots.append({"start_sec": cursor_sec, "duration_sec": dur,
                          "kind": "content", "path": str(media_path),
                          "title": picked["title"], "id": picked["id"],
                          "block_name": blk["block_name"]})
            cursor_sec += dur
            # Insert bumper if cadence reached
            if cursor_sec - last_bumper_sec >= bumper_cadence_min * 60 and cursor_sec < block_end_sec - 30:
                bumper = random.choice([b for b in channel["bumpers"] if b["type"] in ("station_id", "up_next", "pastoral")])
                bumper_path = bumper_dir / f"{bumper['id']}.mp4"
                if bumper_path.exists():
                    bd = get_duration_sec(bumper_path)
                    slots.append({"start_sec": cursor_sec, "duration_sec": bd,
                                  "kind": "bumper", "path": str(bumper_path),
                                  "title": bumper.get("text", "Bumper")})
                    cursor_sec += bd
                    last_bumper_sec = cursor_sec

    total_dur = cursor_sec
    # === Write outputs ===
    output_dir.mkdir(parents=True, exist_ok=True)
    site_channel_dir.mkdir(parents=True, exist_ok=True)

    schedule_json = {
        "channel_id": ch_id,
        "channel_name": channel["name"],
        "date": date,
        "total_duration_sec": total_dur,
        "slot_count": len(slots),
        "slots": slots,
    }
    schedule_path = output_dir / f"schedule_{date}.json"
    schedule_path.write_text(json.dumps(schedule_json, indent=2), encoding="utf-8")

    # Flat .m3u playlist for ffmpeg concat
    m3u_path = output_dir / f"schedule_{date}.m3u"
    with m3u_path.open("w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for s in slots:
            f.write(f"#EXTINF:{int(s['duration_sec'])},{s['title']}\n")
            f.write(f"{s['path']}\n")

    # ffmpeg concat list (simpler, no metadata)
    concat_path = output_dir / f"schedule_{date}.concat.txt"
    with concat_path.open("w", encoding="utf-8") as f:
        for s in slots:
            # Escape single quotes for ffmpeg concat
            p = s["path"].replace("'", "'\\''")
            f.write(f"file '{p}'\n")

    # EPG (XMLTV) — for Plex/Roku
    epg_path = site_channel_dir / "epg.xml"
    epg_lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<tv source-info-name="Narrow Highway" generator-info-name="nh-fast">',
                 f'  <channel id="{ch_id}"><display-name>{xml_escape(channel["name"])}</display-name></channel>']
    # Programs in TZ-aware format
    program_cursor = day_start
    for s in slots:
        if s["kind"] != "content":
            program_cursor += timedelta(seconds=s["duration_sec"])
            continue
        end = program_cursor + timedelta(seconds=s["duration_sec"])
        start_str = program_cursor.strftime("%Y%m%d%H%M%S +0000")
        end_str = end.strftime("%Y%m%d%H%M%S +0000")
        epg_lines.append(
            f'  <programme channel="{ch_id}" start="{start_str}" stop="{end_str}">'
            f'<title>{xml_escape(s["title"])}</title>'
            f'<desc>{xml_escape(channel["description"])}</desc>'
            f'</programme>'
        )
        program_cursor = end
    epg_lines.append("</tv>")
    epg_path.write_text("\n".join(epg_lines), encoding="utf-8")

    # now.json — what's on now + next few
    # For a given UTC time, find slot. For static schedule, just record relative offsets.
    now_obj = {
        "channel_id": ch_id,
        "channel_name": channel["name"],
        "schedule_date": date,
        "total_duration_sec": total_dur,
        "upcoming": [],
    }
    cumulative = 0.0
    for s in slots[:200]:  # cap at 200 entries
        if s["kind"] == "content":
            now_obj["upcoming"].append({
                "offset_sec_from_midnight": cumulative,
                "title": s["title"],
                "duration_sec": s["duration_sec"],
                "block": s.get("block_name", ""),
            })
        cumulative += s["duration_sec"]
    now_path = site_channel_dir / "now.json"
    now_path.write_text(json.dumps(now_obj, indent=2), encoding="utf-8")

    return {
        "schedule_path": schedule_path,
        "m3u_path": m3u_path,
        "concat_path": concat_path,
        "epg_path": epg_path,
        "now_path": now_path,
        "total_duration_sec": total_dur,
        "slot_count": len(slots),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", required=True)
    ap.add_argument("--date", default=None, help="YYYY-MM-DD; default today")
    args = ap.parse_args()
    date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ch = json.loads(Path(args.channel).read_text(encoding="utf-8"))
    ch_id = ch["channel_id"]
    out = REPO / "data" / "channels" / ch_id
    site_out = REPO / "site" / "channels" / ch_id
    print(f"Building schedule for {ch_id} on {date}")
    result = build_schedule(Path(args.channel), date, out, site_out)
    print(f"  schedule.json: {result['schedule_path']}")
    print(f"  m3u playlist:  {result['m3u_path']}")
    print(f"  ffmpeg concat: {result['concat_path']}")
    print(f"  EPG XMLTV:     {result['epg_path']}")
    print(f"  now.json:      {result['now_path']}")
    print(f"  slots:         {result['slot_count']}")
    hrs = result['total_duration_sec'] / 3600
    print(f"  total runtime: {hrs:.2f} hours ({'(24h target hit)' if hrs >= 23.5 else '(NEEDS MORE CONTENT)'})")


if __name__ == "__main__":
    main()
