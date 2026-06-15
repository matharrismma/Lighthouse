#!/usr/bin/env python3
"""Build the ECB euro foreign-exchange reference-rate Layer-0 index (offline, reproducible).

Source: European Central Bank -- euro foreign exchange reference rates,
historical file eurofxref-hist.csv (inside eurofxref-hist.zip), from
https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip
License: free to use with attribution to the ECB. Rates are published each
TARGET business day around 16:00 CET, base currency EUR, ~40 currencies, daily
back to 1999-01-04.

These are REFERENCE rates for information only -- NOT transaction rates. They
ground the finance verifier and a currency_convert lookup (X CUR_A -> CUR_B on a
date, via the EUR cross). EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored.

Output: lw/00_source/ecb_fx/fx.db  (SQLite, query by date+currency)
  rates (date TEXT, cur TEXT, rate REAL)   -- rate = units of cur per 1 EUR; idx (date),(cur)
  meta  (k, v)                             -- source, url, license, attribution, base,
                                              latest_date, n_dates, n_currencies, note

Usage:
  python tools/build_ecb_fx_index.py --src <dir-with eurofxref-hist.csv>
  (download+unzip eurofxref-hist.zip into <dir> first)
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE rates (date TEXT, cur TEXT, rate REAL)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    rows = []
    dates = set()
    currencies = set()
    with (src / "eurofxref-hist.csv").open(encoding="utf-8") as f:
        r = csv.reader(f)
        header = [c.strip() for c in next(r)]   # ['Date','USD','JPY',...,'']
        for row in r:
            if not row or not row[0].strip():
                continue
            d = row[0].strip()
            dates.add(d)
            for i in range(1, len(header)):
                code = header[i]
                if not code:
                    continue
                val = row[i].strip() if i < len(row) else ""
                if not val or val.upper() == "N/A":
                    continue
                try:
                    rate = float(val)
                except ValueError:
                    continue
                rows.append((d, code, rate))
                currencies.add(code)
    cur.executemany("INSERT INTO rates VALUES (?,?,?)", rows)
    cur.execute("CREATE INDEX idx_date ON rates(date)")
    cur.execute("CREATE INDEX idx_cur ON rates(cur)")
    latest = max(dates) if dates else ""
    meta = {
        "source": "European Central Bank -- euro foreign exchange reference rates (eurofxref-hist.csv)",
        "url": "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip",
        "license": "Free to use with attribution to the ECB",
        "attribution": "(c) European Central Bank; euro reference rates, ~16:00 CET",
        "base": "EUR (rate = units of the currency per 1 EUR; EUR itself = 1.0)",
        "latest_date": latest,
        "n_dates": str(len(dates)),
        "n_currencies": str(len(currencies)),
        "note": "Reference rates for INFORMATION only -- not transaction rates.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"rows": len(rows), "dates": len(dates),
            "currencies": len(currencies), "latest": latest}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir containing eurofxref-hist.csv")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "ecb_fx" / "fx.db")
    print(build(Path(a.src), out))
    print("wrote", out)
