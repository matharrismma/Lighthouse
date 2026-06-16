#!/usr/bin/env python3
"""build_sermon_index.py -- a verse-keyed SERMON index (the great-minds preaching layer).

Source: FottyM/spurgeon-gems (https://github.com/FottyM/spurgeon-gems) -- Charles H.
Spurgeon's sermons scraped from spurgeongems.org into JSON (title, audio uri, and the
sermon's TEXT = the verse it was preached on). Spurgeon (1834-1892) is PUBLIC DOMAIN.

This is the SERMON take of the Scripture-onboard build: each sermon was preached on a
specific text, so it indexes verse -> which great-mind sermon addresses it (title +
reference + a source link). It is an attributed INDEX/POINTER -- which sermon, where to
hear/read it -- not the full prose (full-text enrichment is a documented follow-up).
An ATTRIBUTED take (Spurgeon's); the engine surfaces it, never endorses or generates it.

Output: lw/00_source/sermons/spurgeon.db  (SQLite)
  sermons (book_num INT, chapter INT, verse INT, title TEXT, reference TEXT,
           source_url TEXT, author TEXT)   -- idx (book_num,chapter,verse)
  meta    (k, v)

Usage:  python tools/build_sermon_index.py --src <dir with spurgeon.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
from pathlib import Path

BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy", "Joshua", "Judges", "Ruth",
    "1 Samuel", "2 Samuel", "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles", "Ezra",
    "Nehemiah", "Esther", "Job", "Psalms", "Proverbs", "Ecclesiastes", "Song of Solomon",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel", "Amos",
    "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk", "Zephaniah", "Haggai", "Zechariah",
    "Malachi", "Matthew", "Mark", "Luke", "John", "Acts", "Romans", "1 Corinthians",
    "2 Corinthians", "Galatians", "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians", "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter", "1 John", "2 John", "3 John", "Jude",
    "Revelation",
]
NUM = {b.lower(): i + 1 for i, b in enumerate(BOOKS)}
NUM.update({"psalm": 19, "song of songs": 22, "canticles": 22, "revelations": 66,
            "song": 22})
REF = re.compile(r"^\s*((?:[1-3]\s)?[A-Za-z][A-Za-z ]+?)\s+(\d+):(\d+)")


def _booknum(name: str):
    n = re.sub(r"\s+", " ", name.strip().lower())
    if n in NUM:
        return NUM[n]
    for b, i in NUM.items():                 # prefix match (e.g. "Phil" -> Philippians)
        if b.startswith(n) and len(n) >= 3:
            return i
    return None


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    data = json.loads((src / "spurgeon.json").read_text(encoding="utf-8"))
    rows, miss = [], 0
    for s in data:
        v = (s.get("verse") or "").split("\n")[0].strip()
        m = REF.match(v)
        bn = _booknum(m.group(1)) if m else None
        if not m or bn is None:
            miss += 1
            continue
        ch, vs = int(m.group(2)), int(m.group(3))
        rows.append((bn, ch, vs, (s.get("title") or "").strip(), v.strip(),
                     (s.get("uri") or "").strip(), "Charles H. Spurgeon"))
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE sermons (book_num INT, chapter INT, verse INT, title TEXT, "
                "reference TEXT, source_url TEXT, author TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO sermons VALUES (?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_s ON sermons(book_num, chapter, verse)")
    meta = {
        "source": "FottyM/spurgeon-gems -- C.H. Spurgeon sermons (title + text) from spurgeongems.org",
        "url": "https://github.com/FottyM/spurgeon-gems",
        "license": "Spurgeon's sermons are PUBLIC DOMAIN; index compiled from spurgeongems.org",
        "attribution": "Charles H. Spurgeon (1834-1892), public domain; index via spurgeongems.org",
        "author": "Charles H. Spurgeon", "n_sermons": str(len(rows)), "n_unparsed": str(miss),
        "note": "Verse-keyed sermon INDEX/POINTER (which sermon was preached on a text + a source "
                "link), not the full prose. Attributed great-minds take; full-text enrichment is a "
                "follow-up. The engine surfaces it, never endorses or generates it.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"sermons": len(rows), "unparsed": miss}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with spurgeon.json")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "sermons" / "spurgeon.db")
    print(build(Path(a.src), out))
    print("wrote", out)
