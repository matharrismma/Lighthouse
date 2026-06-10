"""surface_memory_verses.py — Top memory verses as cards (LOOP 50).

Surfaces a curated list of the most-memorized Bible verses as individual
cards on shelf=codex/box=memory_verses. These are the verses every Christian
family should know by heart: John 3:16, Romans 8:28, Philippians 4:13, etc.

Authority tier = scripture. Verses Christ speaks directly get words_in_red.

Usage:
  python tools/surface_memory_verses.py
"""
from __future__ import annotations
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
VERSES = REPO / "data" / "bible_en" / "verses.jsonl"

# Curated list of memory verses — (book, chapter, verse[, words_in_red])
MEMORY_VERSES = [
    # Foundation / God / Trinity
    ("Genesis", 1, 1),
    ("Deuteronomy", 6, 4), ("Deuteronomy", 6, 5),
    ("Joshua", 1, 9),
    ("1 Samuel", 16, 7),
    ("2 Chronicles", 7, 14),
    # Psalms — load-bearing
    ("Psalms", 1, 1), ("Psalms", 19, 1), ("Psalms", 19, 14),
    ("Psalms", 23, 1), ("Psalms", 23, 4),
    ("Psalms", 27, 1), ("Psalms", 34, 18), ("Psalms", 46, 1), ("Psalms", 46, 10),
    ("Psalms", 51, 10), ("Psalms", 119, 11), ("Psalms", 119, 105),
    ("Psalms", 139, 14), ("Psalms", 145, 18),
    # Proverbs — wisdom
    ("Proverbs", 1, 7), ("Proverbs", 3, 5), ("Proverbs", 3, 6),
    ("Proverbs", 22, 6), ("Proverbs", 27, 17), ("Proverbs", 29, 25),
    # Isaiah
    ("Isaiah", 26, 3), ("Isaiah", 40, 31), ("Isaiah", 41, 10),
    ("Isaiah", 53, 5), ("Isaiah", 53, 6), ("Isaiah", 55, 8), ("Isaiah", 55, 11),
    # Jeremiah
    ("Jeremiah", 29, 11), ("Jeremiah", 31, 33),
    # Lamentations
    ("Lamentations", 3, 22), ("Lamentations", 3, 23),
    # Gospels — many words_in_red
    ("Matthew", 5, 3, True), ("Matthew", 5, 6, True), ("Matthew", 5, 8, True),
    ("Matthew", 5, 16, True), ("Matthew", 6, 33, True),
    ("Matthew", 7, 7, True), ("Matthew", 11, 28, True), ("Matthew", 11, 29, True),
    ("Matthew", 16, 24, True), ("Matthew", 22, 37, True), ("Matthew", 22, 39, True),
    ("Matthew", 28, 19, True), ("Matthew", 28, 20, True),
    ("Mark", 12, 30, True),
    ("Luke", 6, 31, True), ("Luke", 9, 23, True), ("Luke", 19, 10, True),
    ("John", 1, 1), ("John", 1, 14), ("John", 3, 16, True), ("John", 3, 17, True),
    ("John", 8, 12, True), ("John", 8, 32, True),
    ("John", 10, 10, True), ("John", 10, 27, True), ("John", 10, 28, True),
    ("John", 13, 34, True), ("John", 14, 1, True), ("John", 14, 6, True), ("John", 14, 27, True),
    ("John", 15, 5, True), ("John", 15, 13, True),
    ("John", 16, 33, True),
    # Acts
    ("Acts", 1, 8), ("Acts", 2, 38), ("Acts", 4, 12), ("Acts", 16, 31),
    # Romans
    ("Romans", 1, 16), ("Romans", 3, 23), ("Romans", 5, 1), ("Romans", 5, 8),
    ("Romans", 6, 23), ("Romans", 8, 1), ("Romans", 8, 28), ("Romans", 8, 38),
    ("Romans", 8, 39), ("Romans", 10, 9), ("Romans", 10, 13), ("Romans", 12, 1),
    ("Romans", 12, 2),
    # 1-2 Corinthians
    ("1 Corinthians", 10, 13), ("1 Corinthians", 10, 31),
    ("1 Corinthians", 13, 4), ("1 Corinthians", 13, 7), ("1 Corinthians", 13, 13),
    ("1 Corinthians", 15, 3), ("1 Corinthians", 15, 57), ("1 Corinthians", 15, 58),
    ("2 Corinthians", 4, 17), ("2 Corinthians", 5, 7), ("2 Corinthians", 5, 17),
    ("2 Corinthians", 5, 21), ("2 Corinthians", 12, 9),
    # Galatians
    ("Galatians", 2, 20), ("Galatians", 5, 22), ("Galatians", 5, 23), ("Galatians", 6, 9),
    # Ephesians
    ("Ephesians", 1, 7), ("Ephesians", 2, 8), ("Ephesians", 2, 9), ("Ephesians", 2, 10),
    ("Ephesians", 4, 32), ("Ephesians", 6, 10), ("Ephesians", 6, 11),
    # Philippians
    ("Philippians", 1, 6), ("Philippians", 1, 21),
    ("Philippians", 2, 5), ("Philippians", 2, 9), ("Philippians", 2, 10),
    ("Philippians", 3, 7), ("Philippians", 3, 10), ("Philippians", 3, 14),
    ("Philippians", 4, 4), ("Philippians", 4, 6), ("Philippians", 4, 7),
    ("Philippians", 4, 8), ("Philippians", 4, 11), ("Philippians", 4, 13), ("Philippians", 4, 19),
    # Colossians
    ("Colossians", 1, 16), ("Colossians", 1, 17), ("Colossians", 2, 9),
    ("Colossians", 3, 1), ("Colossians", 3, 2), ("Colossians", 3, 17), ("Colossians", 3, 23),
    # 1 Thessalonians
    ("1 Thessalonians", 4, 16), ("1 Thessalonians", 5, 16), ("1 Thessalonians", 5, 17), ("1 Thessalonians", 5, 18),
    # 2 Timothy
    ("2 Timothy", 1, 7), ("2 Timothy", 2, 15), ("2 Timothy", 3, 16), ("2 Timothy", 3, 17), ("2 Timothy", 4, 7),
    # Hebrews
    ("Hebrews", 4, 12), ("Hebrews", 4, 16), ("Hebrews", 9, 27), ("Hebrews", 10, 25),
    ("Hebrews", 11, 1), ("Hebrews", 11, 6), ("Hebrews", 12, 1), ("Hebrews", 12, 2),
    ("Hebrews", 13, 5), ("Hebrews", 13, 8),
    # James
    ("James", 1, 2), ("James", 1, 5), ("James", 1, 12), ("James", 1, 22),
    ("James", 4, 7), ("James", 4, 8), ("James", 4, 17), ("James", 5, 16),
    # 1 Peter
    ("1 Peter", 1, 3), ("1 Peter", 2, 9), ("1 Peter", 5, 7), ("1 Peter", 5, 8),
    # 1 John
    ("1 John", 1, 8), ("1 John", 1, 9),
    ("1 John", 3, 1), ("1 John", 3, 16),
    ("1 John", 4, 7), ("1 John", 4, 8), ("1 John", 4, 16), ("1 John", 4, 19), ("1 John", 4, 20),
    ("1 John", 5, 14),
    # Revelation
    ("Revelation", 3, 20), ("Revelation", 21, 4), ("Revelation", 22, 13),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    if not VERSES.exists():
        print(f"No verses at {VERSES}"); return

    # Build lookup: (book, ch, v) -> verse dict
    lookup = {}
    with VERSES.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                v = json.loads(line)
                lookup[(v["book"], v["chapter"], v["verse"])] = v
            except Exception:
                continue

    counts = {"created": 0, "skipped_exists": 0, "missing_verse": 0}
    for entry in MEMORY_VERSES:
        if len(entry) == 4:
            book, ch, v, is_wir = entry
        else:
            book, ch, v = entry
            is_wir = False
        verse = lookup.get((book, ch, v))
        if not verse:
            counts["missing_verse"] += 1
            continue
        ref = f"{book} {ch}:{v}"
        seed = f"memory_verse::{book}::{ch}::{v}"
        cid = _make_card_id("note", seed)
        cp = CARDS_DIR / f"{cid}.json"
        if cp.exists():
            counts["skipped_exists"] += 1
            continue
        card = {
            "id": cid,
            "kind": "note",
            "title": ref,
            "body": verse["text"],
            "source": {
                "label": f"World English Bible · {ref}",
                "url": f"/canon.html?ref={book.replace(' ', '%20')}%20{ch}",
                "ref": ref,
                "authority_tier": "words_in_red" if is_wir else "scripture",
            },
            "shelf": "codex",
            "box": "memory_verses",
            "bands": ["memory_verse", "scripture", book.lower().replace(" ", "_"), f"chapter_{ch}"],
            "connections": [],
            "author": "engine",
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "public",
            "lifecycle_stage": "featured",  # memory verses are featured by default
            "volatility": "permanent",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "featured_at": _now(),
        }
        card["source_hash"] = _compute_source_hash(card)
        cp.write_text(json.dumps(card, indent=2), encoding="utf-8")
        counts["created"] += 1

    print(f"=== Memory verses ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
