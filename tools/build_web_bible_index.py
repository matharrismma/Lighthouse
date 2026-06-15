#!/usr/bin/env python3
"""Build the World English Bible (WEB) Layer-0 index -- the translation surface.

Source: World English Bible (WEB), from eBible.org verse-per-line file
eng-web_vpl.txt (https://ebible.org/Scriptures/eng-web_vpl.zip).
License: PUBLIC DOMAIN (the WEB is dedicated to the public domain).

This is MILESTONE 1 of the Scripture-onboard build: the readable TRANSLATION
surface, verse-keyed. The original Hebrew/Greek + Strong's + the great minds'
takes layer onto these same verse coordinates in later milestones. The agent
works in the original; the user reads this. External Layer-0, attributed, never
engine-authored.

Output: lw/00_source/web_bible/web.db  (SQLite, query by reference)
  verses (book_num INT, book TEXT, code TEXT, chapter INT, verse INT, ref TEXT, text TEXT)
          -- idx (book_num,chapter,verse)
  books  (book_num INT, code TEXT, name TEXT)
  meta   (k, v)

Usage:  python tools/build_web_bible_index.py --src <dir with eng-web_vpl.txt>
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

# Canonical 66-book Protestant order, using the eBible.org (haiola) book codes
# present in eng-web_vpl. The source edition also carries the Apocrypha
# (deuterocanon: SIR, TOB, WIS, 1MA-4MA, BAR, JDT, 1ES, 4ES, ESG, DNG, PSX, PRM);
# those are excluded here -- the corpus's canon is the 66.
BOOKS = [
    ("GEN", "Genesis"), ("EXO", "Exodus"), ("LEV", "Leviticus"), ("NUM", "Numbers"),
    ("DEU", "Deuteronomy"), ("JOS", "Joshua"), ("JDG", "Judges"), ("RUT", "Ruth"),
    ("1SA", "1 Samuel"), ("2SA", "2 Samuel"), ("1KI", "1 Kings"), ("2KI", "2 Kings"),
    ("1CH", "1 Chronicles"), ("2CH", "2 Chronicles"), ("EZR", "Ezra"), ("NEH", "Nehemiah"),
    ("EST", "Esther"), ("JOB", "Job"), ("PSA", "Psalms"), ("PRO", "Proverbs"),
    ("ECC", "Ecclesiastes"), ("SOL", "Song of Solomon"), ("ISA", "Isaiah"), ("JER", "Jeremiah"),
    ("LAM", "Lamentations"), ("EZE", "Ezekiel"), ("DAN", "Daniel"), ("HOS", "Hosea"),
    ("JOE", "Joel"), ("AMO", "Amos"), ("OBA", "Obadiah"), ("JON", "Jonah"), ("MIC", "Micah"),
    ("NAH", "Nahum"), ("HAB", "Habakkuk"), ("ZEP", "Zephaniah"), ("HAG", "Haggai"),
    ("ZEC", "Zechariah"), ("MAL", "Malachi"),
    ("MAT", "Matthew"), ("MAR", "Mark"), ("LUK", "Luke"), ("JOH", "John"), ("ACT", "Acts"),
    ("ROM", "Romans"), ("1CO", "1 Corinthians"), ("2CO", "2 Corinthians"), ("GAL", "Galatians"),
    ("EPH", "Ephesians"), ("PHI", "Philippians"), ("COL", "Colossians"),
    ("1TH", "1 Thessalonians"), ("2TH", "2 Thessalonians"), ("1TI", "1 Timothy"),
    ("2TI", "2 Timothy"), ("TIT", "Titus"), ("PHM", "Philemon"), ("HEB", "Hebrews"),
    ("JAM", "James"), ("1PE", "1 Peter"), ("2PE", "2 Peter"), ("1JO", "1 John"),
    ("2JO", "2 John"), ("3JO", "3 John"), ("JUD", "Jude"), ("REV", "Revelation"),
]
CODE_NUM = {c: i + 1 for i, (c, _) in enumerate(BOOKS)}
CODE_NAME = {c: n for c, n in BOOKS}
LINE = re.compile(r"^([A-Z0-9]{3})\s+(\d+):(\d+)\s+(.*)$")


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE verses (book_num INT, book TEXT, code TEXT, chapter INT, "
                "verse INT, ref TEXT, text TEXT)")
    cur.execute("CREATE TABLE books (book_num INT, code TEXT, name TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    rows = []
    seen_codes = []
    skipped = 0
    with (src / "eng-web_vpl.txt").open(encoding="utf-8") as f:
        for line in f:
            m = LINE.match(line.rstrip("\n"))
            if not m:
                skipped += 1
                continue
            code, ch, vs, text = m.group(1), int(m.group(2)), int(m.group(3)), m.group(4).strip()
            if code not in CODE_NUM:        # outside the 66 (e.g. apocrypha) -- skip for now
                skipped += 1
                continue
            num = CODE_NUM[code]
            name = CODE_NAME[code]
            ref = "%s %d:%d" % (name, ch, vs)
            rows.append((num, name, code, ch, vs, ref, text))
            if code not in seen_codes:
                seen_codes.append(code)
    cur.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_v ON verses(book_num, chapter, verse)")
    for c in seen_codes:
        cur.execute("INSERT INTO books VALUES (?,?,?)", (CODE_NUM[c], c, CODE_NAME[c]))
    meta = {
        "source": "World English Bible (WEB), eBible.org eng-web_vpl",
        "url": "https://ebible.org/Scriptures/eng-web_vpl.zip",
        "license": "Public Domain (the WEB is dedicated to the public domain)",
        "attribution": "World English Bible, public domain; via eBible.org",
        "translation": "WEB", "n_verses": str(len(rows)), "n_books": str(len(seen_codes)),
        "note": "Translation surface (milestone 1). Original + Strong's + takes layer on the same verse keys.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"verses": len(rows), "books": len(seen_codes), "skipped": skipped}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir containing eng-web_vpl.txt")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "web_bible" / "web.db")
    print(build(Path(a.src), out))
    print("wrote", out)
