"""author_confessional_connections.py — Generalized connection authoring.

Wires every Heidelberg Q&A and every 1689 LBCF chapter to its proof-text Bible
books. Same pattern as author_catechism_connections.py (which handles WSC).

Idempotent — re-runs skip existing.

Usage:
  python tools/author_confessional_connections.py --source hc
  python tools/author_confessional_connections.py --source lbcf
  python tools/author_confessional_connections.py --source all
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_book_from_ref(ref: str) -> str | None:
    if not ref:
        return None
    s = ref.strip()
    book_aliases = {
        "Gen": "Genesis", "Ex": "Exodus", "Exo": "Exodus", "Lev": "Leviticus",
        "Num": "Numbers", "Deut": "Deuteronomy", "Josh": "Joshua",
        "Judg": "Judges", "Ruth": "Ruth", "1 Sam": "1 Samuel", "2 Sam": "2 Samuel",
        "1 Kings": "1 Kings", "2 Kings": "2 Kings", "1 Kgs": "1 Kings", "2 Kgs": "2 Kings",
        "1 Chr": "1 Chronicles", "2 Chr": "2 Chronicles",
        "Ezra": "Ezra", "Neh": "Nehemiah", "Esth": "Esther", "Esther": "Esther",
        "Job": "Job", "Ps": "Psalms", "Psa": "Psalms", "Psalm": "Psalms", "Psalms": "Psalms",
        "Prov": "Proverbs", "Eccl": "Ecclesiastes", "Song": "Song of Solomon",
        "Isa": "Isaiah", "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel",
        "Dan": "Daniel", "Hos": "Hosea", "Joel": "Joel", "Amos": "Amos",
        "Obad": "Obadiah", "Jon": "Jonah", "Mic": "Micah", "Nah": "Nahum",
        "Hab": "Habakkuk", "Zeph": "Zephaniah", "Hag": "Haggai", "Zech": "Zechariah",
        "Mal": "Malachi",
        "Matt": "Matthew", "Mt": "Matthew", "Mk": "Mark", "Mark": "Mark",
        "Lk": "Luke", "Luke": "Luke", "Jn": "John", "John": "John",
        "Acts": "Acts",
        "Rom": "Romans", "Romans": "Romans",
        "1 Cor": "1 Corinthians", "2 Cor": "2 Corinthians",
        "Gal": "Galatians", "Eph": "Ephesians", "Phil": "Philippians",
        "Col": "Colossians",
        "1 Thess": "1 Thessalonians", "2 Thess": "2 Thessalonians",
        "1 Tim": "1 Timothy", "2 Tim": "2 Timothy",
        "Titus": "Titus", "Phlm": "Philemon",
        "Heb": "Hebrews", "Jas": "James", "James": "James",
        "1 Pet": "1 Peter", "2 Pet": "2 Peter",
        "1 John": "1 John", "2 John": "2 John", "3 John": "3 John",
        "Jude": "Jude", "Rev": "Revelation",
    }
    for alias in sorted(book_aliases.keys(), key=len, reverse=True):
        if s.startswith(alias):
            after = s[len(alias):len(alias)+1]
            if not after or not after.isalpha():
                return book_aliases[alias]
    return None


def _title_to_id() -> dict:
    out = {}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            t = c.get("title")
            if t:
                out[t] = c["id"]
        except Exception:
            continue
    return out


def author_for_source(source: str) -> dict:
    """source: 'hc' or 'lbcf'. Returns counts dict."""
    from api.cards import _make_card_id, _compute_source_hash  # type: ignore
    title_idx = _title_to_id()

    if source == "hc":
        json_path = REPO / "content" / "codex" / "catechism_heidelberg.json"
        items_key = "questions"
        item_card_prefix = lambda q: f"Heidelberg Q{q.get('q')}"
        seed_prefix = "hc"
        tradition_band = "heidelberg"
        author_field = "heidelberg_assembly"
        relationship = "proof_text"
        authority_tier_on_card = "catechism"
    elif source == "lbcf":
        json_path = REPO / "content" / "codex" / "confession_1689_baptist.json"
        items_key = "chapters"
        item_card_prefix = lambda ch: f"1689 LBCF ch. {ch.get('n')}: {ch.get('title','')}"
        seed_prefix = "lbcf"
        tradition_band = "1689_baptist"
        author_field = "particular_baptists_1689"
        relationship = "proof_text"
        authority_tier_on_card = "creed"
    else:
        return {"error": f"Unknown source: {source}"}

    if not json_path.exists():
        return {"error": f"No file at {json_path}"}

    j = json.loads(json_path.read_text(encoding="utf-8"))
    items = j.get(items_key) or []

    counts = {"attempted": 0, "created": 0, "skipped_exists": 0, "missing_book_card": 0, "missing_item_card": 0}

    for item in items:
        item_title = item_card_prefix(item)
        item_id = title_idx.get(item_title)
        if not item_id:
            counts["missing_item_card"] += 1
            continue
        books_in_item = set()
        for pt in (item.get("proof_texts") or []):
            book = _parse_book_from_ref(pt)
            if book:
                books_in_item.add(book)
        for book in books_in_item:
            counts["attempted"] += 1
            book_id = title_idx.get(book)
            if not book_id:
                counts["missing_book_card"] += 1
                continue
            seed = f"conn::{item_id}::{book_id}::{relationship}::{seed_prefix}"
            conn_id = _make_card_id("connection", seed)
            if (CARDS_DIR / f"{conn_id}.json").exists():
                counts["skipped_exists"] += 1
                continue
            refs_for_book = [pt for pt in (item.get("proof_texts") or []) if _parse_book_from_ref(pt) == book]
            short_title = item_title if len(item_title) < 40 else item_title[:37] + "..."
            conn = {
                "id": conn_id,
                "kind": "connection",
                "title": f"{short_title} ↔ {book}",
                "body": f"{item_title} cites {book}: {'; '.join(refs_for_book)}.",
                "source": {
                    "label": j.get("source", source.upper()),
                    "url": "",
                    "ref": "; ".join(refs_for_book),
                    "authority_tier": authority_tier_on_card,
                },
                "shelf": "connections",
                "box": "proof_text",
                "bands": ["proof_text", tradition_band, book.lower().replace(" ", "_")],
                "connections": [
                    {"to_card_id": item_id, "relationship": "see_also"},
                    {"to_card_id": book_id, "relationship": "see_also"},
                ],
                "author": author_field,
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                "extra": {
                    "left_card_id": item_id,
                    "right_card_id": book_id,
                    "relationship_kind": relationship,
                    "explanation": f"{item_title} → {book}",
                    "bidirectional": True,
                    "verse_refs": refs_for_book,
                },
            }
            conn["source_hash"] = _compute_source_hash(conn)
            (CARDS_DIR / f"{conn_id}.json").write_text(json.dumps(conn, indent=2), encoding="utf-8")
            # Update both endpoints
            for end_id, other_id in [(item_id, book_id), (book_id, item_id)]:
                pp = CARDS_DIR / f"{end_id}.json"
                if pp.exists():
                    try:
                        other = json.loads(pp.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    conns = other.get("connections") or []
                    if not any(x.get("via_connection_card_id") == conn_id for x in conns):
                        conns.append({"to_card_id": other_id, "relationship": relationship, "via_connection_card_id": conn_id})
                        other["connections"] = conns
                        other["updated_at"] = _now()
                        pp.write_text(json.dumps(other, indent=2), encoding="utf-8")
            counts["created"] += 1

    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["hc", "lbcf", "all"], default="all")
    args = parser.parse_args()

    sources = [args.source] if args.source != "all" else ["hc", "lbcf"]
    for src in sources:
        print(f"\n=== Authoring connections for {src.upper()} ===")
        counts = author_for_source(src)
        for k, v in counts.items():
            if v:
                print(f"  {k}: {v}")

    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
