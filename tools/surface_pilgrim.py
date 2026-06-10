"""surface_pilgrim.py — Pilgrim's Progress as cards (LOOP 35).

Surfaces substantial sections of John Bunyan's Pilgrim's Progress as cards.
Sections under 500 chars are skipped (mostly fragments / titles / metadata).
Sections >= 1000 chars become "rich" cards; 500-999 become "passage" cards.

The card title uses a sensible excerpt rather than the noisy first-line title
in the source JSONL. Scripture refs (when present) become bands.

Usage:
  python tools/surface_pilgrim.py                       # write cards
  python tools/surface_pilgrim.py --min-chars 1000      # only the longest
  python tools/surface_pilgrim.py --dry-run             # report only
"""
from __future__ import annotations
import argparse
import json
import re
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
SECTIONS_PATH = REPO / "data" / "pilgrim" / "sections.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _smart_title(text: str, section_n: int) -> str:
    """Build a readable title from the first meaningful clause."""
    # Strip leading number/punctuation
    t = re.sub(r"^\d+\.\s*", "", text).strip()
    # Take first sentence (or first 70 chars)
    sentence = re.split(r"(?<=[.!?])\s+", t, maxsplit=1)[0]
    if len(sentence) > 90:
        sentence = sentence[:87] + "..."
    return f"Pilgrim's Progress §{section_n}: {sentence}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-chars", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    if not SECTIONS_PATH.exists():
        print(f"No sections.jsonl at {SECTIONS_PATH}")
        return

    counts = {"surfaced": 0, "skipped_short": 0, "skipped_exists": 0}
    with SECTIONS_PATH.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                s = json.loads(line)
            except Exception:
                continue
            text = s.get("text", "")
            if len(text) < args.min_chars:
                counts["skipped_short"] += 1
                continue
            section_n = s.get("section", i + 1)
            scripture_refs = s.get("scripture_refs") or []
            seed = f"pilgrim::{section_n}"
            cid = _make_card_id("note", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            title = _smart_title(text, section_n)
            card = {
                "id": cid,
                "kind": "note",
                "title": title,
                "body": text[:3800] + ("…" if len(text) > 3800 else ""),
                "source": {
                    "label": "John Bunyan, Pilgrim's Progress (1678)",
                    "url": f"/canon.html?ref=pilgrim_{section_n:03d}",
                    "ref": f"§{section_n}",
                    "authority_tier": "external_aligned",
                },
                "shelf": "classics",
                "box": "pilgrims_progress",
                "bands": (["pilgrim", "bunyan", "allegory"] + list(scripture_refs)[:5])[:12],
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

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Pilgrim's Progress surfacing — {mode} ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
