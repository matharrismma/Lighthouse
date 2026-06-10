#!/usr/bin/env python
"""Parse 口語訳聖書 (Kogoyaku) from OSIS XML.

Source: tadd/jpn.bible vendor/kougo.osis.zip → originally from
bible.salterrae.net (PD release by Japan Bible Society, 2005).
The salterrae copyright statement says "claims no rights" / Public Domain.

Output: data/bible_ja/verses.jsonl in the same shape as the other parallel
Bibles. Replaces the prior Shinkaiyaku-NT-only file.

OSIS verse shapes handled:
  <verse osisID="X.C.V">text</verse>                      single verse
  <verse sID="X.C.V" osisID="X.C.V"/>text<verse eID="X.C.V"/>   split verse
Furigana <w gloss="reading">kanji</w> → keep kanji, drop gloss.
"""
from __future__ import annotations
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "data" / "raw_sources" / "kougo.osis.zip"
OUT_DIR = REPO / "data" / "bible_ja"
OUT_FILE = OUT_DIR / "verses.jsonl"

# OSIS book ID → canonical English book name + our 3-letter abbr
# Same conventions used by the other bible_<lang>/verses.jsonl files.
BOOK_MAP: Dict[str, Tuple[str, str]] = {
    "Gen":   ("Genesis", "GEN"),     "Exod":  ("Exodus", "EXO"),
    "Lev":   ("Leviticus", "LEV"),   "Num":   ("Numbers", "NUM"),
    "Deut":  ("Deuteronomy", "DEU"),
    "Josh":  ("Joshua", "JOS"),      "Judg":  ("Judges", "JDG"),
    "Ruth":  ("Ruth", "RUT"),
    "1Sam":  ("1 Samuel", "1SA"),    "2Sam":  ("2 Samuel", "2SA"),
    "1Kgs":  ("1 Kings", "1KI"),     "2Kgs":  ("2 Kings", "2KI"),
    "1Chr":  ("1 Chronicles", "1CH"),"2Chr":  ("2 Chronicles", "2CH"),
    "Ezra":  ("Ezra", "EZR"),        "Neh":   ("Nehemiah", "NEH"),
    "Esth":  ("Esther", "EST"),
    "Job":   ("Job", "JOB"),
    "Ps":    ("Psalms", "PSA"),
    "Prov":  ("Proverbs", "PRO"),
    "Eccl":  ("Ecclesiastes", "ECC"),
    "Song":  ("Song of Solomon", "SOL"),
    "Isa":   ("Isaiah", "ISA"),      "Jer":   ("Jeremiah", "JER"),
    "Lam":   ("Lamentations", "LAM"),"Ezek":  ("Ezekiel", "EZE"),
    "Dan":   ("Daniel", "DAN"),
    "Hos":   ("Hosea", "HOS"),       "Joel":  ("Joel", "JOE"),
    "Amos":  ("Amos", "AMO"),        "Obad":  ("Obadiah", "OBA"),
    "Jonah": ("Jonah", "JON"),       "Mic":   ("Micah", "MIC"),
    "Nah":   ("Nahum", "NAH"),       "Hab":   ("Habakkuk", "HAB"),
    "Zeph":  ("Zephaniah", "ZEP"),   "Hag":   ("Haggai", "HAG"),
    "Zech":  ("Zechariah", "ZEC"),   "Mal":   ("Malachi", "MAL"),
    "Matt":  ("Matthew", "MAT"),     "Mark":  ("Mark", "MAR"),
    "Luke":  ("Luke", "LUK"),        "John":  ("John", "JOH"),
    "Acts":  ("Acts", "ACT"),
    "Rom":   ("Romans", "ROM"),
    "1Cor":  ("1 Corinthians", "1CO"),"2Cor": ("2 Corinthians", "2CO"),
    "Gal":   ("Galatians", "GAL"),   "Eph":   ("Ephesians", "EPH"),
    "Phil":  ("Philippians", "PHI"), "Col":   ("Colossians", "COL"),
    "1Thess":("1 Thessalonians", "1TH"),"2Thess":("2 Thessalonians", "2TH"),
    "1Tim":  ("1 Timothy", "1TI"),   "2Tim":  ("2 Timothy", "2TI"),
    "Titus": ("Titus", "TIT"),       "Phlm":  ("Philemon", "PHM"),
    "Heb":   ("Hebrews", "HEB"),     "Jas":   ("James", "JAM"),
    "1Pet":  ("1 Peter", "1PE"),     "2Pet":  ("2 Peter", "2PE"),
    "1John": ("1 John", "1JO"),      "2John": ("2 John", "2JO"),
    "3John": ("3 John", "3JO"),      "Jude":  ("Jude", "JUD"),
    "Rev":   ("Revelation", "REV"),
}

# Helper: strip namespace from a tag name for easier comparison
def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def strip_to_text(elem: ET.Element) -> str:
    """Return concatenated text of element, dropping <verse> markers and
    keeping only the kanji content of <w gloss="...">kanji</w>. We do NOT
    recurse into <verse> children since they're handled at the chapter walk."""
    parts: List[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if _local(child.tag) == "verse":
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(strip_to_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def parse(osis_text: str) -> Dict[Tuple[str, int, int], str]:
    """Walk the OSIS tree, return {(book_osis, ch, v) → text}."""
    root = ET.fromstring(osis_text)
    verses: Dict[Tuple[str, int, int], List[str]] = {}
    current: Tuple[str, int, int] | None = None

    def walk(node: ET.Element) -> None:
        nonlocal current
        for child in node:
            tag = _local(child.tag)
            if tag == "verse":
                osis_id = child.get("osisID")
                sid = child.get("sID")
                eid = child.get("eID")
                if sid:
                    # Start marker for split verse
                    parts = sid.split(".")
                    if len(parts) == 3:
                        try:
                            current = (parts[0], int(parts[1]), int(parts[2]))
                        except ValueError:
                            current = None
                    if child.tail:
                        if current:
                            verses.setdefault(current, []).append(child.tail)
                elif eid:
                    # End marker
                    if child.tail and current:
                        # tail is usually whitespace; harmless
                        pass
                    current = None
                elif osis_id:
                    # Complete-verse form (has osisID but no sID/eID)
                    parts = osis_id.split(".")
                    if len(parts) == 3:
                        try:
                            key = (parts[0], int(parts[1]), int(parts[2]))
                        except ValueError:
                            continue
                        txt = strip_to_text(child).strip()
                        if txt:
                            verses.setdefault(key, []).append(txt)
                    if child.tail and current:
                        verses.setdefault(current, []).append(child.tail)
            else:
                # Non-verse element: capture text + tail into current open verse
                if child.text and current:
                    verses.setdefault(current, []).append(child.text)
                walk(child)
                if child.tail and current:
                    verses.setdefault(current, []).append(child.tail)

    walk(root)
    return {k: re.sub(r"\s+", " ", "".join(parts)).strip() for k, parts in verses.items()}


def main() -> int:
    if not SRC.exists():
        print(f"missing source: {SRC}", file=sys.stderr)
        return 1
    with zipfile.ZipFile(SRC) as z:
        raw = z.read("kougo.osis").decode("utf-8")
    print(f"parsing {len(raw):,} chars of OSIS...", flush=True)

    verses = parse(raw)
    if not verses:
        print("ERROR: no verses extracted", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Order verses by canonical book order
    book_order = list(BOOK_MAP.keys())
    book_idx = {b: i for i, b in enumerate(book_order)}
    items = sorted(
        verses.items(),
        key=lambda kv: (book_idx.get(kv[0][0], 99), kv[0][1], kv[0][2]),
    )

    unknown_books: set[str] = set()
    written = 0
    with OUT_FILE.open("w", encoding="utf-8") as out:
        for (book_osis, ch, vs), text in items:
            spec = BOOK_MAP.get(book_osis)
            if not spec:
                unknown_books.add(book_osis)
                continue
            book, abbr = spec
            rec = {
                "id":          f"kogo_{abbr.lower()}_{ch:02d}_{vs:02d}",
                "book":        book,
                "book_abbr":   abbr,
                "chapter":     ch,
                "verse":       vs,
                "reference":   f"{book} {ch}:{vs}",
                "text":        text,
                "lang":        "ja",
                "translation": "口語訳聖書 (Kogoyaku 1954/1955)",
                "year":        "1954-1955",
                "source":      "bible.salterrae.net via tadd/jpn.bible (PD release 2005)",
                "license":     "Public Domain",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written += 1

    print(f"wrote {written:,} verses to {OUT_FILE}")
    if unknown_books:
        print(f"WARNING unknown OSIS book IDs: {sorted(unknown_books)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
