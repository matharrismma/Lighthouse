"""link_sequential_cards.py — Add prev/next connections to narrative works.

For each card on shelves where order matters (Pilgrim's Progress, Augustine
Confessions, Aurelius Meditations, Imitation of Christ, patristic chapters
within a single work), sort by section number and add prev/next "see_also"
connections so the reader can walk the narrative card-by-card.

Usage:
  python tools/link_sequential_cards.py
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CARDS_DIR = REPO / "data" / "cards"

# Shelves+boxes where sequence matters
SEQUENTIAL_BOXES = [
    "pilgrims_progress",
    "augustine_confessions",
    "aurelius_meditations",
    "boethius_consolation",
    "imitation_of_christ",
    "pirkei_avot",
    "clement_first",
    "didache",
    "ignatius_ephesians", "ignatius_magnesians", "ignatius_philadelphians",
    "ignatius_to_polycarp", "ignatius_romans", "ignatius_smyrnaeans", "ignatius_trallians",
    "polycarp_philippians", "martyrdom_polycarp", "barnabas",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sort_key(card: dict) -> tuple:
    """Extract a sortable sequence number from title or source.ref."""
    title = card.get("title", "")
    ref = (card.get("source") or {}).get("ref", "")
    # Try various patterns:
    # "Pilgrim's Progress §42:" → 42
    # "Augustine, Confessions §aug_conf_05_008:" → (5, 8)
    # "Aurelius, Meditations §aur_08_xxxvii" → (8, 37) [convert roman]
    # "Didache 1" → 1 (from title)
    # "1 Clement V" → 5 (roman) — but title is "1 Clement V" with V as roman

    # Try title number
    m = re.search(r"§(\w+_(\d+)_(\d+))", title) or re.search(r"§(\w+_(\d+)_(\d+))", ref)
    if m:
        return (int(m.group(2)), int(m.group(3)))
    m = re.search(r"§\d*[_-]?(\d+)[_-](\w+)", title)
    if m:
        try: return (int(m.group(1)), _roman_to_int(m.group(2)))
        except: pass
    m = re.search(r"§(\d+)", title) or re.search(r"§(\d+)", ref)
    if m:
        return (0, int(m.group(1)))
    m = re.search(r"\b(\d+)\s*$", title)
    if m:
        return (0, int(m.group(1)))
    m = re.search(r"\b([IVXLCDM]+)\s*$", title)
    if m:
        try: return (0, _roman_to_int(m.group(1)))
        except: pass
    return (999, 999)


_ROMAN = {"I":1,"V":5,"X":10,"L":50,"C":100,"D":500,"M":1000}
def _roman_to_int(s: str) -> int:
    s = s.upper()
    if not all(ch in _ROMAN for ch in s): raise ValueError(s)
    total = 0; prev = 0
    for ch in reversed(s):
        v = _ROMAN[ch]
        if v < prev: total -= v
        else: total += v
        prev = v
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    # Group cards by box
    by_box = defaultdict(list)
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        box = c.get("box")
        if box in SEQUENTIAL_BOXES:
            by_box[box].append(c)

    counts = {"sequences": 0, "connections_created": 0, "skipped_exists": 0}
    for box, cards in by_box.items():
        cards.sort(key=_sort_key)
        if len(cards) < 2:
            continue
        counts["sequences"] += 1
        # Add next/prev connections
        for i, card in enumerate(cards):
            for direction, neighbor_i in [("next", i + 1), ("prev", i - 1)]:
                if neighbor_i < 0 or neighbor_i >= len(cards):
                    continue
                neighbor = cards[neighbor_i]
                seed = f"conn::{card['id']}::{neighbor['id']}::sequence::{direction}"
                cid = _make_card_id("connection", seed)
                cp = CARDS_DIR / f"{cid}.json"
                if cp.exists():
                    counts["skipped_exists"] += 1
                    continue
                conn = {
                    "id": cid,
                    "kind": "connection",
                    "title": f"{card.get('title','?')[:36]} → {neighbor.get('title','?')[:36]}",
                    "body": f"Sequential {direction} in {box}.",
                    "source": {
                        "label": "Sequential ordering within work",
                        "url": "",
                        "ref": box,
                        "authority_tier": "engine_derived",
                    },
                    "shelf": "connections",
                    "box": f"sequence_{box}",
                    "bands": ["sequence", direction, box],
                    "connections": [
                        {"to_card_id": card["id"], "relationship": "see_also"},
                        {"to_card_id": neighbor["id"], "relationship": "see_also"},
                    ],
                    "author": "engine",
                    "created_at": _now(),
                    "updated_at": _now(),
                    "visibility": "public",
                    "lifecycle_stage": "public",
                    "volatility": "permanent",
                    "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                    "extra": {
                        "left_card_id": card["id"],
                        "right_card_id": neighbor["id"],
                        "relationship_kind": "see_also",
                        "direction": direction,
                    },
                }
                conn["source_hash"] = _compute_source_hash(conn)
                if not args.dry_run:
                    cp.write_text(json.dumps(conn, indent=2), encoding="utf-8")
                counts["connections_created"] += 1

    print(f"=== Sequence linker ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"  sequences linked: {list(by_box.keys())}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
