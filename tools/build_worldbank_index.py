#!/usr/bin/env python3
"""Build the economics Layer-0 index -- a World Bank Open Data snapshot.

Source: World Bank Open Data (https://data.worldbank.org), via the public API
(api.worldbank.org/v2). A curated set of key development indicators, most-recent value
per country/aggregate (mrnev=1). This is a DATED SNAPSHOT (re-run to refresh). World
Bank data is openly licensed (CC BY 4.0). EXTERNAL Layer-0, attributed, never engine-
authored. Grounds economics -- real indicator VALUES to check claims against.

Output: lw/00_source/worldbank/worldbank.db  (SQLite)
  indicators (country TEXT, iso3 TEXT, code TEXT, indicator TEXT, value REAL, year TEXT)
             -- idx (iso3), (country)
  meta       (k, v)

Usage:  python tools/build_worldbank_index.py
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import urllib.request
from pathlib import Path

API = "https://api.worldbank.org/v2/country/all/indicator/%s?format=json&per_page=400&mrnev=1"

# Curated, broadly-useful, reliable indicators (code -> short friendly name).
INDICATORS = {
    "NY.GDP.MKTP.CD": "GDP (current US$)",
    "NY.GDP.PCAP.CD": "GDP per capita (current US$)",
    "SP.POP.TOTL": "Population, total",
    "SP.DYN.LE00.IN": "Life expectancy at birth (years)",
    "FP.CPI.TOTL.ZG": "Inflation, consumer prices (annual %)",
    "SL.UEM.TOTL.ZS": "Unemployment (% of labor force, modeled ILO)",
    "SP.URB.TOTL.IN.ZS": "Urban population (% of total)",
    # Labor indicators (grounds the 'labor' domain via the same World Bank source).
    "SL.TLF.CACT.ZS": "Labor force participation rate (% of pop 15+)",
    "SL.EMP.TOTL.SP.ZS": "Employment to population ratio (% of pop 15+)",
    "SL.TLF.TOTL.IN": "Labor force, total",
    "SL.AGR.EMPL.ZS": "Employment in agriculture (% of employment)",
    "SL.SRV.EMPL.ZS": "Employment in services (% of employment)",
}


def _get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            if k == tries - 1:
                return None
    return None


def build(out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    rows = []
    years = set()
    fetched = 0
    for code, name in INDICATORS.items():
        d = _get(API % code)
        if not d or len(d) < 2 or not d[1]:
            continue
        fetched += 1
        for r in d[1]:
            v = r.get("value")
            if v is None:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            cn = (r.get("country") or {}).get("value") or ""
            iso3 = r.get("countryiso3code") or ""
            yr = r.get("date") or ""
            years.add(yr)
            rows.append((cn, iso3, code, name, v, yr))
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE indicators (country TEXT, iso3 TEXT, code TEXT, indicator TEXT, "
                "value REAL, year TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO indicators VALUES (?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_iso ON indicators(iso3)")
    cur.execute("CREATE INDEX idx_country ON indicators(country)")
    meta = {
        "source": "World Bank Open Data -- key development indicators (most-recent value per country)",
        "url": "https://data.worldbank.org (api.worldbank.org/v2)",
        "license": "CC BY 4.0 (World Bank Open Data)",
        "attribution": "World Bank Open Data, CC BY 4.0",
        "n_rows": str(len(rows)), "n_indicators": str(fetched),
        "years": ",".join(sorted(y for y in years if y)),
        "note": "DATED SNAPSHOT of World Bank indicators (re-run to refresh). Grounds economics: real "
                "indicator values to check claims against. Includes country aggregates (e.g. 'Arab World').",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"rows": len(rows), "indicators": fetched, "countries": len({r[1] for r in rows})}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "worldbank" / "worldbank.db")
    print(build(out))
    print("wrote", out)
