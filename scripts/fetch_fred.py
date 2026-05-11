"""Fetch FRED economic series → fred_full.jsonl.

FRED (Federal Reserve Economic Data, https://fred.stlouisfed.org/)
hosts thousands of public-domain US economic time series. The API is
free but requires a key. Get one at:
  https://fredaccount.stlouisfed.org/apikey

Set the key as the environment variable FRED_API_KEY before running:
  set FRED_API_KEY=your_key_here

Usage:
    python scripts/fetch_fred.py
    python scripts/fetch_fred.py --series CPIAUCSL UNRATE FEDFUNDS GDPC1
    python scripts/fetch_fred.py --start 1980 --end 2024

The engine's fred_economics verifier prefers data/economics/fred_full.jsonl
when present; the shipped seed at fred_seed.jsonl is the fallback.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

OUT = Path(__file__).resolve().parent.parent / "data" / "economics" / "fred_full.jsonl"

# FRED series ID → our canonical series_id + name + computation method
_SERIES_MAP = {
    "CPIAUCSL":  {"sid": "CPI_INFLATION_LEVEL",  "name": "CPI All Urban Consumers (level)",     "agg": "last"},
    "UNRATE":    {"sid": "UNEMP_RATE",            "name": "US unemployment rate, annual avg",    "agg": "mean"},
    "FEDFUNDS":  {"sid": "FED_FUNDS",             "name": "US federal funds effective rate",     "agg": "mean"},
    "GDPC1":     {"sid": "REAL_GDP_LEVEL",        "name": "Real GDP (level, billions chained)",  "agg": "last"},
}


def fetch_series(series_id: str, api_key: str, start: str, end: str) -> List[Dict[str, Any]]:
    qs = urllib.parse.urlencode({
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start,
        "observation_end": end,
    })
    url = f"https://api.stlouisfed.org/fred/series/observations?{qs}"
    print(f"  GET {series_id} ({start} → {end})", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "concordance-engine/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("observations", [])


def aggregate_annual(obs: List[Dict[str, Any]], method: str) -> Dict[int, float]:
    """Reduce observations to one value per year."""
    by_year: Dict[int, List[float]] = {}
    for o in obs:
        date_str = o.get("date")
        val_str = o.get("value")
        if not date_str or val_str == "." or val_str is None:
            continue
        try:
            year = int(date_str[:4])
            v = float(val_str)
        except ValueError:
            continue
        by_year.setdefault(year, []).append(v)
    out: Dict[int, float] = {}
    for year, vals in by_year.items():
        if not vals:
            continue
        if method == "mean":
            out[year] = sum(vals) / len(vals)
        elif method == "last":
            out[year] = vals[-1]
        else:
            out[year] = vals[-1]
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch FRED economic series.")
    p.add_argument("--series", nargs="+", default=list(_SERIES_MAP.keys()),
                   help="FRED series IDs to fetch")
    p.add_argument("--start", default="1980-01-01")
    p.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"))
    args = p.parse_args()

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    if not api_key:
        print("FRED_API_KEY not set. Get a free key at https://fredaccount.stlouisfed.org/apikey",
              file=sys.stderr)
        return 2

    OUT.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with OUT.open("w", encoding="utf-8") as out:
        out.write('# source: FRED + BLS + BEA (US government, public domain)\n')
        for series_id in args.series:
            cfg = _SERIES_MAP.get(series_id)
            if not cfg:
                print(f"  skipping unknown series {series_id}", file=sys.stderr)
                continue
            try:
                obs = fetch_series(series_id, api_key, args.start, args.end)
            except Exception as exc:
                print(f"  fetch failed for {series_id}: {exc}", file=sys.stderr)
                continue
            annual = aggregate_annual(obs, cfg["agg"])
            for year in sorted(annual):
                out.write(json.dumps({
                    "series_id": cfg["sid"],
                    "name":      cfg["name"],
                    "year":      year,
                    "value":     round(annual[year], 4),
                    "unit":      "percent" if "rate" in cfg["sid"].lower() or cfg["sid"] == "CPI_INFLATION" else "index_or_level",
                    "source":    "FRED (Federal Reserve Bank of St. Louis)",
                }, ensure_ascii=False) + "\n")
                total += 1
    print(f"wrote {total} rows to {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
