#!/usr/bin/env python
"""Fetch and parse 口語訳聖書 (Kogoyaku, Japanese Colloquial Bible, 1954/1955).

Source: bible.salterrae.net (PD release by Japan Bible Society, 2005).
Live host is unreachable from many networks; pull via Wayback Machine.

Output: data/bible_ja/verses.jsonl in the same shape as the other parallel
Bibles. Replaces the prior Shinkaiyaku-NT-only file with a full PD Bible.

XML format: each book is one file with <chapter id="N"> containing verses
that come in two shapes:
  <verse id="C:V">complete text</verse>           — single line
  <verse sid="C:V"/> text spread across <l>... <verse eid="C:V"/>   — split

Furigana annotations: <w s="reading">kanji</w>. Drop the reading attribute,
keep only the kanji content.
"""
from __future__ import annotations
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple
import xml.etree.ElementTree as ET

# Make stdout safe for non-ASCII characters on Windows consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
RAW_DIR = REPO / "data" / "raw_sources" / "kogoyaku"
OUT_DIR = REPO / "data" / "bible_ja"
OUT_FILE = OUT_DIR / "verses.jsonl"

# Wayback Machine raw-content URL prefix (the `if_` suffix returns the
# original archived content untouched).
WAYBACK = "https://web.archive.org/web/2020if_/http://bible.salterrae.net/kougo/xml/"

# Filename(s) → English book name. Some books are split for size; multiple
# files map to the same canonical book.
BOOK_FILES: List[Tuple[str, str]] = [
    ("genesis_12.xml",     "Genesis"),
    ("genesis_3.xml",      "Genesis"),
    ("exodus.xml",         "Exodus"),
    ("leviticus.xml",      "Leviticus"),
    ("numbers.xml",        "Numbers"),
    ("deuteronomy.xml",    "Deuteronomy"),
    ("joshua.xml",         "Joshua"),
    ("judges.xml",         "Judges"),
    ("ruth.xml",           "Ruth"),
    ("1samuel.xml",        "1 Samuel"),
    ("2samuel.xml",        "2 Samuel"),
    ("1kings.xml",         "1 Kings"),
    ("2kings.xml",         "2 Kings"),
    ("1chronicles.xml",    "1 Chronicles"),
    ("2chronicles.xml",    "2 Chronicles"),
    ("ezra.xml",           "Ezra"),
    ("nehemiah.xml",       "Nehemiah"),
    ("esther.xml",         "Esther"),
    ("job.xml",            "Job"),
    ("psalms_12.xml",      "Psalms"),
    ("psalms_345.xml",     "Psalms"),
    ("proverbs.xml",       "Proverbs"),
    ("ecclesiastes.xml",   "Ecclesiastes"),
    ("songofsongs.xml",    "Song of Solomon"),
    ("isaiah_1.xml",       "Isaiah"),
    ("isaiah_2.xml",       "Isaiah"),
    ("jeremiah_1.xml",     "Jeremiah"),
    ("jeremiah_2.xml",     "Jeremiah"),
    ("lamentations.xml",   "Lamentations"),
    ("ezekiel_1.xml",      "Ezekiel"),
    ("ezekiel_2.xml",      "Ezekiel"),
    ("daniel.xml",         "Daniel"),
    ("hosea.xml",          "Hosea"),
    ("joel.xml",           "Joel"),
    ("amos.xml",           "Amos"),
    ("obadiah.xml",        "Obadiah"),
    ("jonah.xml",          "Jonah"),
    ("micah.xml",          "Micah"),
    ("nahum.xml",          "Nahum"),
    ("habakkuk.xml",       "Habakkuk"),
    ("zephaniah.xml",      "Zephaniah"),
    ("haggai.xml",         "Haggai"),
    ("zecariah.xml",       "Zechariah"),  # NB: salterrae filename typo
    ("malachi.xml",        "Malachi"),
    ("matthew.xml",        "Matthew"),
    ("mark.xml",           "Mark"),
    ("luke.xml",           "Luke"),
    ("john.xml",           "John"),
    ("acts.xml",           "Acts"),
    ("romans.xml",         "Romans"),
    ("1corintians.xml",    "1 Corinthians"),  # NB: filename typo
    ("2corintians.xml",    "2 Corinthians"),
    ("galatians.xml",      "Galatians"),
    ("ephesians.xml",      "Ephesians"),
    ("philippians.xml",    "Philippians"),
    ("colossians.xml",     "Colossians"),
    ("1thessalonians.xml", "1 Thessalonians"),
    ("2thessalonians.xml", "2 Thessalonians"),
    ("1timothy.xml",       "1 Timothy"),
    ("2timothy.xml",       "2 Timothy"),
    ("titus.xml",          "Titus"),
    ("philemon.xml",       "Philemon"),
    ("hebrews.xml",        "Hebrews"),
    ("james.xml",          "James"),
    ("1peter.xml",         "1 Peter"),
    ("2peter.xml",         "2 Peter"),
    ("1john.xml",          "1 John"),
    ("2john.xml",          "2 John"),
    ("3john.xml",          "3 John"),
    ("jude.xml",           "Jude"),
    ("revelation.xml",     "Revelation"),
]

# Map English book name to a stable 3-letter abbreviation for verse IDs.
BOOK_ABBR = {
    "Genesis": "GEN", "Exodus": "EXO", "Leviticus": "LEV", "Numbers": "NUM",
    "Deuteronomy": "DEU", "Joshua": "JOS", "Judges": "JDG", "Ruth": "RUT",
    "1 Samuel": "1SA", "2 Samuel": "2SA", "1 Kings": "1KI", "2 Kings": "2KI",
    "1 Chronicles": "1CH", "2 Chronicles": "2CH", "Ezra": "EZR",
    "Nehemiah": "NEH", "Esther": "EST", "Job": "JOB", "Psalms": "PSA",
    "Proverbs": "PRO", "Ecclesiastes": "ECC", "Song of Solomon": "SOL",
    "Isaiah": "ISA", "Jeremiah": "JER", "Lamentations": "LAM",
    "Ezekiel": "EZE", "Daniel": "DAN", "Hosea": "HOS", "Joel": "JOE",
    "Amos": "AMO", "Obadiah": "OBA", "Jonah": "JON", "Micah": "MIC",
    "Nahum": "NAH", "Habakkuk": "HAB", "Zephaniah": "ZEP", "Haggai": "HAG",
    "Zechariah": "ZEC", "Malachi": "MAL",
    "Matthew": "MAT", "Mark": "MAR", "Luke": "LUK", "John": "JOH",
    "Acts": "ACT", "Romans": "ROM",
    "1 Corinthians": "1CO", "2 Corinthians": "2CO",
    "Galatians": "GAL", "Ephesians": "EPH", "Philippians": "PHI",
    "Colossians": "COL",
    "1 Thessalonians": "1TH", "2 Thessalonians": "2TH",
    "1 Timothy": "1TI", "2 Timothy": "2TI", "Titus": "TIT", "Philemon": "PHM",
    "Hebrews": "HEB", "James": "JAM",
    "1 Peter": "1PE", "2 Peter": "2PE",
    "1 John": "1JO", "2 John": "2JO", "3 John": "3JO",
    "Jude": "JUD", "Revelation": "REV",
}


def fetch(filename: str) -> bytes:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cached = RAW_DIR / filename
    if cached.exists() and cached.stat().st_size > 200:
        return cached.read_bytes()
    url = WAYBACK + filename
    print(f"  fetching {filename}...", flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (concordance-engine)"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = resp.read()
    cached.write_bytes(data)
    return data


def strip_xml_to_text(elem: ET.Element) -> str:
    """Recursive walk: return concatenated text content of the element,
    dropping furigana reading attributes (we keep only the kanji content
    inside <w>...</w>)."""
    parts: List[str] = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.tag == "verse":
            # Don't recurse into verse markers — those are handled at the
            # chapter walk level.
            if child.tail:
                parts.append(child.tail)
            continue
        parts.append(strip_xml_to_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def parse_chapter(chapter_elem: ET.Element) -> Dict[int, str]:
    """Walk a <chapter> element, return {verse_num → text}.

    Handles both verse shapes:
      <verse id="C:V">text</verse>           — direct content
      <verse sid="C:V"/> ... <verse eid="C:V"/>   — spans siblings/children
    """
    chapter_id = int(chapter_elem.get("id", "0"))
    verses: Dict[int, List[str]] = {}
    current_verse: int = 0

    def walk(node: ET.Element) -> None:
        nonlocal current_verse
        for child in node:
            if child.tag == "verse":
                vid = child.get("id")
                sid = child.get("sid")
                eid = child.get("eid")
                if vid:
                    # Complete verse — inner text is the entire verse
                    try:
                        v_num = int(vid.split(":")[1])
                    except (IndexError, ValueError):
                        continue
                    txt = strip_xml_to_text(child).strip()
                    verses.setdefault(v_num, []).append(txt)
                    if child.tail:
                        # tail follows the close tag; treat as belonging to
                        # current verse if there is one
                        if current_verse:
                            verses.setdefault(current_verse, []).append(child.tail)
                elif sid:
                    try:
                        current_verse = int(sid.split(":")[1])
                    except (IndexError, ValueError):
                        current_verse = 0
                    if child.tail:
                        verses.setdefault(current_verse, []).append(child.tail)
                elif eid:
                    if child.tail and current_verse:
                        # Trailing whitespace; rarely meaningful
                        pass
                    current_verse = 0
            else:
                # Non-verse element: walk into it, but also capture text+tail
                # so accumulated content lands in the current open verse.
                if child.text and current_verse:
                    verses.setdefault(current_verse, []).append(child.text)
                walk(child)
                if child.tail and current_verse:
                    verses.setdefault(current_verse, []).append(child.tail)

    walk(chapter_elem)
    # Concatenate + normalize whitespace
    return {
        n: re.sub(r"\s+", " ", "".join(parts)).strip()
        for n, parts in verses.items()
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Accumulate verses keyed by (book, chapter, verse) so split-files
    # for the same book merge cleanly.
    all_verses: Dict[Tuple[str, int, int], str] = {}

    for i, (filename, book) in enumerate(BOOK_FILES, 1):
        try:
            data = fetch(filename)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
            print(f"  FAILED {filename}: {exc}", file=sys.stderr)
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError as exc:
            print(f"  PARSE FAIL {filename}: {exc}", file=sys.stderr)
            continue
        verses_in_file = 0
        for ch in root.findall("chapter"):
            try:
                ch_num = int(ch.get("id", "0"))
            except ValueError:
                continue
            verses = parse_chapter(ch)
            for v_num, text in verses.items():
                if not text:
                    continue
                all_verses[(book, ch_num, v_num)] = text
                verses_in_file += 1
        print(f"    [{i}/{len(BOOK_FILES)}] {filename} -> {book}: +{verses_in_file} verses (total {len(all_verses)})", flush=True)
        # Polite pacing — Wayback throttles aggressive scrapers
        if i % 5 == 0:
            time.sleep(0.6)

    if not all_verses:
        print("ERROR: no verses extracted", file=sys.stderr)
        return 1

    # Emit JSONL sorted by (canonical book order, chapter, verse).
    book_order = {name: idx for idx, (_, name) in enumerate(BOOK_FILES)}
    rows = sorted(all_verses.items(), key=lambda kv: (book_order.get(kv[0][0], 99), kv[0][1], kv[0][2]))

    with OUT_FILE.open("w", encoding="utf-8") as out:
        for (book, ch, vs), text in rows:
            abbr = BOOK_ABBR.get(book, "XXX")
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
                "source":      "bible.salterrae.net (PD release 2005)",
                "license":     "Public Domain",
            }
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"wrote {len(rows)} verses to {OUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
