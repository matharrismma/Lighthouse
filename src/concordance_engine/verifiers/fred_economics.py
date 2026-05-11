"""FRED economic data verifier.

Historical US macroeconomic time-series from FRED (Federal Reserve
Economic Data) and BLS. US government works are not copyrightable;
this data is fully public domain.

The shipped seed covers four headline series annually 2000-2023:
  * CPI_INFLATION     — annual CPI inflation rate (Dec YoY)
  * UNEMP_RATE        — unemployment rate, annual average
  * FED_FUNDS         — federal funds effective rate, annual avg
  * REAL_GDP_GROWTH   — real GDP annual growth rate

The operator can run scripts/fetch_fred.py with a free FRED API key
to expand to the full set of FRED series and tighter monthly/daily
resolution.

Checks:
  * econ.series_value — value of a series in a given year matches claim

ECON_VERIFY shape:
    {
      "series_id": "CPI_INFLATION",   # or aliases (see below)
      "year": 2022,
      "claimed_value": 6.5,
      "rel_tol": 0.10,                # default 0.10 — series revisions vary
      "abs_tol": 0.5,                 # default 0.5 percentage points
    }

Series aliases:
  inflation, cpi_inflation, us_inflation → CPI_INFLATION
  unemployment, unemployment_rate         → UNEMP_RATE
  fed_funds, federal_funds, ffr           → FED_FUNDS
  gdp_growth, real_gdp_growth             → REAL_GDP_GROWTH
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


_DATA_DIR = Path(__file__).resolve().parents[2].parent / "data" / "economics"
_SOURCES = [
    _DATA_DIR / "fred_full.jsonl",   # operator-fetched
    _DATA_DIR / "fred_seed.jsonl",   # shipped
]

_CACHE: Dict[str, Any] = {"mtime": 0.0, "by_series_year": {}, "total": 0}

_SERIES_ALIASES: Dict[str, str] = {
    "inflation": "CPI_INFLATION",
    "cpi": "CPI_INFLATION",
    "cpi_inflation": "CPI_INFLATION",
    "us_inflation": "CPI_INFLATION",
    "consumer_price_index": "CPI_INFLATION",
    "annual_inflation": "CPI_INFLATION",
    "inflation_rate": "CPI_INFLATION",
    "cpiaucsl": "CPI_INFLATION",       # official FRED ID
    "cpiaucns": "CPI_INFLATION",
    "unemployment": "UNEMP_RATE",
    "unemployment_rate": "UNEMP_RATE",
    "us_unemployment": "UNEMP_RATE",
    "unrate": "UNEMP_RATE",             # official FRED ID
    "fed_funds": "FED_FUNDS",
    "federal_funds": "FED_FUNDS",
    "federal_funds_rate": "FED_FUNDS",
    "ffr": "FED_FUNDS",
    "fed_funds_rate": "FED_FUNDS",
    "fed_rate": "FED_FUNDS",
    "fedfunds": "FED_FUNDS",            # official FRED ID
    "dff": "FED_FUNDS",
    "gdp_growth": "REAL_GDP_GROWTH",
    "real_gdp_growth": "REAL_GDP_GROWTH",
    "us_gdp_growth": "REAL_GDP_GROWTH",
    "gdp": "REAL_GDP_GROWTH",
    "gdpc1": "REAL_GDP_GROWTH",         # FRED real GDP level — we use growth %
    "a191rl1q225sbea": "REAL_GDP_GROWTH",  # FRED real GDP growth rate
    "a191rl1a225nbea": "REAL_GDP_GROWTH",
}


def _canonical_series(s: str) -> str:
    raw = (s or "").strip()
    if raw.upper() in {"CPI_INFLATION", "UNEMP_RATE", "FED_FUNDS", "REAL_GDP_GROWTH"}:
        return raw.upper()
    key = raw.lower().replace(" ", "_").replace("-", "_")
    return _SERIES_ALIASES.get(key, raw.upper())


def _latest_mtime() -> float:
    latest = 0.0
    for p in _SOURCES:
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _load() -> Tuple[Dict[Tuple[str, int], Dict[str, Any]], int]:
    mtime = _latest_mtime()
    if _CACHE["by_series_year"] and mtime <= _CACHE["mtime"]:
        return _CACHE["by_series_year"], _CACHE["total"]
    by_key: Dict[Tuple[str, int], Dict[str, Any]] = {}
    total = 0
    for path in _SOURCES:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    sid = rec.get("series_id")
                    year = rec.get("year")
                    val = rec.get("value")
                    if not sid or year is None or val is None:
                        continue
                    try:
                        ykey = int(year)
                    except (TypeError, ValueError):
                        continue
                    key = (sid, ykey)
                    if key not in by_key:
                        by_key[key] = rec
                        total += 1
        except OSError:
            continue
    _CACHE["mtime"] = mtime
    _CACHE["by_series_year"] = by_key
    _CACHE["total"] = total
    return by_key, total


def total_entries() -> int:
    _, total = _load()
    return total


def verify_series_value(spec: Dict[str, Any]) -> VerifierResult:
    name = "econ.series_value"
    raw_series = spec.get("series_id") or spec.get("series")
    year = spec.get("year")
    claimed = spec.get("claimed_value")
    if not raw_series or year is None or claimed is None:
        return na(name)
    sid = _canonical_series(str(raw_series))
    try:
        y = int(year)
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "year must be int, claimed_value must be numeric")
    by_key, _ = _load()
    rec = by_key.get((sid, y))
    if not rec:
        return mismatch(
            name,
            f"no data for series {sid} year {y} in the seed; consider scripts/fetch_fred.py for full corpus",
            {"series_id": sid, "year": y, "claimed_value": cl, "looked_up": False},
        )
    actual = float(rec["value"])
    rel_tol = float(spec.get("rel_tol") or 0.10)
    abs_tol = float(spec.get("abs_tol") or 0.5)  # 0.5 percentage points
    threshold = max(abs_tol, abs(actual) * rel_tol)
    # Be forgiving about percent-vs-decimal representation. If the
    # claimed value is suspiciously small relative to actual (looks
    # like a 100x scaling, i.e. someone wrote 6.5% as 0.065), try the
    # rescaled version and use whichever is closer.
    diff_direct = abs(actual - cl)
    diff_rescaled = abs(actual - cl * 100)
    if rec.get("unit", "percent") == "percent" and diff_rescaled < diff_direct:
        cl = cl * 100
        diff = diff_rescaled
        data_note = "claimed value interpreted as decimal-form percentage (×100)"
    else:
        diff = diff_direct
        data_note = ""
    data = {
        "series_id": sid,
        "series_name": rec.get("name", sid),
        "year": y,
        "actual_value": actual,
        "claimed_value": cl,
        "unit": rec.get("unit", "percent"),
        "diff": diff,
        "tol_abs": threshold,
        "note": data_note,
        "source": rec.get("source", "FRED / BLS / BEA (public domain)"),
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{sid} {y}: {actual} {rec.get('unit','percent')} (claim {cl} within ±{threshold:.2f})",
            data,
        )
    return mismatch(
        name,
        f"{sid} {y}: actual {actual}, claimed {cl} (diff {diff:.2f} > tol {threshold:.2f})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("ECON_VERIFY") or {}
    if (ev.get("series_id") or ev.get("series")) and ev.get("year") is not None and ev.get("claimed_value") is not None:
        results.append(verify_series_value(ev))
    if not results:
        results.append(na("fred_economics"))
    return results
