"""surface_easton.py — Easton's Bible Dictionary as cards (LOOP 36).

Surfaces entries from Matthew Easton's 1897 Illustrated Bible Dictionary.
3962 entries; we surface only those with non-trivial text (>= 100 chars) and
categorize by Easton's `category` field (concept / person / place / event).

Authority tier: external_aligned (Easton is widely respected but not creedal).

Usage:
  python tools/surface_easton.py
  python tools/surface_easton.py --max-entries 500   # cap for test runs
  python tools/surface_easton.py --min-chars 200     # filter trivial entries
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CARDS_DIR = REPO / "data" / "cards"
EASTON = REPO / "data" / "easton" / "entries.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-chars", type=int, default=200)
    parser.add_argument("--max-entries", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    if not EASTON.exists():
        print(f"No Easton entries at {EASTON}")
        return

    counts = {"surfaced": 0, "skipped_short": 0, "skipped_exists": 0, "by_category": {}}
    surfaced_count = 0
    with EASTON.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if args.max_entries and surfaced_count >= args.max_entries:
                break
            try:
                e = json.loads(line)
            except Exception:
                continue
            text = e.get("text", "")
            if len(text) < args.min_chars:
                counts["skipped_short"] += 1
                continue
            name = e.get("name", "")
            cat = e.get("category", "concept")
            seed = f"easton::{e.get('id') or name}"
            cid = _make_card_id("note", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            card = {
                "id": cid,
                "kind": "note",
                "title": f"Easton: {name}",
                "body": text[:3800] + ("…" if len(text) > 3800 else ""),
                "source": {
                    "label": "Matthew Easton, Illustrated Bible Dictionary (1897)",
                    "url": f"/encyclopedia.html?ref={name.replace(' ', '_')}",
                    "ref": name,
                    "authority_tier": "external_aligned",
                },
                "shelf": "dictionary",
                "box": "easton_" + cat,
                "bands": ["easton", "bible_dictionary", cat],
                "connections": [],
                "author": "engine",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            }
            card["source_hash"] = _compute_source_hash(card)
            if not args.dry_run:
                cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
            counts["surfaced"] += 1
            surfaced_count += 1
            counts["by_category"][cat] = counts["by_category"].get(cat, 0) + 1

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Easton's Bible Dictionary — {mode} ===")
    print(f"  surfaced: {counts['surfaced']}")
    print(f"  skipped_short: {counts['skipped_short']}")
    print(f"  skipped_exists: {counts['skipped_exists']}")
    print(f"  by category: {counts['by_category']}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
