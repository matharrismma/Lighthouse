"""
triangulation/lookup.py — Layer 0 WORD resolver

Resolves scripture reference strings to:
  - WEB text (locked English)
  - Strong's numbers for key terms
  - Original language word definitions

Usage:
    # From Python
    from triangulation.lookup import SourceLayer
    src = SourceLayer()
    result = src.lookup("Jn3:16")
    result = src.lookup("Gen1:1")
    result = src.search("living water")
    result = src.word_range("G26")     # all verses using agape (love)

    # From command line
    python -m triangulation.lookup --ref Jn3:16
    python -m triangulation.lookup --ref Gen1:1
    python -m triangulation.lookup --search "living water"
    python -m triangulation.lookup --word G26
    python -m triangulation.lookup --word H430     # Elohim
"""

from __future__ import annotations

import json
import re
import sqlite3
import argparse
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent

WEB_DB = ROOT / "web" / "web.db"
STRONGS_H = ROOT / "original" / "lexicon" / "strongs_hebrew.json"
STRONGS_G = ROOT / "original" / "lexicon" / "strongs_greek.json"

# ---------------------------------------------------------------------------
# Book name → book number (1–66) + testament
# Covers common abbreviations used in ref strings
# ---------------------------------------------------------------------------
BOOK_MAP: dict[str, tuple[int, str]] = {
    # OT
    "gen": (1, "OT"), "ge": (1, "OT"), "genesis": (1, "OT"),
    "exo": (2, "OT"), "ex": (2, "OT"), "exodus": (2, "OT"),
    "lev": (3, "OT"), "le": (3, "OT"), "leviticus": (3, "OT"),
    "num": (4, "OT"), "nu": (4, "OT"), "numbers": (4, "OT"),
    "deu": (5, "OT"), "de": (5, "OT"), "deut": (5, "OT"), "deuteronomy": (5, "OT"),
    "jos": (6, "OT"), "josh": (6, "OT"), "joshua": (6, "OT"),
    "jdg": (7, "OT"), "judg": (7, "OT"), "judges": (7, "OT"),
    "rut": (8, "OT"), "ruth": (8, "OT"),
    "1sa": (9, "OT"), "1sam": (9, "OT"), "1samuel": (9, "OT"),
    "2sa": (10, "OT"), "2sam": (10, "OT"), "2samuel": (10, "OT"),
    "1ki": (11, "OT"), "1kings": (11, "OT"),
    "2ki": (12, "OT"), "2kings": (12, "OT"),
    "1ch": (13, "OT"), "1chr": (13, "OT"), "1chronicles": (13, "OT"),
    "2ch": (14, "OT"), "2chr": (14, "OT"), "2chronicles": (14, "OT"),
    "ezr": (15, "OT"), "ezra": (15, "OT"),
    "neh": (16, "OT"), "nehemiah": (16, "OT"),
    "est": (17, "OT"), "esth": (17, "OT"), "esther": (17, "OT"),
    "job": (18, "OT"),
    "psa": (19, "OT"), "ps": (19, "OT"), "psalm": (19, "OT"), "psalms": (19, "OT"),
    "pro": (20, "OT"), "pr": (20, "OT"), "prov": (20, "OT"), "proverbs": (20, "OT"),
    "ecc": (21, "OT"), "eccl": (21, "OT"), "ecclesiastes": (21, "OT"),
    "sng": (22, "OT"), "song": (22, "OT"), "ss": (22, "OT"),
    "isa": (23, "OT"), "is": (23, "OT"), "isaiah": (23, "OT"),
    "jer": (24, "OT"), "jeremiah": (24, "OT"),
    "lam": (25, "OT"), "lamentations": (25, "OT"),
    "ezk": (26, "OT"), "eze": (26, "OT"), "ezek": (26, "OT"), "ezekiel": (26, "OT"),
    "dan": (27, "OT"), "da": (27, "OT"), "daniel": (27, "OT"),
    "hos": (28, "OT"), "hosea": (28, "OT"),
    "joe": (29, "OT"), "joel": (29, "OT"),
    "amo": (30, "OT"), "am": (30, "OT"), "amos": (30, "OT"),
    "oba": (31, "OT"), "ob": (31, "OT"), "obadiah": (31, "OT"),
    "jon": (32, "OT"), "jonah": (32, "OT"),
    "mic": (33, "OT"), "micah": (33, "OT"),
    "nah": (34, "OT"), "na": (34, "OT"), "nahum": (34, "OT"),
    "hab": (35, "OT"), "habakkuk": (35, "OT"),
    "zep": (36, "OT"), "zeph": (36, "OT"), "zephaniah": (36, "OT"),
    "hag": (37, "OT"), "haggai": (37, "OT"),
    "zec": (38, "OT"), "zech": (38, "OT"), "zechariah": (38, "OT"),
    "mal": (39, "OT"), "malachi": (39, "OT"),
    # NT
    "mat": (40, "NT"), "mt": (40, "NT"), "matt": (40, "NT"), "matthew": (40, "NT"),
    "mrk": (41, "NT"), "mk": (41, "NT"), "mar": (41, "NT"), "mark": (41, "NT"),
    "luk": (42, "NT"), "lk": (42, "NT"), "luke": (42, "NT"),
    "jhn": (43, "NT"), "jn": (43, "NT"), "joh": (43, "NT"), "john": (43, "NT"),
    "act": (44, "NT"), "ac": (44, "NT"), "acts": (44, "NT"),
    "rom": (45, "NT"), "ro": (45, "NT"), "romans": (45, "NT"),
    "1co": (46, "NT"), "1cor": (46, "NT"), "1corinthians": (46, "NT"),
    "2co": (47, "NT"), "2cor": (47, "NT"), "2corinthians": (47, "NT"),
    "gal": (48, "NT"), "galatians": (48, "NT"),
    "eph": (49, "NT"), "ephesians": (49, "NT"),
    "php": (50, "NT"), "phi": (50, "NT"), "phil": (50, "NT"), "philippians": (50, "NT"),
    "col": (51, "NT"), "colossians": (51, "NT"),
    "1th": (52, "NT"), "1thes": (52, "NT"), "1thessalonians": (52, "NT"),
    "2th": (53, "NT"), "2thes": (53, "NT"), "2thessalonians": (53, "NT"),
    "1ti": (54, "NT"), "1tim": (54, "NT"), "1timothy": (54, "NT"),
    "2ti": (55, "NT"), "2tim": (55, "NT"), "2timothy": (55, "NT"),
    "tit": (56, "NT"), "titus": (56, "NT"),
    "phm": (57, "NT"), "phlm": (57, "NT"), "philemon": (57, "NT"),
    "heb": (58, "NT"), "hebrews": (58, "NT"),
    "jas": (59, "NT"), "jam": (59, "NT"), "james": (59, "NT"),
    "1pe": (60, "NT"), "1pet": (60, "NT"), "1peter": (60, "NT"),
    "2pe": (61, "NT"), "2pet": (61, "NT"), "2peter": (61, "NT"),
    "1jn": (62, "NT"), "1john": (62, "NT"),
    "2jn": (63, "NT"), "2john": (63, "NT"),
    "3jn": (64, "NT"), "3john": (64, "NT"),
    "jud": (65, "NT"), "jude": (65, "NT"),
    "rev": (66, "NT"), "re": (66, "NT"), "revelation": (66, "NT"),
}

BOOK_NAMES = {
    1: "Genesis", 2: "Exodus", 3: "Leviticus", 4: "Numbers", 5: "Deuteronomy",
    6: "Joshua", 7: "Judges", 8: "Ruth", 9: "1 Samuel", 10: "2 Samuel",
    11: "1 Kings", 12: "2 Kings", 13: "1 Chronicles", 14: "2 Chronicles",
    15: "Ezra", 16: "Nehemiah", 17: "Esther", 18: "Job", 19: "Psalms",
    20: "Proverbs", 21: "Ecclesiastes", 22: "Song of Solomon", 23: "Isaiah",
    24: "Jeremiah", 25: "Lamentations", 26: "Ezekiel", 27: "Daniel",
    28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadiah", 32: "Jonah",
    33: "Micah", 34: "Nahum", 35: "Habakkuk", 36: "Zephaniah", 37: "Haggai",
    38: "Zechariah", 39: "Malachi",
    40: "Matthew", 41: "Mark", 42: "Luke", 43: "John", 44: "Acts",
    45: "Romans", 46: "1 Corinthians", 47: "2 Corinthians", 48: "Galatians",
    49: "Ephesians", 50: "Philippians", 51: "Colossians",
    52: "1 Thessalonians", 53: "2 Thessalonians", 54: "1 Timothy",
    55: "2 Timothy", 56: "Titus", 57: "Philemon", 58: "Hebrews",
    59: "James", 60: "1 Peter", 61: "2 Peter",
    62: "1 John", 63: "2 John", 64: "3 John", 65: "Jude", 66: "Revelation",
}


def _parse_ref(ref: str) -> Optional[tuple[int, int, int]]:
    """
    Parse a ref string like "Jn3:16", "Gen1:1", "Pr4:23", "1Co13:4"
    Returns (book_number, chapter, verse) or None if unparseable.
    """
    ref = ref.strip()
    # Pattern: optional leading digit + book name + chapter + ":" + verse
    m = re.match(r"^(\d?[A-Za-z]+)[\s.]?(\d+):(\d+)$", ref)
    if not m:
        return None
    book_str = m.group(1).lower()
    chapter = int(m.group(2))
    verse = int(m.group(3))
    entry = BOOK_MAP.get(book_str)
    if not entry:
        return None
    return entry[0], chapter, verse


class SourceLayer:
    """
    Interface to the Layer 0 WORD sources.

    Lazily opens SQLite and JSON files on first use.
    Falls back gracefully if sources have not been fetched yet.
    """

    def __init__(self):
        self._db: Optional[sqlite3.Connection] = None
        self._h: Optional[dict] = None
        self._g: Optional[dict] = None

    # ------------------------------------------------------------------
    # Internal accessors
    # ------------------------------------------------------------------

    def _get_db(self) -> Optional[sqlite3.Connection]:
        if self._db is not None:
            return self._db
        if not WEB_DB.exists():
            return None
        self._db = sqlite3.connect(WEB_DB)
        return self._db

    def _get_strongs(self, testament: str) -> Optional[dict]:
        if testament == "OT":
            if self._h is None and STRONGS_H.exists():
                with open(STRONGS_H, encoding="utf-8") as f:
                    self._h = json.load(f)
            return self._h
        else:
            if self._g is None and STRONGS_G.exists():
                with open(STRONGS_G, encoding="utf-8") as f:
                    self._g = json.load(f)
            return self._g

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def lookup(self, ref: str) -> dict:
        """
        Resolve a ref string to WEB text.

        Returns:
            {
                "ref":        "Jn3:16",
                "book":       "John",
                "chapter":    3,
                "verse":      16,
                "testament":  "NT",
                "web_text":   "For God so loved...",
                "status":     "ok" | "not_found" | "source_missing",
            }
        """
        parsed = _parse_ref(ref)
        if parsed is None:
            return {"ref": ref, "status": "parse_error",
                    "detail": f"Could not parse '{ref}'. Try format: Jn3:16"}

        book_num, chapter, verse = parsed
        testament = BOOK_MAP.get(ref.strip().split(":")[0].lower().rstrip("0123456789"), ("?", "?"))[1]
        # re-derive testament cleanly
        for k, v in BOOK_MAP.items():
            if v[0] == book_num:
                testament = v[1]
                break

        db = self._get_db()
        if db is None:
            return {
                "ref": ref,
                "book": BOOK_NAMES.get(book_num, "Unknown"),
                "chapter": chapter,
                "verse": verse,
                "testament": testament,
                "status": "source_missing",
                "detail": "WEB SQLite not found. Run: python fetch_sources.py",
            }

        row = db.execute(
            "SELECT t FROM t_web WHERE b=? AND c=? AND v=?",
            (book_num, chapter, verse)
        ).fetchone()

        if row is None:
            return {
                "ref": ref,
                "book": BOOK_NAMES.get(book_num, "Unknown"),
                "chapter": chapter,
                "verse": verse,
                "testament": testament,
                "status": "not_found",
            }

        return {
            "ref": ref,
            "book": BOOK_NAMES.get(book_num, "Unknown"),
            "chapter": chapter,
            "verse": verse,
            "testament": testament,
            "web_text": row[0],
            "status": "ok",
            "layer": "WEB (locked English)",
            "note": "Triangulate key terms via word_range() for original language meaning.",
        }

    def lookup_strongs(self, strongs_num: str) -> dict:
        """
        Look up a Strong's number (e.g. "G26", "H430").

        Returns the dictionary entry: word, transliteration, definition, usage.
        """
        strongs_num = strongs_num.strip().upper()
        prefix = strongs_num[0]
        key = strongs_num[1:].lstrip("0") or "0"

        if prefix == "H":
            lex = self._get_strongs("OT")
        elif prefix == "G":
            lex = self._get_strongs("NT")
        else:
            return {"strongs": strongs_num, "status": "invalid_prefix",
                    "detail": "Use H### for Hebrew, G### for Greek"}

        if lex is None:
            return {
                "strongs": strongs_num,
                "status": "source_missing",
                "detail": f"Lexicon not found. Run: python fetch_sources.py",
            }

        # openscriptures format uses zero-padded keys
        for pad in (key, key.zfill(4), key.zfill(5)):
            full_key = prefix + pad
            if full_key in lex:
                entry = lex[full_key]
                return {
                    "strongs": strongs_num,
                    "word": entry.get("lemma", entry.get("word", "")),
                    "transliteration": entry.get("translit", entry.get("xlit", "")),
                    "pronunciation": entry.get("pronounce", ""),
                    "definition": entry.get("strongs_def", entry.get("kjv_def", "")),
                    "derivation": entry.get("derivation", ""),
                    "see_also": entry.get("see", []),
                    "status": "ok",
                    "layer": "original_language",
                    "note": (
                        "This is the original language word behind the WEB translation. "
                        "Use word_range() to see this word's full usage across scripture "
                        "and prevent single-verse interpretation drift."
                    ),
                }

        return {"strongs": strongs_num, "status": "not_found"}

    def search(self, keyword: str, limit: int = 20) -> dict:
        """
        Full-text search across all WEB verses.

        Returns up to `limit` matching verses.
        """
        db = self._get_db()
        if db is None:
            return {
                "query": keyword,
                "status": "source_missing",
                "detail": "WEB SQLite not found. Run: python fetch_sources.py",
            }

        rows = db.execute(
            "SELECT b, c, v, t FROM t_web WHERE t LIKE ? LIMIT ?",
            (f"%{keyword}%", limit)
        ).fetchall()

        results = []
        for b, c, v, t in rows:
            results.append({
                "ref": f"{BOOK_NAMES.get(b, str(b))} {c}:{v}",
                "text": t,
            })

        return {
            "query": keyword,
            "count": len(results),
            "results": results,
            "status": "ok",
            "layer": "WEB (locked English)",
        }

    def word_range(self, strongs_num: str) -> dict:
        """
        Return the lexical definition for a Strong's number.

        This is the foundation of the triangulation drift check:
        a word's meaning is constrained by its full corpus usage,
        not just its appearance in any single verse.
        """
        entry = self.lookup_strongs(strongs_num)
        if entry.get("status") != "ok":
            return entry

        entry["triangulation_note"] = (
            f"To prevent drift: any interpretation of a verse containing "
            f"{strongs_num} ({entry.get('word', '')}) must be consistent with "
            f"the definition above. Single-verse readings that contradict the "
            f"word's attested meaning across the corpus are flagged as drift."
        )
        return entry

    def ready(self) -> dict:
        """Return the availability status of each source layer."""
        return {
            "WEB_sqlite": WEB_DB.exists(),
            "strongs_hebrew": STRONGS_H.exists(),
            "strongs_greek": STRONGS_G.exists(),
            "morphhb_hebrew": (ROOT / "original" / "hebrew").exists(),
            "morphgnt_greek": (ROOT / "original" / "greek").exists(),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_result(result: dict):
    import json as _json
    print(_json.dumps(result, indent=2, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(
        description="Layer 0 WORD resolver — lookup scripture references"
    )
    parser.add_argument("--ref", help="Scripture reference, e.g. Jn3:16 or Gen1:1")
    parser.add_argument("--search", help="Keyword to search in WEB text")
    parser.add_argument("--word", help="Strong's number, e.g. G26 or H430")
    parser.add_argument("--status", action="store_true", help="Show source availability")
    args = parser.parse_args()

    src = SourceLayer()

    if args.status:
        _print_result(src.ready())
    elif args.ref:
        _print_result(src.lookup(args.ref))
    elif args.search:
        _print_result(src.search(args.search))
    elif args.word:
        _print_result(src.word_range(args.word))
    else:
        parser.print_help()
        print("\nExamples:")
        print("  python -m triangulation.lookup --ref Jn3:16")
        print("  python -m triangulation.lookup --ref Gen1:1")
        print("  python -m triangulation.lookup --search 'living water'")
        print("  python -m triangulation.lookup --word G26    # agape")
        print("  python -m triangulation.lookup --word H430   # Elohim")
        print("  python -m triangulation.lookup --status")


if __name__ == "__main__":
    main()
