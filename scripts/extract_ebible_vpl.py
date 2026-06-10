#!/usr/bin/env python
"""Generic eBible.org VPL → bible_<lang>/verses.jsonl extractor.

Every eBible VPL uses the same `BOOK CHAPTER:VERSE TEXT` line format with the
same SIL 3-letter book abbreviations. So one extractor handles every
translation; we just parameterize: which zip, which language code, which
translation label, which year, and which source URL.

Usage:
  python scripts/extract_ebible_vpl.py <ebible_id> <lang_code> <translation_label> [<year>]

Examples:
  python scripts/extract_ebible_vpl.py cmn-cu89s zh "Chinese Union Version (Simplified)" 1919
  python scripts/extract_ebible_vpl.py fraLSG    fr "Louis Segond 1910" 1910
  python scripts/extract_ebible_vpl.py porbrbsl  pt "Bíblia Portuguesa Mundial" 2022

Output: data/bible_<lang>/verses.jsonl, same shape as data/bible_es/verses.jsonl.
Source zip expected at data/raw_sources/<ebible_id>_vpl.zip.
"""
from __future__ import annotations
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Canonical book mapping. Identical to the RV1909 extractor — eBible uses
# SIL's older 3-letter abbreviations consistently across all translations.
BOOK_MAP = {
    "GEN": "Genesis", "EXO": "Exodus", "LEV": "Leviticus",
    "NUM": "Numbers", "DEU": "Deuteronomy",
    "JOS": "Joshua", "JDG": "Judges", "RUT": "Ruth",
    "1SA": "1 Samuel", "2SA": "2 Samuel",
    "1KI": "1 Kings", "2KI": "2 Kings",
    "1CH": "1 Chronicles", "2CH": "2 Chronicles",
    "EZR": "Ezra", "NEH": "Nehemiah", "EST": "Esther",
    "JOB": "Job", "PSA": "Psalms", "PRO": "Proverbs",
    "ECC": "Ecclesiastes", "SOL": "Song of Solomon",
    "ISA": "Isaiah", "JER": "Jeremiah", "LAM": "Lamentations",
    "EZE": "Ezekiel", "DAN": "Daniel",
    "HOS": "Hosea", "JOE": "Joel", "AMO": "Amos", "OBA": "Obadiah",
    "JON": "Jonah", "MIC": "Micah", "NAH": "Nahum", "HAB": "Habakkuk",
    "ZEP": "Zephaniah", "HAG": "Haggai", "ZEC": "Zechariah", "MAL": "Malachi",
    "MAT": "Matthew", "MAR": "Mark", "LUK": "Luke", "JOH": "John",
    "ACT": "Acts",
    "ROM": "Romans", "1CO": "1 Corinthians", "2CO": "2 Corinthians",
    "GAL": "Galatians", "EPH": "Ephesians", "PHI": "Philippians",
    "COL": "Colossians", "1TH": "1 Thessalonians", "2TH": "2 Thessalonians",
    "1TI": "1 Timothy", "2TI": "2 Timothy", "TIT": "Titus", "PHM": "Philemon",
    "HEB": "Hebrews", "JAM": "James",
    "1PE": "1 Peter", "2PE": "2 Peter",
    "1JO": "1 John", "2JO": "2 John", "3JO": "3 John",
    "JUD": "Jude", "REV": "Revelation",
}

LINE_RE = re.compile(r"^([A-Z0-9]+)\s+(\d+):(\d+)\s+(.+?)\s*$")


def extract(ebible_id: str, lang: str, translation: str, year: str = "") -> int:
    src = REPO / "data" / "raw_sources" / f"{ebible_id}_vpl.zip"
    if not src.exists():
        print(f"missing source: {src}", file=sys.stderr)
        return 1

    out_dir = REPO / "data" / f"bible_{lang}"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "verses.jsonl"

    with zipfile.ZipFile(src) as z:
        txt_name = next((n for n in z.namelist() if n.endswith("_vpl.txt")), None)
        if not txt_name:
            print(f"no _vpl.txt inside {src}", file=sys.stderr)
            return 2
        raw = z.read(txt_name).decode("utf-8")

    unknown: set[str] = set()
    count = skipped = 0
    id_prefix = ebible_id.replace("-", "").lower()

    with out_file.open("w", encoding="utf-8") as out:
        for line in raw.splitlines():
            m = LINE_RE.match(line)
            if not m:
                continue
            abbr, ch_s, vs_s, body = m.groups()
            book = BOOK_MAP.get(abbr)
            if not book:
                unknown.add(abbr)
                skipped += 1
                continue
            try:
                chapter = int(ch_s)
                verse = int(vs_s)
            except ValueError:
                skipped += 1
                continue
            body = re.sub(r"\s+", " ", body).strip()
            if not body:
                skipped += 1
                continue
            rec = {
                "id":          f"{id_prefix}_{abbr.lower()}_{chapter:02d}_{verse:02d}",
                "book":        book,
                "book_abbr":   abbr,
                "chapter":     chapter,
                "verse":       verse,
                "reference":   f"{book} {chapter}:{verse}",
                "text":        body,
                "lang":        lang,
                "translation": translation,
                "year":        year,
                "source":      f"eBible.org · {ebible_id}",
                "license":     "Public Domain",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1

    print(f"wrote {count} verses to {out_file}")
    if skipped:
        print(f"skipped {skipped} non-matching lines")
    if unknown:
        print(f"WARNING unknown abbreviations: {sorted(unknown)}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: extract_ebible_vpl.py <ebible_id> <lang> <label> [<year>]",
              file=sys.stderr)
        return 1
    return extract(argv[1], argv[2], argv[3], argv[4] if len(argv) > 4 else "")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
