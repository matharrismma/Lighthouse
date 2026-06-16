#!/usr/bin/env python3
"""Build a verse-keyed COMMENTARY index -- an attributed great-minds TAKE layer.

Source: Free Use Bible API (https://bible.helloao.org) -- public-domain classic
commentaries served as clean per-chapter JSON. Default: Matthew Henry's Commentary
(public domain). License per the API: the underlying commentary text is public
domain (CC0); attributed to its author. EXTERNAL Layer-0, attributed, never
engine-authored.

This is the great-minds COMMENTARY take of the Scripture-onboard build: the classic
expositor's note for a passage, keyed to the same verse coordinates as the WEB.
Matthew Henry (and most classic commentators) comment at PASSAGE granularity, so
each note is keyed to its START verse; a lookup for John 3:16 returns the note whose
start verse is the largest <= 16 in that chapter (the passage covering v16). The
note is an ATTRIBUTED take (the author's), never engine doctrine.

Output: lw/00_source/commentary/<id>.db  (SQLite)
  notes (book_num INT, chapter INT, verse_start INT, text TEXT)  -- idx (book_num,chapter)
  meta  (k, v)

Usage:  python tools/build_commentary_index.py [--commentary matthew-henry]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://bible.helloao.org"

# USFM 3-letter book code -> canonical book_num (1-66), the same keying as the WEB.
USFM = [
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA", "1KI", "2KI",
    "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO", "ECC", "SNG", "ISA", "JER",
    "LAM", "EZK", "DAN", "HOS", "JOL", "AMO", "OBA", "JON", "MIC", "NAM", "HAB", "ZEP",
    "HAG", "ZEC", "MAL", "MAT", "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL",
    "EPH", "PHP", "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
]
CODE_NUM = {c: i + 1 for i, c in enumerate(USFM)}


def _get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                return None
    return None


def _flatten(content):
    out = []
    for item in content or []:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            t = item.get("text") or item.get("content")
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, list):
                out.append(_flatten(t))
    return "\n".join(x for x in out if x).strip()


def build(commentary: str, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    books = _get("%s/api/c/%s/books.json" % (API, commentary))
    if not books or "books" not in books:
        raise SystemExit("could not fetch book list for " + commentary)
    cname = (books.get("commentary") or {}).get("name") or commentary
    jobs = []
    for b in books["books"]:
        code = b.get("id")
        bn = CODE_NUM.get(code)
        if bn is None:
            continue
        first = b.get("firstChapterNumber") or 1
        last = b.get("lastChapterNumber") or b.get("numberOfChapters") or 0
        for ch in range(int(first), int(last) + 1):
            jobs.append((bn, code, ch))

    rows = []
    fetched = {"n": 0, "fail": 0}

    def work(job):
        bn, code, ch = job
        d = _get("%s/api/c/%s/%s/%d.json" % (API, commentary, code, ch))
        if not d:
            fetched["fail"] += 1
            return []
        fetched["n"] += 1
        content = (d.get("chapter") or {}).get("content") or []
        r = []
        for node in content:
            if node.get("type") != "verse":
                continue
            vs = node.get("number")
            txt = _flatten(node.get("content"))
            if vs is not None and txt:
                r.append((bn, ch, int(vs), txt))
        return r

    with ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(work, jobs):
            rows.extend(res)

    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE notes (book_num INT, chapter INT, verse_start INT, text TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO notes VALUES (?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_n ON notes(book_num, chapter)")
    meta = {
        "source": "Free Use Bible API (bible.helloao.org) -- %s" % cname,
        "url": "%s/api/c/%s" % (API, commentary),
        "license": "Public domain commentary text (CC0); via the Free Use Bible API",
        "attribution": "%s (public domain)" % cname,
        "commentary_id": commentary, "author": cname,
        "n_notes": str(len(rows)), "n_chapters_fetched": str(fetched["n"]),
        "n_chapters_failed": str(fetched["fail"]),
        "note": "Attributed great-minds COMMENTARY take, passage-level, keyed to start verse. "
                "A lookup returns the note whose verse_start is the largest <= the queried verse. "
                "ATTRIBUTED to the author, never engine doctrine.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"notes": len(rows), "chapters": fetched["n"], "failed": fetched["fail"],
            "books": len({r[0] for r in rows})}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--commentary", default="matthew-henry")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    fname = a.commentary.replace("-", "_") + ".db"
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "commentary" / fname)
    print(build(a.commentary, out))
    print("wrote", out)
