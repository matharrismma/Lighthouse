#!/usr/bin/env python3
"""Build the Hebrew OT Layer-0 index -- the CANONICAL layer the agent works on.

Source: OpenScriptures Hebrew Bible (OSHB) -- the Westminster Leningrad Codex
with word-level Strong's numbers and morphology, from
https://github.com/openscriptures/morphhb (wlc/*.xml, OSIS).
License: the WLC text is PUBLIC DOMAIN; the OSHB morphology/Strong's tagging is
CC BY 4.0 (OpenScriptures). EXTERNAL Layer-0, attributed, never engine-authored.

This is MILESTONE 2 of the Scripture-onboard build: the original Hebrew, keyed to
the same verse coordinates as the WEB (book_num 1-39 = Genesis..Malachi), every
word tagged with its Strong's number + morphology. The AGENT works here (the
source); the user reads the WEB; Strong's + the great minds layer takes on top.

Output: lw/00_source/hebrew_ot/hebrew.db  (SQLite, query by reference)
  words (book_num INT, chapter INT, verse INT, pos INT, heb TEXT, strongs TEXT,
         morph TEXT, lemma TEXT)   -- idx (book_num,chapter,verse)
  meta  (k, v)

Usage:  python tools/build_hebrew_ot_index.py --src <dir with the wlc *.xml>
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

OSIS_NUM = {
    "Gen": 1, "Exod": 2, "Lev": 3, "Num": 4, "Deut": 5, "Josh": 6, "Judg": 7, "Ruth": 8,
    "1Sam": 9, "2Sam": 10, "1Kgs": 11, "2Kgs": 12, "1Chr": 13, "2Chr": 14, "Ezra": 15,
    "Neh": 16, "Esth": 17, "Job": 18, "Ps": 19, "Prov": 20, "Eccl": 21, "Song": 22,
    "Isa": 23, "Jer": 24, "Lam": 25, "Ezek": 26, "Dan": 27, "Hos": 28, "Joel": 29,
    "Amos": 30, "Obad": 31, "Jonah": 32, "Mic": 33, "Nah": 34, "Hab": 35, "Zeph": 36,
    "Hag": 37, "Zech": 38, "Mal": 39,
}
FILES = {a: a for a in OSIS_NUM}   # filename stem == osis abbrev


def _local(tag):
    return tag.split("}")[-1]


def _strongs(lemma):
    nums = re.findall(r"(\d+)\s*([a-z]?)", lemma or "")
    if not nums:
        return ""
    n, l = nums[-1]          # primary = the content word (prefixes come first)
    return n + l


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE words (book_num INT, chapter INT, verse INT, pos INT, "
                "heb TEXT, strongs TEXT, morph TEXT, lemma TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    rows = []
    verses_seen = set()
    for abbr, bn in OSIS_NUM.items():
        fp = src / (FILES[abbr] + ".xml")
        if not fp.exists():
            continue
        root = ET.parse(str(fp)).getroot()
        for verse in root.iter():
            if _local(verse.tag) != "verse":
                continue
            osis = verse.get("osisID")
            if not osis or osis.count(".") != 2:
                continue
            _, ch, vs = osis.split(".")
            ch, vs = int(ch), int(vs)
            verses_seen.add((bn, ch, vs))
            pos = 0
            for w in verse.iter():
                if _local(w.tag) != "w":
                    continue
                pos += 1
                heb = "".join(w.itertext()).strip()
                lemma = w.get("lemma", "")
                rows.append((bn, ch, vs, pos, heb, _strongs(lemma),
                             w.get("morph", ""), lemma))
    cur.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_w ON words(book_num, chapter, verse)")
    meta = {
        "source": "OpenScriptures Hebrew Bible (OSHB) -- Westminster Leningrad Codex, tagged",
        "url": "https://github.com/openscriptures/morphhb",
        "license": "WLC text public domain; OSHB tagging CC BY 4.0 (OpenScriptures)",
        "attribution": "Westminster Leningrad Codex; morphology + Strong's by OpenScriptures (CC BY)",
        "language": "Hebrew (+ Aramaic portions)", "n_words": str(len(rows)),
        "n_verses": str(len(verses_seen)),
        "note": "Original-language CANONICAL layer (milestone 2). Strong's = primary content lemma; "
                "prefixes (conjunction/article/preposition) are separate morphemes in heb (split by /).",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"words": len(rows), "verses": len(verses_seen)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with the OSHB wlc *.xml files")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "hebrew_ot" / "hebrew.db")
    print(build(Path(a.src), out))
    print("wrote", out)
