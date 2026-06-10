"""author_patristics_connections.py — Link patristic cards to scripture.

Scans the body of every patristics-shelf card for Bible book mentions, and
authors a single `cites` connection per (patristic_card, book) pair. Conservative:
only fires when a book is explicitly named (not when "Romans" appears as a
proper noun in a wider sense like "Roman empire" — we guard with context tokens).

Run after surface_patristics.py.

Usage:
  python tools/author_patristics_connections.py
  python tools/author_patristics_connections.py --dry-run
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CARDS_DIR = REPO / "data" / "cards"

# Book detection patterns: each book → regex that matches the book name with
# scripture-citation context (verse numbers, "in <Book>", "the apostle says", etc.)
# Phase 1: simple book-name match in the body. Guards against false positives by
# requiring the book name in a context word that suggests a citation.
BOOK_PATTERNS = {
    "Genesis": r"\bGenesis\b",
    "Exodus": r"\bExodus\b",
    "Deuteronomy": r"\bDeuteronomy\b",
    "Psalms": r"\b(?:Psalm|Psalms)\b",
    "Proverbs": r"\bProverbs\b",
    "Isaiah": r"\bIsaiah\b|\bIsaias\b",
    "Jeremiah": r"\bJeremiah\b|\bJeremias\b",
    "Ezekiel": r"\bEzekiel\b",
    "Daniel": r"\bDaniel\b",
    "Matthew": r"\bMatthew\b|\bGospel of Matthew\b",
    "Mark": r"\bMark\b(?=\s+(?:says|tells|writes|wrote|records|chapter|\d))",
    "Luke": r"\bLuke\b(?=\s+(?:says|tells|writes|wrote|records|chapter|\d))",
    "John": r"\bJohn\b(?=\s+(?:says|tells|writes|wrote|records|chapter|the (?:Baptist|evangelist|apostle|beloved)|\d))",
    "Acts": r"\bActs\b(?:\s+of\s+the\s+Apostles)?",
    "Romans": r"\bRomans\b(?!\s+(?:empire|emperor|legion|army|nation|people|world))",
    "1 Corinthians": r"\b1\s*Corinthians\b|\bfirst (?:epistle|letter) to the Corinthians\b",
    "2 Corinthians": r"\b2\s*Corinthians\b|\bsecond (?:epistle|letter) to the Corinthians\b",
    "Galatians": r"\bGalatians\b",
    "Ephesians": r"\bEphesians\b",
    "Philippians": r"\bPhilippians\b",
    "Colossians": r"\bColossians\b",
    "1 Thessalonians": r"\b1\s*Thessalonians\b",
    "Hebrews": r"\bHebrews\b",
    "James": r"\bJames\b(?=\s+(?:says|tells|writes|wrote|the apostle|the (?:lord's )?brother|\d))",
    "1 Peter": r"\b1\s*Peter\b",
    "2 Peter": r"\b2\s*Peter\b",
    "1 John": r"\b1\s*John\b",
    "Revelation": r"\b(?:Revelation|Apocalypse)\b",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit-cards", type=int, default=None)
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    # Build {book_title -> book_card_id} for quick lookup
    book_id = {}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            t = c.get("title", "")
            if (c.get("source") or {}).get("authority_tier") == "scripture" and t:
                book_id[t] = c["id"]
        except Exception:
            continue

    counts = {"scanned": 0, "created": 0, "skipped_exists": 0, "no_books_found": 0, "would_create": 0}

    files = list(CARDS_DIR.glob("*.json"))
    for i, f in enumerate(files):
        if args.limit_cards and i >= args.limit_cards:
            break
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("shelf") != "patristics":
            continue
        counts["scanned"] += 1
        body = c.get("body", "") + " " + c.get("title", "")
        books_found = set()
        for book, pat in BOOK_PATTERNS.items():
            if re.search(pat, body):
                books_found.add(book)
        if not books_found:
            counts["no_books_found"] += 1
            continue
        for book in books_found:
            target_id = book_id.get(book)
            if not target_id:
                continue
            seed = f"conn::{c['id']}::{target_id}::cites"
            cid = _make_card_id("connection", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            conn = {
                "id": cid,
                "kind": "connection",
                "title": f"{c.get('title', '?')[:40]} cites {book}",
                "body": f"Patristic text references {book}. Detected via name match in the chapter body.",
                "source": {
                    "label": "Auto-detected citation",
                    "url": "",
                    "ref": "",
                    "authority_tier": "engine_derived",
                },
                "shelf": "connections",
                "box": "patristic_cites_scripture",
                "bands": ["cites", "patristics", book.lower().replace(" ", "_"), "auto_detected"],
                "connections": [
                    {"to_card_id": c["id"], "relationship": "see_also"},
                    {"to_card_id": target_id, "relationship": "see_also"},
                ],
                "author": "engine",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "stable",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                "extra": {
                    "left_card_id": c["id"],
                    "right_card_id": target_id,
                    "relationship_kind": "cites",
                    "explanation": f"Auto-detected: {book} named in patristic body.",
                    "bidirectional": True,
                },
            }
            conn["source_hash"] = _compute_source_hash(conn)
            if args.dry_run:
                counts["would_create"] += 1
                continue
            cp.write_text(json.dumps(conn, indent=2), encoding="utf-8")
            # Append to both endpoints' connections
            for end_id, other_id in [(c["id"], target_id), (target_id, c["id"])]:
                pp = CARDS_DIR / f"{end_id}.json"
                if pp.exists():
                    try:
                        other = json.loads(pp.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    conns = other.get("connections") or []
                    if not any(x.get("via_connection_card_id") == cid for x in conns):
                        conns.append({"to_card_id": other_id, "relationship": "cites", "via_connection_card_id": cid})
                        other["connections"] = conns
                        other["updated_at"] = _now()
                        pp.write_text(json.dumps(other, indent=2), encoding="utf-8")
            counts["created"] += 1

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Patristics→Scripture citation authoring — {mode} ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
