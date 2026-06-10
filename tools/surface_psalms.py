"""surface_psalms.py — All 150 Psalms as cards (LOOP 42).

Per-chapter (per-Psalm) cards. Authority tier = scripture (the highest tier
for non-Words-in-Red text). The existing Bible-book card for "Psalms" stays
as a parent; these are the chapter-level granularity below it.

Usage:
  python tools/surface_psalms.py
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
PSALMS_PATH = REPO / "data" / "psalms" / "chapters.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    if not PSALMS_PATH.exists():
        print(f"No psalms data at {PSALMS_PATH}")
        return

    counts = {"surfaced": 0, "skipped_exists": 0}
    with PSALMS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                p = json.loads(line)
            except Exception:
                continue
            ch = p.get("chapter")
            if not ch:
                continue
            title_short = p.get("title", "")
            seed = f"psalm::{ch}"
            cid = _make_card_id("note", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            text = p.get("text", "")
            card = {
                "id": cid,
                "kind": "note",
                "title": f"Psalm {ch}" + (f" — {title_short}" if title_short else ""),
                "body": text[:3800] + ("…" if len(text) > 3800 else ""),
                "source": {
                    "label": f"Psalm {ch}",
                    "url": f"/canon.html?ref=Psalms%20{ch}",
                    "ref": f"Psalms {ch}",
                    "authority_tier": "scripture",
                },
                "shelf": "codex",
                "box": "psalms_individual",
                "bands": ["psalms", f"psalm_{ch:03d}", "scripture"] + ([title_short.lower().replace(" ", "_")] if title_short else []),
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

    print(f"=== Psalms surfacing ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
