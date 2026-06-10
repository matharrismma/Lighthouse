"""episode_sequencer.py - Appointment-viewing episode progression.

Turns the FAST channel from random-shuffle into appointment TV: each
named slot marches through a show one episode per day, IN ORDER. When a
show runs out, the slot advances to the next show in the SAME pool (same
genre). The slot's time and genre never change - that's the product.

See memory: project_appointment_programming_2026-05-20.

Two pieces:
  1. Series grouping - cluster a pool's items into shows, episodes ordered
  2. Slot state - data/channels/slot_state.json persists, per slot:
       {series, ep_index, last_date}
     Each daily rebuild advances ep_index. Exhaust a series -> next series.

The scheduler (fast_channel_schedule.py) calls `next_for_block` instead
of random.choice when the channel manifest has "sequential_programming": true.
"""
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "data" / "channels" / "slot_state.json"

# Episode / junk markers we strip to find the bare series name.
_EP_MARKERS = re.compile(
    r"\b(s\d{1,2}\s*e\d{1,3}|season\s*\d+|episode\s*\d+|ep\s*\d+|part\s*\d+|"
    r"\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{2}|#?\d{2,4}|complete|full|uncut|"
    r"remastered|hd|1080p|480p|4k)\b",
    re.IGNORECASE,
)
_PREFIX = re.compile(r"^(tv|anim|otr|pdcartoon|hymn|kids)[\s_]+", re.IGNORECASE)


def parse_series(item: Dict[str, Any]) -> str:
    """Extract a coarse series name from a pool item's title (or id)."""
    raw = (item.get("title") or item.get("id") or "").strip()
    s = _PREFIX.sub("", raw)
    # cut at the first episode marker — everything before it is the show
    m = _EP_MARKERS.search(s)
    if m:
        s = s[: m.start()]
    s = re.sub(r"[^A-Za-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # collapse an immediately-doubled show name ("Clutch Cargo Clutch Cargo")
    words = s.split()
    half = len(words) // 2
    if half >= 1 and words[:half] == words[half:2 * half]:
        words = words[:half]
    # keep the first 4 significant words as the series key
    key = " ".join(words[:4]).strip()
    return key or raw[:40] or "Untitled"


def _ep_sort_key(item: Dict[str, Any]) -> tuple:
    """Order episodes within a series: by sNNeNN, then date, then id."""
    blob = (item.get("title") or "") + " " + (item.get("id") or "")
    se = re.search(r"s(\d{1,2})\s*e(\d{1,3})", blob, re.IGNORECASE)
    if se:
        return (0, int(se.group(1)), int(se.group(2)), item.get("id", ""))
    d = re.search(r"(\d{4})-(\d{2})-(\d{2})", blob)
    if d:
        return (1, int(d.group(1)), int(d.group(2) + d.group(3)), item.get("id", ""))
    n = re.search(r"\b(\d{2,4})\b", blob)
    if n:
        return (2, int(n.group(1)), 0, item.get("id", ""))
    return (3, 0, 0, item.get("id", ""))


def build_lineup(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group items into series; return an ordered list of
    {series, episodes:[...]}. Series ordered by size desc (biggest shows
    anchor the slot), episodes ordered within."""
    by_series: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        by_series.setdefault(parse_series(it), []).append(it)
    lineup = []
    for series, eps in by_series.items():
        eps.sort(key=_ep_sort_key)
        lineup.append({"series": series, "episodes": eps})
    lineup.sort(key=lambda s: (-len(s["episodes"]), s["series"]))
    return lineup


def _load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def next_for_block(channel_id: str, block_name: str, items: List[Dict[str, Any]],
                   count: int, date: str, advance: bool = True) -> List[Dict[str, Any]]:
    """Return the next `count` episodes for a slot, in order.

    The slot marches through its current series; when the series runs out
    it advances to the next series in `items` (same pool = same genre).
    State (which series, which episode) persists across days. With
    advance=True the pointer moves forward and is saved — call once per
    daily rebuild per slot."""
    if not items:
        return []
    lineup = build_lineup(items)
    if not lineup:
        return []

    state = _load_state()
    ch = state.setdefault(channel_id, {})
    slot = ch.get(block_name) or {}
    series_idx = slot.get("series_idx", 0) % len(lineup)
    ep_idx = slot.get("ep_idx", 0)

    out: List[Dict[str, Any]] = []
    guard = 0
    while len(out) < count and guard < len(items) + len(lineup) + 5:
        guard += 1
        series = lineup[series_idx]
        eps = series["episodes"]
        if ep_idx >= len(eps):
            # current show exhausted -> next show, same genre
            series_idx = (series_idx + 1) % len(lineup)
            ep_idx = 0
            continue
        out.append(eps[ep_idx])
        ep_idx += 1

    if advance:
        # The daily advance: tomorrow's slot starts where today's ended.
        ch[block_name] = {
            "series": lineup[series_idx]["series"],
            "series_idx": series_idx,
            "ep_idx": ep_idx,
            "last_date": date,
        }
        _save_state(state)
    return out


def slot_report(channel_id: str) -> dict:
    """What each slot is currently on — for the operator."""
    state = _load_state()
    return state.get(channel_id, {})


if __name__ == "__main__":
    # Self-test against the live channel manifest
    import sys
    manifest = REPO / "content" / "channels" / "narrow_highway.json"
    m = json.loads(manifest.read_text(encoding="utf-8"))
    pool = m.get("content_pool", {})
    key = sys.argv[1] if len(sys.argv) > 1 else "classic_tv_video"
    items = pool.get(key, [])
    print(f"pool '{key}': {len(items)} items")
    lineup = build_lineup(items)
    print(f"grouped into {len(lineup)} series:")
    for s in lineup[:12]:
        print(f"  {s['series']:<36} {len(s['episodes'])} eps")
