"""author_catechism_connections.py — Wire every catechism Q&A to its proof texts.

Walks `content/codex/catechism_westminster_shorter.json` and, for each Q's
proof_texts array, authors a connection card linking the catechism Q card to
the corresponding Bible book card. Idempotent — connections already in place
are skipped.

This is the densest layer of the graph. After this run, every catechism Q
has at least one connection to scripture, and every scripture book is hit by
the connections from the catechism Q&As that cite it. Walks land on the
proof-text relationship visibly, the way the Westminster Assembly intended
you to read them.

Usage:
    python tools/author_catechism_connections.py             # author missing
    python tools/author_catechism_connections.py --dry-run   # report only
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

CARDS_DIR = REPO / "data" / "cards"
CATECHISM_PATH = REPO / "content" / "codex" / "catechism_westminster_shorter.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_book_from_ref(ref: str) -> str | None:
    """Extract the Bible book name from a reference like 'Rom 11:36' or '1 Cor 10:31'.
    Returns the canonical book name as it appears in bible_books.json."""
    if not ref:
        return None
    # Normalize: strip leading number/space, match book names
    s = ref.strip()
    # Map common abbreviations to canonical names
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
    # Try longest matches first
    for alias in sorted(book_aliases.keys(), key=len, reverse=True):
        if s.startswith(alias):
            # Make sure the next char isn't alphabetic (avoid Gen matching Genesis already)
            after = s[len(alias):len(alias)+1]
            if not after or not after.isalpha():
                return book_aliases[alias]
    return None


def _load_card_id_index() -> dict:
    """Return {card_title -> card_id, ...} for all cards on disk."""
    out = {}
    if not CARDS_DIR.exists():
        return out
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
            t = c.get("title")
            if t:
                out[t] = c["id"]
        except Exception:
            continue
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Load catechism JSON
    cat = json.loads(CATECHISM_PATH.read_text(encoding="utf-8"))
    questions = cat.get("questions") or []

    # Build card index
    title_to_id = _load_card_id_index()

    # Import cards module helpers
    from api.cards import _make_card_id, _compute_source_hash, _save_card, VALID_RELATIONSHIPS  # type: ignore

    counts = {"attempted": 0, "created": 0, "skipped_exists": 0, "missing_book_card": 0, "unparseable_ref": 0, "missing_catechism_card": 0}

    for q in questions:
        qnum = q.get("q")
        cat_title = f"Westminster Shorter Q{qnum}"
        cat_id = title_to_id.get(cat_title)
        if not cat_id:
            counts["missing_catechism_card"] += 1
            continue

        # Collect distinct Bible books referenced in this Q's proof texts
        books_referenced = set()
        for pt in (q.get("proof_texts") or []):
            book = _parse_book_from_ref(pt)
            if not book:
                counts["unparseable_ref"] += 1
                continue
            books_referenced.add(book)

        # Author one connection per book (not per verse; otherwise we'd flood)
        for book in books_referenced:
            counts["attempted"] += 1
            book_id = title_to_id.get(book)
            if not book_id:
                counts["missing_book_card"] += 1
                continue

            seed = f"conn::{cat_id}::{book_id}::proof_text"
            conn_id = _make_card_id("connection", seed)
            if (CARDS_DIR / f"{conn_id}.json").exists():
                counts["skipped_exists"] += 1
                continue

            # The specific verses cited (for the body)
            refs_for_book = [pt for pt in (q.get("proof_texts") or []) if _parse_book_from_ref(pt) == book]
            explanation = f"Westminster Q{qnum} cites {book}: {'; '.join(refs_for_book)}."

            conn_card = {
                "id": conn_id,
                "kind": "connection",
                "title": f"WSC Q{qnum} ↔ {book}",
                "body": explanation,
                "source": {
                    "label": "Westminster Assembly 1647 proof text",
                    "url": "",
                    "ref": "; ".join(refs_for_book),
                    "authority_tier": "catechism",
                },
                "shelf": "connections",
                "box": "proof_text",
                "bands": ["proof_text", "westminster_shorter", book.lower().replace(" ", "_")],
                "connections": [
                    {"to_card_id": cat_id, "relationship": "see_also"},
                    {"to_card_id": book_id, "relationship": "see_also"},
                ],
                "author": "westminster_assembly",
                "created_at": _now(),
                "updated_at": _now(),
                "visibility": "public",
                "lifecycle_stage": "public",
                "volatility": "permanent",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                "extra": {
                    "left_card_id": cat_id,
                    "right_card_id": book_id,
                    "relationship_kind": "proof_text",
                    "explanation": explanation,
                    "bidirectional": True,
                    "verse_refs": refs_for_book,
                },
            }
            conn_card["source_hash"] = _compute_source_hash(conn_card)

            if args.dry_run:
                counts["created"] += 1
                continue

            _save_card(conn_card)
            # Append to both ends' connections
            for end_id, other_id in [(cat_id, book_id), (book_id, cat_id)]:
                p = CARDS_DIR / f"{end_id}.json"
                if p.exists():
                    try:
                        other = json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    conns = other.get("connections") or []
                    if not any(x.get("to_card_id") == other_id and x.get("via_connection_card_id") == conn_id for x in conns):
                        conns.append({"to_card_id": other_id, "relationship": "proof_text", "via_connection_card_id": conn_id})
                        other["connections"] = conns
                        other["updated_at"] = _now()
                        p.write_text(json.dumps(other, indent=2), encoding="utf-8")
            counts["created"] += 1

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Catechism connection authoring — {mode} ===")
    for k, v in counts.items():
        if v:
            print(f"  {k}: {v}")
    print(f"\nTotal cards on disk now: {len(list(CARDS_DIR.glob('*.json')))}")


if __name__ == "__main__":
    main()
