#!/usr/bin/env python3
"""Build the HYG star-catalog Layer-0 index (offline, reproducible).

Source: the HYG stellar database (hyg_v42), a merge of the Hipparcos, Yale
Bright Star, and Gliese catalogs, from https://codeberg.org/astronexus/hyg
(LFS media: .../data/hyg/CURRENT/hyg_v42.csv.gz).
License: Creative Commons Attribution-ShareAlike 4.0 (CC BY-SA 4.0),
(c) David Nash / astronexus.

EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored. Grounds the
astronomy verifier: a star's constellation, magnitude, spectral type, and
distance (e.g. "Betelgeuse is in Orion", "Sirius is the brightest star").
Positions/distances are catalog measurements (authority); we report them as the
source gives them, attributed.

Output: lw/00_source/hyg/hyg.db  (SQLite, query-by-key, low memory)
  stars (proper TEXT, proper_lc TEXT, bf TEXT, con TEXT, ra REAL, dec REAL,
         dist REAL, mag REAL, absmag REAL, spect TEXT, lum REAL)
        indexed by proper_lc and con. dist is in parsecs; 100000 = unknown.
  meta  (k, v)

Usage:
  python tools/build_hyg_index.py --src _tmp_hyg/hyg_v42.csv.gz
"""
from __future__ import annotations

import argparse
import csv
import gzip
import sqlite3
from pathlib import Path


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE stars (proper TEXT, proper_lc TEXT, bf TEXT, "
                "con TEXT, ra REAL, dec REAL, dist REAL, mag REAL, "
                "absmag REAL, spect TEXT, lum REAL)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    n = 0
    named = 0
    rows = []
    with gzip.open(str(src), "rt", encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        hdr = next(r)
        ix = {c: i for i, c in enumerate(hdr)}

        def g(row, col):
            i = ix.get(col)
            return row[i] if i is not None and i < len(row) else ""

        for row in r:
            proper = g(row, "proper").strip()
            if proper:
                named += 1
            rows.append((
                proper, proper.lower(),
                g(row, "bf").strip(), g(row, "con").strip(),
                _f(g(row, "ra")), _f(g(row, "dec")), _f(g(row, "dist")),
                _f(g(row, "mag")), _f(g(row, "absmag")),
                g(row, "spect").strip(), _f(g(row, "lum")),
            ))
            if len(rows) >= 5000:
                cur.executemany(
                    "INSERT INTO stars VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
                n += len(rows)
                rows = []
    if rows:
        cur.executemany("INSERT INTO stars VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        n += len(rows)

    cur.execute("CREATE INDEX idx_proper ON stars(proper_lc)")
    cur.execute("CREATE INDEX idx_con ON stars(con)")
    meta = {
        "source": "HYG stellar database (hyg_v42; Hipparcos + Yale BSC + Gliese)",
        "license": "CC BY-SA 4.0",
        "url": "https://codeberg.org/astronexus/hyg",
        "attribution": "HYG database (c) David Nash / astronexus, CC BY-SA 4.0.",
        "note": "dist in parsecs (100000 = unknown/no parallax); "
                "mag = apparent magnitude; con = IAU constellation abbreviation.",
        "stars": str(n),
        "named": str(named),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"stars": n, "named": named, "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_hyg/hyg_v42.csv.gz")
    ap.add_argument("--out", default="lw/00_source/hyg/hyg.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("hyg.db built: %s" % out)
    print("  stars=%d named=%d  (%.1f MB)" % (
        r["stars"], r["named"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
