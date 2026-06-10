"""surface_bible_chapters.py — Key Bible chapters as cards (LOOP 48).

Walks data/bible_en/verses.jsonl, aggregates verses per (book, chapter), and
authors a chapter-level scripture card. Only authors chapters in the curated
list of high-leverage doctrinal chapters by default. Use --all to author
every chapter (warning: ~1200 cards across the canon).

The chapter cards complement the existing book-level cards and the 150 Psalm
cards — adding granularity at the chapters most-quoted in catechism, creed,
patristic, and confession substrate.

Usage:
  python tools/surface_bible_chapters.py                  # curated 30+ chapters
  python tools/surface_bible_chapters.py --all            # every chapter
"""
from __future__ import annotations
import argparse
import json
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
VERSES = REPO / "data" / "bible_en" / "verses.jsonl"

# Hand-picked load-bearing chapters
CURATED = [
    ("Genesis", 1), ("Genesis", 2), ("Genesis", 3), ("Genesis", 15), ("Genesis", 22),
    ("Exodus", 3), ("Exodus", 12), ("Exodus", 20),
    ("Leviticus", 16),
    ("Deuteronomy", 6),
    ("2 Samuel", 7),
    ("Isaiah", 6), ("Isaiah", 53), ("Isaiah", 55),
    ("Jeremiah", 31),
    ("Ezekiel", 36),
    ("Daniel", 7),
    ("Matthew", 5), ("Matthew", 6), ("Matthew", 7),
    ("Matthew", 28),
    ("Mark", 8),
    ("Luke", 1), ("Luke", 15),
    ("John", 1), ("John", 3), ("John", 6), ("John", 10), ("John", 14), ("John", 15), ("John", 17),
    ("Acts", 2), ("Acts", 17),
    ("Romans", 1), ("Romans", 3), ("Romans", 5), ("Romans", 6), ("Romans", 8), ("Romans", 10), ("Romans", 12),
    ("1 Corinthians", 1), ("1 Corinthians", 13), ("1 Corinthians", 15),
    ("2 Corinthians", 5),
    ("Galatians", 2), ("Galatians", 3), ("Galatians", 5),
    ("Ephesians", 1), ("Ephesians", 2), ("Ephesians", 6),
    ("Philippians", 2), ("Philippians", 3),
    ("Colossians", 1), ("Colossians", 3),
    ("1 Thessalonians", 4),
    ("1 Timothy", 3),
    ("2 Timothy", 3),
    ("Titus", 3),
    ("Hebrews", 1), ("Hebrews", 4), ("Hebrews", 9), ("Hebrews", 10), ("Hebrews", 11), ("Hebrews", 12),
    ("James", 1), ("James", 2),
    ("1 Peter", 1), ("1 Peter", 2),
    ("1 John", 1), ("1 John", 3), ("1 John", 4),
    ("Revelation", 1), ("Revelation", 5), ("Revelation", 21), ("Revelation", 22),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="Author every chapter (~1200 cards)")
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    if not VERSES.exists():
        print(f"No verses at {VERSES}"); return

    # Aggregate verses by (book, chapter)
    by_chapter = defaultdict(list)
    with VERSES.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                v = json.loads(line)
            except Exception:
                continue
            by_chapter[(v["book"], v["chapter"])].append(v)

    targets = list(by_chapter.keys()) if args.all else CURATED

    counts = {"created": 0, "skipped_exists": 0, "missing_chapter": 0}
    for book, ch in targets:
        verses = by_chapter.get((book, ch))
        if not verses:
            counts["missing_chapter"] += 1
            continue
        verses.sort(key=lambda v: v["verse"])
        body = "\n".join(f"{v['verse']}. {v['text']}" for v in verses)
        seed = f"bible_chapter::{book}::{ch}"
        cid = _make_card_id("note", seed)
        cp = CARDS_DIR / f"{cid}.json"
        if cp.exists():
            counts["skipped_exists"] += 1
            continue
        title = f"{book} {ch}"
        card = {
            "id": cid,
            "kind": "note",
            "title": title,
            "body": body[:3800] + ("…" if len(body) > 3800 else ""),
            "source": {
                "label": f"World English Bible · {title}",
                "url": f"/canon.html?ref={book.replace(' ', '%20')}%20{ch}",
                "ref": title,
                "authority_tier": "scripture",
            },
            "shelf": "codex",
            "box": "bible_chapters",
            "bands": ["scripture", "bible_chapter", book.lower().replace(" ", "_"), f"chapter_{ch}"],
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
        cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
        counts["created"] += 1

    print(f"=== Bible chapters surfacing ({'all' if args.all else 'curated'}) ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
