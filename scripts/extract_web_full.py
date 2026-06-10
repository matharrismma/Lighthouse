#!/usr/bin/env python
"""Extract full WEB English Bible from lw/00_source/web/web.db to
data/bible_en/verses.jsonl in the same shape as the other parallel
bibles.

This becomes the canonical English Scripture substrate for parallel
lookups and Bible-corpus alignment. The scattered per-book files
(proverbs/, james/, ecclesiastes/, psalms/, sermon_on_mount/) remain
for the existing Apothecary retrieval — they carry axes/themes that
the full WEB doesn't yet.

SQLite schema: t_web(id, b, c, v, t). Book codes 1..66 standard order.
"""
from __future__ import annotations
import io
import json
import sqlite3
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "lw" / "00_source" / "web" / "web.db"
OUT_DIR = REPO / "data" / "bible_en"
OUT_FILE = OUT_DIR / "verses.jsonl"

# Standard 1-66 book order with canonical English names + 3-letter abbreviations.
BOOKS = [
    (1,  "Genesis",        "GEN"), (2,  "Exodus",         "EXO"),
    (3,  "Leviticus",      "LEV"), (4,  "Numbers",        "NUM"),
    (5,  "Deuteronomy",    "DEU"),
    (6,  "Joshua",         "JOS"), (7,  "Judges",         "JDG"),
    (8,  "Ruth",           "RUT"),
    (9,  "1 Samuel",       "1SA"), (10, "2 Samuel",       "2SA"),
    (11, "1 Kings",        "1KI"), (12, "2 Kings",        "2KI"),
    (13, "1 Chronicles",   "1CH"), (14, "2 Chronicles",   "2CH"),
    (15, "Ezra",           "EZR"), (16, "Nehemiah",       "NEH"),
    (17, "Esther",         "EST"),
    (18, "Job",            "JOB"), (19, "Psalms",         "PSA"),
    (20, "Proverbs",       "PRO"), (21, "Ecclesiastes",   "ECC"),
    (22, "Song of Solomon","SOL"),
    (23, "Isaiah",         "ISA"), (24, "Jeremiah",       "JER"),
    (25, "Lamentations",   "LAM"), (26, "Ezekiel",        "EZE"),
    (27, "Daniel",         "DAN"),
    (28, "Hosea",          "HOS"), (29, "Joel",           "JOE"),
    (30, "Amos",           "AMO"), (31, "Obadiah",        "OBA"),
    (32, "Jonah",          "JON"), (33, "Micah",          "MIC"),
    (34, "Nahum",          "NAH"), (35, "Habakkuk",       "HAB"),
    (36, "Zephaniah",      "ZEP"), (37, "Haggai",         "HAG"),
    (38, "Zechariah",      "ZEC"), (39, "Malachi",        "MAL"),
    (40, "Matthew",        "MAT"), (41, "Mark",           "MAR"),
    (42, "Luke",           "LUK"), (43, "John",           "JOH"),
    (44, "Acts",           "ACT"),
    (45, "Romans",         "ROM"),
    (46, "1 Corinthians",  "1CO"), (47, "2 Corinthians",  "2CO"),
    (48, "Galatians",      "GAL"), (49, "Ephesians",      "EPH"),
    (50, "Philippians",    "PHI"), (51, "Colossians",     "COL"),
    (52, "1 Thessalonians","1TH"), (53, "2 Thessalonians","2TH"),
    (54, "1 Timothy",      "1TI"), (55, "2 Timothy",      "2TI"),
    (56, "Titus",          "TIT"), (57, "Philemon",       "PHM"),
    (58, "Hebrews",        "HEB"),
    (59, "James",          "JAM"),
    (60, "1 Peter",        "1PE"), (61, "2 Peter",        "2PE"),
    (62, "1 John",         "1JO"), (63, "2 John",         "2JO"),
    (64, "3 John",         "3JO"),
    (65, "Jude",           "JUD"),
    (66, "Revelation",     "REV"),
]
BOOK_BY_NUM = {n: (name, abbr) for n, name, abbr in BOOKS}


def main() -> int:
    if not DB.exists():
        print(f"missing source: {DB}", file=sys.stderr)
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(DB))
    cur = con.cursor()
    cur.execute("SELECT b, c, v, t FROM t_web ORDER BY b, c, v")
    rows = cur.fetchall()
    con.close()

    unknown: set[int] = set()
    written = 0
    with OUT_FILE.open("w", encoding="utf-8") as out:
        for b, c, v, text in rows:
            spec = BOOK_BY_NUM.get(b)
            if not spec:
                unknown.add(b)
                continue
            book, abbr = spec
            text = (text or "").strip()
            if not text:
                continue
            rec = {
                "id":          f"web_{abbr.lower()}_{c:02d}_{v:02d}",
                "book":        book,
                "book_abbr":   abbr,
                "chapter":     c,
                "verse":       v,
                "reference":   f"{book} {c}:{v}",
                "text":        text,
                "lang":        "en",
                "translation": "World English Bible",
                "year":        "1997 (revision ongoing)",
                "source":      "lw/00_source/web/web.db",
                "license":     "Public Domain",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    print(f"wrote {written:,} verses to {OUT_FILE}")
    if unknown:
        print(f"WARNING unknown book codes: {sorted(unknown)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
