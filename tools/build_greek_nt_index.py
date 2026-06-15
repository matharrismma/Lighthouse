#!/usr/bin/env python3
"""Build the Greek NT Layer-0 index -- the CANONICAL layer the agent works on.

Source: MorphGNT / SBLGNT (https://github.com/morphgnt/sblgnt) -- the SBL Greek
New Testament with per-word part-of-speech + morphological parsing + lemma.
License: SBLGNT text is freely usable under the SBLGNT EULA (non-commercial use
and study permitted, attribution required); MorphGNT analysis is CC BY-SA 3.0.
EXTERNAL Layer-0, attributed, never engine-authored.

Strong's numbers are attached as an attributed TAKE: each MorphGNT lemma is looked
up in the OpenScriptures Strong's Greek dictionary (public domain, James Strong)
-- exact-lemma match first, accent-normalized fallback. ~95% of lemmas map; the
remainder (particles, rare variants) carry their lemma but no Strong's (honest --
the lemma is the canonical handle either way).

This is MILESTONE 3 of the Scripture-onboard build: the original Greek, keyed to
the same verse coordinates as the WEB (book_num 40-66 = Matthew..Revelation),
every word tagged with its lemma, morphology, and (where it maps) Strong's number.
The AGENT works here (the source); the user reads the WEB; Strong's + the great
minds layer takes on top.

Output: lw/00_source/greek_nt/greek.db  (SQLite, query by reference)
  words (book_num INT, chapter INT, verse INT, pos INT, grk TEXT, strongs TEXT,
         morph TEXT, lemma TEXT)   -- idx (book_num,chapter,verse)
  meta  (k, v)

Usage:  python tools/build_greek_nt_index.py --src <dir with NN-XX-morphgnt.txt + strongs.js>
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import unicodedata
from pathlib import Path

# MorphGNT BBCCVV book code 01=Matthew .. 27=Revelation -> canonical book_num 40..66.
GREEK_FILES = [
    "61-Mt", "62-Mk", "63-Lk", "64-Jn", "65-Ac", "66-Ro", "67-1Co", "68-2Co",
    "69-Ga", "70-Eph", "71-Php", "72-Col", "73-1Th", "74-2Th", "75-1Ti", "76-2Ti",
    "77-Tit", "78-Phm", "79-Heb", "80-Jas", "81-1Pe", "82-2Pe", "83-1Jn", "84-2Jn",
    "85-3Jn", "86-Jud", "87-Re",
]


def _strip(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn").lower()


def _load_strongs(src: Path):
    """Build lemma -> G-number maps (exact + accent-stripped) from the dict."""
    fp = src / "strongs.js"
    if not fp.exists():
        return {}, {}
    raw = fp.read_text(encoding="utf-8")
    d = json.loads(re.search(r"\{.*\}", raw, re.S).group(0))
    lem2g, strip2g = {}, {}
    for g, e in d.items():
        lem = (e.get("lemma") or "").strip()
        if lem:
            lem2g.setdefault(lem, g)
            strip2g.setdefault(_strip(lem), g)
    return lem2g, strip2g


def _strongs_for(lemma: str, lem2g, strip2g) -> str:
    if lemma in lem2g:
        return lem2g[lemma]
    g = strip2g.get(_strip(lemma))
    return g or ""


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    lem2g, strip2g = _load_strongs(src)
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE words (book_num INT, chapter INT, verse INT, pos INT, "
                "grk TEXT, strongs TEXT, morph TEXT, lemma TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    rows = []
    verses_seen = set()
    mapped = 0
    for stem in GREEK_FILES:
        fp = src / (stem + "-morphgnt.txt")
        if not fp.exists():
            continue
        cur_key = None
        pos = 0
        for line in fp.open(encoding="utf-8"):
            p = line.split()
            if len(p) < 7:
                continue
            bcv = p[0]
            bn = 39 + int(bcv[0:2])          # 01=Matthew -> 40
            ch, vs = int(bcv[2:4]), int(bcv[4:6])
            word = p[4]                       # surface word, punctuation removed
            lemma = p[6]
            morph = (p[1] + " " + p[2]).strip()   # POS + parse code
            key = (bn, ch, vs)
            if key != cur_key:
                cur_key, pos = key, 0
            pos += 1
            verses_seen.add(key)
            g = _strongs_for(lemma, lem2g, strip2g)
            if g:
                mapped += 1
            rows.append((bn, ch, vs, pos, word, g, morph, lemma))
    cur.executemany("INSERT INTO words VALUES (?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_w ON words(book_num, chapter, verse)")
    pct = (100 * mapped // len(rows)) if rows else 0
    meta = {
        "source": "MorphGNT / SBLGNT -- SBL Greek New Testament, morphologically tagged",
        "url": "https://github.com/morphgnt/sblgnt",
        "license": "SBLGNT text under the SBLGNT EULA (attribution; non-commercial study); "
                   "MorphGNT analysis CC BY-SA 3.0; Strong's mapping public domain (J. Strong)",
        "attribution": "SBL Greek New Testament; morphology by MorphGNT (CC BY-SA); "
                       "Strong's via OpenScriptures (public domain)",
        "language": "Greek (Koine)", "n_words": str(len(rows)),
        "n_verses": str(len(verses_seen)), "strongs_mapped_pct": str(pct),
        "note": "Original-language CANONICAL layer (milestone 3). Strong's attached by "
                "lemma match (exact, then accent-normalized); ~%d%% of words map, the rest "
                "(particles/variants) carry the lemma only." % pct,
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"words": len(rows), "verses": len(verses_seen),
            "strongs_mapped": mapped, "strongs_pct": pct}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with NN-XX-morphgnt.txt + strongs.js")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "greek_nt" / "greek.db")
    print(build(Path(a.src), out))
    print("wrote", out)
