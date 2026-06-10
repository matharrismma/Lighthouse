#!/usr/bin/env python
"""Extract Reina-Valera 1909 (Spanish, PD) verse-by-verse.

Source: eBible.org VPL (verse-per-line) ZIP.
URL:    https://eBible.org/Scriptures/spaRV1909_vpl.zip
License: Public Domain.

Output: data/bible_es/verses.jsonl with the same {book, chapter, verse, text}
shape as the English Proverbs / James / Ecclesiastes / Psalms files, so
the scripture_lookup module can swap text by (lang, book, chapter, verse).
The English book name is stored in `book` so lookup is symmetric across
languages.

Note: the VPL uses some non-standard SIL abbreviations (e.g. JAM/JOH/EZE/
JOE/MAR/NAH/PHI/SOL/1JO). The mapping below normalizes to canonical
English book names.
"""
from __future__ import annotations
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "raw_sources" / "spaRV1909_vpl.zip"
OUT_DIR = REPO / "data" / "bible_es"
OUT_FILE = OUT_DIR / "verses.jsonl"

# eBible RV1909 VPL → canonical English book name.
BOOK_MAP = {
    # Pentateuch
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus",
    "NUM": "Numbers", "DEU": "Deuteronomy",
    # Historical
    "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel",
    "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles",
    "EZR": "Ezra", "NEH": "Nehemiah", "EST": "Esther",
    # Wisdom + Poetic
    "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
    "ECC": "Ecclesiastes", "SOL": "Song of Solomon",
    # Major Prophets
    "ISA": "Isaiah", "JER": "Jeremiah", "LAM": "Lamentations",
    "EZE": "Ezekiel", "DAN": "Daniel",
    # Minor Prophets
    "HOS": "Hosea", "JOE": "Joel", "AMO": "Amos", "OBA": "Obadiah",
    "JON": "Jonah", "MIC": "Micah", "NAH": "Nahum", "HAB": "Habakkuk",
    "ZEP": "Zephaniah", "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi",
    # Gospels + Acts
    "MAT": "Matthew", "MAR": "Mark", "LUK": "Luke", "JOH": "John",
    "ACT": "Acts",
    # Pauline
    "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
    "GAL": "Galatians", "EPH": "Ephesians", "PHI": "Philippians",
    "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians",
    "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon",
    # General Epistles + Revelation
    "HEB": "Hebrews", "JAM": "James",
    "1PE": "1 Peter", "2PE": "2 Peter",
    "1JO": "1 John", "2JO": "2 John", "3JO": "3 John",
    "JUD": "Jude", "REV": "Revelation",
}

LINE_RE = re.compile(r"^([A-Z0-9]+)\s+(\d+):(\d+)\s+(.+?)\s*$")


def extract() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(SRC) as z:
        raw = z.read("spaRV1909_vpl.txt").decode("utf-8")

    unknown_books: set[str] = set()
    count = 0
    skipped = 0
    with OUT_FILE.open("w", encoding="utf-8") as out:
        for line in raw.splitlines():
            m = LINE_RE.match(line)
            if not m:
                continue
            abbr, ch_s, vs_s, body = m.groups()
            book = BOOK_MAP.get(abbr)
            if not book:
                unknown_books.add(abbr)
                skipped += 1
                continue
            try:
                chapter = int(ch_s)
                verse = int(vs_s)
            except ValueError:
                skipped += 1
                continue
            body = body.strip()
            if not body:
                skipped += 1
                continue
            # Strip Strong's-style or paratext brackets that occasionally appear.
            # RV1909 VPL uses [bracketed insertions] for words not in the
            # underlying text — keep them (they're part of the translation
            # convention) but normalize whitespace.
            body = re.sub(r"\s+", " ", body).strip()

            rec = {
                "id":        f"rv1909_{abbr.lower()}_{chapter:02d}_{verse:02d}",
                "book":      book,
                "book_abbr": abbr,
                "chapter":   chapter,
                "verse":     verse,
                "reference": f"{book} {chapter}:{verse}",
                "text":      body,
                "lang":      "es",
                "translation": "Reina-Valera 1909",
                "source":    "eBible.org",
                "license":   "Public Domain",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"wrote {count} verses to {OUT_FILE}")
    if skipped:
        print(f"skipped {skipped} non-matching lines")
    if unknown_books:
        print(f"WARNING unknown book abbreviations: {sorted(unknown_books)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(extract())
