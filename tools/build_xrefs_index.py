#!/usr/bin/env python3
"""Build the cross-references Layer-0 index -- the openbible.info cross-reference set.

Source: openbible.info "Cross References" (https://www.openbible.info/labs/cross-references/),
a community-voted expansion of the public-domain Treasury of Scripture Knowledge (TSK). Each
row links a FROM verse to a related TO verse/passage, with a relevance VOTE score. Licensed
CC BY (openbible.info). EXTERNAL Layer-0, ATTRIBUTED, never engine-authored. Grounds the
concordance's core act -- cross-referencing Scripture with Scripture.

Output: lw/00_source/xrefs/xrefs.db  (SQLite)
  cross_refs (from_book INT, from_chapter INT, from_verse INT,
              to_book INT, to_chapter INT, to_verse_start INT, to_verse_end INT, votes INT)
             -- idx (from_book, from_chapter, from_verse)
  meta       (k, v)

book_num matches lw/00_source/web_bible/web.db (Genesis=1 .. Malachi=39, Matthew=40 .. Rev=66).

Usage:  python tools/build_xrefs_index.py
"""
from __future__ import annotations

import argparse
import io
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

URL = "https://a.openbible.info/data/cross-references.zip"

# OSIS abbreviations in canonical Protestant order -> book_num = index + 1 (matches web.db).
OSIS_ORDER = [
    "Gen", "Exod", "Lev", "Num", "Deut", "Josh", "Judg", "Ruth", "1Sam", "2Sam",
    "1Kgs", "2Kgs", "1Chr", "2Chr", "Ezra", "Neh", "Esth", "Job", "Ps", "Prov",
    "Eccl", "Song", "Isa", "Jer", "Lam", "Ezek", "Dan", "Hos", "Joel", "Amos",
    "Obad", "Jonah", "Mic", "Nah", "Hab", "Zeph", "Hag", "Zech", "Mal",            # 1-39 OT
    "Matt", "Mark", "Luke", "John", "Acts", "Rom", "1Cor", "2Cor", "Gal", "Eph",
    "Phil", "Col", "1Thess", "2Thess", "1Tim", "2Tim", "Titus", "Phlm", "Heb",
    "Jas", "1Pet", "2Pet", "1John", "2John", "3John", "Jude", "Rev",               # 40-66 NT
]
OSIS2NUM = {a: i + 1 for i, a in enumerate(OSIS_ORDER)}


def _parse_ref(ref):
    """'Gen.1.1' -> (book_num, chapter, verse) or None if unparseable."""
    parts = ref.split(".")
    if len(parts) != 3:
        return None
    bn = OSIS2NUM.get(parts[0])
    if bn is None:
        return None
    try:
        return bn, int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _parse_to(tov):
    """TO field: 'Isa.44.24' or a range 'Gen.1.2-Gen.1.5'. Returns
    (to_book, to_chapter, to_verse_start, to_verse_end) or None."""
    if "-" in tov:
        lo, hi = tov.split("-", 1)
        a = _parse_ref(lo)
        b = _parse_ref(hi)
        if a is None:
            return None
        # range end verse only when same book+chapter; else the anchor verse
        end = b[2] if (b is not None and b[0] == a[0] and b[1] == a[1] and b[2] >= a[2]) else a[2]
        return a[0], a[1], a[2], end
    a = _parse_ref(tov)
    if a is None:
        return None
    return a[0], a[1], a[2], a[2]


def build(out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    req = urllib.request.Request(URL, headers={"User-Agent": "concordance-build/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        blob = r.read()
    z = zipfile.ZipFile(io.BytesIO(blob))
    text = z.read(z.namelist()[0]).decode("utf-8", "replace")

    rows = []
    skipped = 0
    for line in text.splitlines():
        line = line.rstrip()
        if not line or line.startswith("From Verse"):
            continue
        cols = line.split("\t")
        if len(cols) < 2:
            skipped += 1
            continue
        frm = _parse_ref(cols[0])
        to = _parse_to(cols[1])
        if frm is None or to is None:
            skipped += 1
            continue
        try:
            votes = int(cols[2]) if len(cols) > 2 and cols[2].strip() else 0
        except ValueError:
            votes = 0
        rows.append((frm[0], frm[1], frm[2], to[0], to[1], to[2], to[3], votes))

    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE cross_refs (from_book INT, from_chapter INT, from_verse INT, "
                "to_book INT, to_chapter INT, to_verse_start INT, to_verse_end INT, votes INT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO cross_refs VALUES (?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_from ON cross_refs(from_book, from_chapter, from_verse)")
    meta = {
        "source": "openbible.info Cross References (community-voted expansion of the public-domain "
                  "Treasury of Scripture Knowledge)",
        "url": "https://www.openbible.info/labs/cross-references/",
        "license": "CC BY (openbible.info)",
        "attribution": "Cross-reference data courtesy of openbible.info, CC BY; based on the "
                       "public-domain Treasury of Scripture Knowledge",
        "n_rows": str(len(rows)),
        "note": "Scripture-to-Scripture cross references with a relevance VOTE score (higher = more "
                "strongly linked). An ATTRIBUTED index, not engine doctrine. book_num matches web.db.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"rows": len(rows), "skipped": skipped,
            "from_verses": len({(r[0], r[1], r[2]) for r in rows})}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "xrefs" / "xrefs.db")
    print(build(out))
    print("wrote", out)
