"""Daily-ops one-shot: rebuild schedule, HLS day, MRSS, index, now.json for every channel.

Walks content/channels/*.json. For each channel:
  1. Run the scheduler for today's date.
  2. If the cache is sufficiently populated (>50% of unique scheduled items), build the HLS day.
     Otherwise skip the HLS step and report what's still missing.
  3. Refresh MRSS and EPG.
Finally rebuild the channels index + cross-channel now.json snapshot.

Operator runs this once each morning. Cron-friendly: prints a status block and exits 0
unless something blows up.
"""
from __future__ import annotations
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def run(cmd: list[str]) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def coverage_for_channel(ch: dict) -> tuple[int, int]:
    """How many unique pool items have cache files? (covered, total)."""
    ch_id = ch["channel_id"]
    cache_dir = Path(f"D:/library_files/_channel_cache/{ch_id}")
    covered, total = 0, 0
    for category, items in ch["content_pool"].items():
        for it in items:
            total += 1
            if (cache_dir / f"{it['id']}.mp4").exists():
                covered += 1
    return covered, total


def main():
    print(f"=== Daily channel ops for {TODAY} ===\n")
    summary = []

    for manifest_path in sorted((REPO / "content" / "channels").glob("*.json")):
        ch = json.loads(manifest_path.read_text(encoding="utf-8"))
        ch_id = ch["channel_id"]
        cov, tot = coverage_for_channel(ch)
        pct = (cov / tot * 100) if tot else 0
        line = f"[{ch_id}] {cov}/{tot} cached ({pct:.0f}%)"

        # 1. Schedule
        rc, out = run(["python", "tools/fast_channel_schedule.py",
                       "--channel", str(manifest_path), "--date", TODAY])
        if rc == 0:
            line += " · schedule OK"
        else:
            line += f" · schedule FAILED: {out[-200:]}"
            summary.append(line)
            continue

        # 2. MRSS
        rc, out = run(["python", "tools/fast_channel_mrss.py", "--channel", str(manifest_path)])
        if rc == 0:
            line += " · MRSS OK"

        # 3. HLS day — only if enough cache exists
        if pct >= 50 or ch_id == "nh-hymns-247":  # hymns has its own render path
            rc, out = run(["python", "tools/fast_channel_hls.py",
                           "--channel", str(manifest_path), "--date", TODAY])
            if rc == 0:
                # Quick segment count
                day_m3u8 = REPO / "site" / "channels" / ch_id / "hls" / "day.m3u8"
                segs = list((REPO / "site" / "channels" / ch_id / "hls").glob("seg_*.ts")) \
                    if day_m3u8.exists() else []
                line += f" · HLS OK ({len(segs)} segments)"
            else:
                line += f" · HLS FAILED: {out[-200:]}"
        else:
            line += f" · HLS skipped (need 50% cache, have {pct:.0f}%)"

        summary.append(line)

    # 4. Index + now.json
    run(["python", "tools/fast_channel_index.py"])
    run(["python", "tools/fast_channel_now_all.py"])

    print("\n=== SUMMARY ===")
    for line in summary:
        print(line)
    print(f"\nIndex + now.json refreshed.\nDone at {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
