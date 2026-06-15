#!/usr/bin/env python3
"""Build the GeoNames Layer-0 place index (offline, reproducible).

Source: GeoNames cities5000 gazetteer (all places with population >= 5000),
plus countryInfo (country-code -> name) and admin1CodesASCII (admin1-code ->
name).  Downloaded from https://download.geonames.org/export/dump/ .
License: Creative Commons Attribution 4.0 (CC-BY 4.0).

This is EXTERNAL, ATTRIBUTED data -- a Layer-0 source, never engine-authored.
The engine stores it offline and looks it up by name; it does not generate it.

Output: lw/00_source/geonames/geonames.db  (SQLite, query-by-name, low memory).
  places    (geonameid, name, ascii, name_lc, ascii_lc, lat, lon, cc,
             admin1, fcode, population, tz)  -- indexed by name_lc + ascii_lc
  countries (cc, name, iso3, capital, continent, pop)
  admin1    (code, name)        -- code = "<CC>.<admin1>", e.g. "US.CA"
  meta      (k, v)              -- source, license, url, counts

Usage:
  python tools/build_geonames_index.py --src _tmp_geonames
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def _float(x):
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
    cur.execute(
        "CREATE TABLE places (geonameid INTEGER, name TEXT, ascii TEXT, "
        "name_lc TEXT, ascii_lc TEXT, lat REAL, lon REAL, cc TEXT, "
        "admin1 TEXT, fcode TEXT, population INTEGER, tz TEXT)"
    )
    cur.execute("CREATE TABLE countries (cc TEXT PRIMARY KEY, name TEXT, "
                "iso3 TEXT, capital TEXT, continent TEXT, pop INTEGER)")
    cur.execute("CREATE TABLE admin1 (code TEXT PRIMARY KEY, name TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    # --- countries -------------------------------------------------------
    n_countries = 0
    with (src / "countryInfo.txt").open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            c = line.rstrip("\n").split("\t")
            if len(c) < 9 or not c[0]:
                continue
            cur.execute(
                "INSERT OR REPLACE INTO countries VALUES (?,?,?,?,?,?)",
                (c[0], c[4], c[1], c[5], c[8], _int(c[7])),
            )
            n_countries += 1

    # --- admin1 ----------------------------------------------------------
    n_admin1 = 0
    with (src / "admin1CodesASCII.txt").open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            a = line.rstrip("\n").split("\t")
            if len(a) < 2 or not a[0]:
                continue
            cur.execute("INSERT OR REPLACE INTO admin1 VALUES (?,?)",
                        (a[0], a[1]))
            n_admin1 += 1

    # --- places ----------------------------------------------------------
    n_places = 0
    rows = []
    with (src / "cities5000.txt").open(encoding="utf-8") as fh:
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) < 19 or not f[1]:
                continue
            name, ascii_ = f[1], f[2]
            rows.append((
                _int(f[0]), name, ascii_,
                name.lower(), ascii_.lower(),
                _float(f[4]), _float(f[5]),
                f[8], f[10], f[7], _int(f[14]), f[17],
            ))
            if len(rows) >= 5000:
                cur.executemany(
                    "INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
                n_places += len(rows)
                rows = []
    if rows:
        cur.executemany(
            "INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        n_places += len(rows)

    cur.execute("CREATE INDEX idx_name_lc ON places(name_lc)")
    cur.execute("CREATE INDEX idx_ascii_lc ON places(ascii_lc)")

    meta = {
        "source": "GeoNames cities5000 gazetteer",
        "license": "CC-BY 4.0 (Creative Commons Attribution 4.0)",
        "url": "https://download.geonames.org/export/dump/",
        "attribution": "Data (c) GeoNames.org, used under CC-BY 4.0.",
        "threshold": "places with population >= 5000",
        "places": str(n_places),
        "countries": str(n_countries),
        "admin1": str(n_admin1),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))

    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"places": n_places, "countries": n_countries, "admin1": n_admin1}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_geonames",
                    help="dir with cities5000.txt, countryInfo.txt, "
                         "admin1CodesASCII.txt")
    ap.add_argument("--out",
                    default="lw/00_source/geonames/geonames.db")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[1]
    src = (root / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (root / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    counts = build(src, out)
    size_mb = out.stat().st_size / (1024 * 1024)
    print("geonames.db built: %s" % out)
    print("  places=%d countries=%d admin1=%d  (%.1f MB)" % (
        counts["places"], counts["countries"], counts["admin1"], size_mb))


if __name__ == "__main__":
    main()
