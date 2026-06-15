#!/usr/bin/env python3
"""Build the OEIS Layer-0 index (offline, reproducible).

Source: the On-Line Encyclopedia of Integer Sequences (OEIS), bulk files
  stripped.gz  (A-number -> its terms)
  names.gz     (A-number -> its name/definition)
from https://oeis.org/ .  License: Creative Commons Attribution-ShareAlike 4.0
(CC BY-SA 4.0), (c) The OEIS Foundation Inc.

This is EXTERNAL, ATTRIBUTED data -- a Layer-0 source, never engine-authored.
OEIS is a curated/crowd-sourced reference: matching terms IDENTIFIES a sequence
(a CONCORDANT-grade reference pointer), it is not a deterministic proof of the
sequence's defining property.

Output: lw/00_source/oeis/oeis.db  (SQLite, query-by-key, low memory)
  sequences (anum TEXT PRIMARY KEY, name TEXT, terms TEXT)
        terms is comma-delimited with a leading AND trailing comma
        (",0,1,1,2,...,") so a needle ",2,3,5," matches whole terms only.
  meta      (k, v)

Usage:
  python tools/build_oeis_index.py --src _tmp_oeis
"""
from __future__ import annotations

import argparse
import gzip
import sqlite3
from pathlib import Path


def _rows(path: Path):
    with gzip.open(str(path), "rt", encoding="utf-8", errors="replace") as f:
        for ln in f:
            if ln.startswith("#") or not ln.strip():
                continue
            yield ln.rstrip("\n")


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    names = {}
    for ln in _rows(src / "names.gz"):
        sp = ln.find(" ")
        if sp <= 0:
            continue
        names[ln[:sp]] = ln[sp + 1:].strip()

    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE sequences (anum TEXT PRIMARY KEY, name TEXT, terms TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    n = 0
    batch = []
    for ln in _rows(src / "stripped.gz"):
        sp = ln.find(" ")
        if sp <= 0:
            continue
        anum = ln[:sp]
        terms = ln[sp + 1:].strip()
        if not terms.startswith(","):
            terms = "," + terms
        if not terms.endswith(","):
            terms = terms + ","
        batch.append((anum, names.get(anum, ""), terms))
        if len(batch) >= 5000:
            cur.executemany("INSERT OR REPLACE INTO sequences VALUES (?,?,?)", batch)
            n += len(batch)
            batch = []
    if batch:
        cur.executemany("INSERT OR REPLACE INTO sequences VALUES (?,?,?)", batch)
        n += len(batch)

    meta = {
        "source": "OEIS (On-Line Encyclopedia of Integer Sequences)",
        "license": "CC BY-SA 4.0",
        "url": "https://oeis.org",
        "attribution": "Sequence data from the OEIS, (c) The OEIS Foundation "
                       "Inc., licensed CC BY-SA 4.0.",
        "grade": "CONCORDANT -- curated/crowd-sourced reference; term match "
                 "identifies, it does not prove the defining property.",
        "sequences": str(n),
        "names": str(len(names)),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))

    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"sequences": n, "names": len(names), "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_oeis",
                    help="dir with stripped.gz and names.gz")
    ap.add_argument("--out", default="lw/00_source/oeis/oeis.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("oeis.db built: %s" % out)
    print("  sequences=%d names=%d  (%.1f MB)" % (
        r["sequences"], r["names"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
