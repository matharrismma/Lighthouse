"""scan_citations.py — Universal Bible-citation scanner (LOOP 45).

Walks any shelf of cards (default: dictionary, classics, patristics, codex/devotionals,
codex/sermons) and authors connection cards from those cards TO Bible-book cards
when an explicit book name appears in the body.

Uses the same regex patterns as author_patristics_connections.py but generalized.

Usage:
  python tools/scan_citations.py --shelf dictionary
  python tools/scan_citations.py --shelf classics
  python tools/scan_citations.py --shelf all
  python tools/scan_citations.py --shelf dictionary --max-cards 500
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

BOOK_PATTERNS = {
    "Genesis": r"\bGenesis\b",
    "Exodus": r"\bExodus\b",
    "Leviticus": r"\bLeviticus\b",
    "Numbers": r"\bbook of Numbers\b",
    "Deuteronomy": r"\bDeuteronomy\b",
    "Joshua": r"\bbook of Joshua\b",
    "Judges": r"\bbook of Judges\b",
    "Psalms": r"\b(?:Psalm|Psalms)\b",
    "Proverbs": r"\bProverbs\b",
    "Ecclesiastes": r"\bEcclesiastes\b",
    "Isaiah": r"\bIsaiah\b|\bIsaias\b",
    "Jeremiah": r"\bJeremiah\b|\bJeremias\b",
    "Lamentations": r"\bLamentations\b",
    "Ezekiel": r"\bEzekiel\b",
    "Daniel": r"\bbook of Daniel\b|\bprophet Daniel\b",
    "Hosea": r"\bHosea\b|\bHoseah\b",
    "Joel": r"\bbook of Joel\b|\bprophet Joel\b",
    "Amos": r"\bbook of Amos\b|\bprophet Amos\b",
    "Jonah": r"\bbook of Jonah\b|\bJonas\b",
    "Micah": r"\bMicah\b|\bMicheas\b",
    "Habakkuk": r"\bHabakkuk\b|\bHabacuc\b",
    "Zechariah": r"\bZechariah\b",
    "Malachi": r"\bMalachi\b|\bMalachy\b",
    "Matthew": r"\bGospel of Matthew\b|\bSaint Matthew\b|\bMatt\.\s*\d",
    "Mark": r"\bGospel of Mark\b|\bSaint Mark\b",
    "Luke": r"\bGospel of Luke\b|\bSaint Luke\b|\bLuke\b(?=\s+\d)",
    "John": r"\bGospel of John\b|\bSaint John\b|\bJohn\b(?=\s+\d|\s+the (?:Baptist|evangelist|apostle))",
    "Acts": r"\bActs of the Apostles\b|\bbook of Acts\b",
    "Romans": r"\bRomans\b(?!\s+(?:empire|emperor|legion|army|nation|people|world|catholic))",
    "1 Corinthians": r"\b(?:1|First)\s*Corinthians\b|\bfirst (?:epistle|letter) to the Corinthians\b",
    "2 Corinthians": r"\b(?:2|Second)\s*Corinthians\b",
    "Galatians": r"\bGalatians\b",
    "Ephesians": r"\bEphesians\b",
    "Philippians": r"\bPhilippians\b",
    "Colossians": r"\bColossians\b",
    "1 Thessalonians": r"\b(?:1|First)\s*Thessalonians\b",
    "2 Thessalonians": r"\b(?:2|Second)\s*Thessalonians\b",
    "1 Timothy": r"\b(?:1|First)\s*Timothy\b",
    "2 Timothy": r"\b(?:2|Second)\s*Timothy\b",
    "Titus": r"\b(?:to )?Titus\b",
    "Hebrews": r"\bHebrews\b|\bepistle to the Hebrews\b",
    "James": r"\b(?:Saint |St\. )?James\b(?=\s+(?:says|tells|writes|wrote|the apostle|chapter|\d|\.)|\b)",
    "1 Peter": r"\b(?:1|First)\s*Peter\b",
    "2 Peter": r"\b(?:2|Second)\s*Peter\b",
    "1 John": r"\b(?:1|First)\s*John\b",
    "Revelation": r"\b(?:Revelation|Apocalypse)\b",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shelf", choices=["dictionary", "classics", "patristics", "codex", "hymns", "maker", "recipes", "all"], default="all")
    parser.add_argument("--max-cards", type=int, default=None)
    args = parser.parse_args()

    from api.cards import _make_card_id, _compute_source_hash  # type: ignore

    # Build book-title → card_id lookup
    book_id = {}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            if (c.get("source") or {}).get("authority_tier") == "scripture" and c.get("title"):
                book_id[c["title"]] = c["id"]
        except Exception:
            continue

    counts = {"scanned": 0, "created": 0, "skipped_exists": 0, "no_books_found": 0}
    files = list(CARDS_DIR.glob("*.json"))
    for i, f in enumerate(files):
        if args.max_cards and counts["scanned"] >= args.max_cards:
            break
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        shelf = c.get("shelf")
        if args.shelf != "all" and shelf != args.shelf:
            continue
        if shelf in ("connections", "atlas") or c.get("kind") in ("connection", "walk", "search", "community_note"):
            continue
        # Don't link a scripture card to itself
        if (c.get("source") or {}).get("authority_tier") == "scripture":
            continue
        counts["scanned"] += 1
        text = c.get("body", "") + " " + c.get("title", "")
        books_found = set()
        for book, pat in BOOK_PATTERNS.items():
            if re.search(pat, text):
                books_found.add(book)
        if not books_found:
            counts["no_books_found"] += 1
            continue
        for book in books_found:
            target_id = book_id.get(book)
            if not target_id:
                continue
            seed = f"conn::{c['id']}::{target_id}::cites::auto"
            cid = _make_card_id("connection", seed)
            cp = CARDS_DIR / f"{cid}.json"
            if cp.exists():
                counts["skipped_exists"] += 1
                continue
            conn = {
                "id": cid,
                "kind": "connection",
                "title": f"{c.get('title','?')[:40]} cites {book}",
                "body": f"Card references {book}. Auto-detected via book-name match.",
                "source": {
                    "label": "Auto-detected citation",
                    "url": "",
                    "ref": "",
                    "authority_tier": "engine_derived",
                },
                "shelf": "connections",
                "box": f"{shelf}_cites_scripture",
                "bands": ["cites", "auto_detected", shelf, book.lower().replace(" ", "_")],
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
                    "explanation": f"Auto-detected: {book} named in {shelf} body.",
                    "bidirectional": True,
                },
            }
            conn["source_hash"] = _compute_source_hash(conn)
            cp.write_text(json.dumps(conn, indent=2), encoding="utf-8")
            # Append to both endpoints
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

    print(f"=== Citation scanner — shelf={args.shelf} ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
