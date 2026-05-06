"""History / chronology verifier.

Deterministic arithmetic checks for historical date and time-span claims.
Handles BCE/CE (BC/AD) year arithmetic including the absence of a year 0
in the proleptic Julian/Gregorian calendar used in historical scholarship.

Sign convention used throughout:
    Positive integer → CE year (e.g. 1 = 1 CE)
    Negative integer → BCE year (e.g. -44 = 44 BCE, i.e. Julius Caesar's death)
    There is no year 0: 1 BCE (−1 in this scheme) is immediately followed by 1 CE (+1).

HIST_VERIFY packet shape (any subset of fields):
    {
      # year elapsed arithmetic
      "from_year": -44, "to_year": 1453, "claimed_elapsed_years": 1497,

      # century assignment (CE only)
      "year_CE": 1776, "claimed_century": 18,

      # era classification
      "year": -44, "claimed_era": "BCE",

      # elapsed from a BCE year to a CE year (no year 0 helper)
      "from_BCE": 44, "to_CE": 1453, "claimed_elapsed": 1496,

      # decade assignment
      "year_CE": 1985, "claimed_decade_start": 1980,
    }

Grid axes: time/sequence (chronological ordering and arithmetic),
           information/encoding (era/century labelling conventions).
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# ---------------------------------------------------------------------------
# history_chronology.year_arithmetic
# ---------------------------------------------------------------------------

_YEAR_ARITH_RULE = (
    "Elapsed years = to_year − from_year using the sign convention "
    "(positive = CE, negative = BCE). There is no year 0 in historical "
    "counting; callers must encode BCE years as negative integers accordingly. "
    "Tolerance: ±1 year."
)


def verify_year_arithmetic(spec: Dict[str, Any]) -> VerifierResult:
    """Elapsed years between two signed years (positive=CE, negative=BCE).

    actual_elapsed = to_year - from_year.
    Tolerance: absolute 1 year.
    """
    name = "history_chronology.year_arithmetic"
    from_y  = spec.get("from_year")
    to_y    = spec.get("to_year")
    claimed = spec.get("claimed_elapsed_years")
    if from_y is None or to_y is None or claimed is None:
        return na(name)
    try:
        fy  = int(from_y)
        ty  = int(to_y)
        cl  = int(claimed)
    except (TypeError, ValueError):
        return error(name, "from_year / to_year / claimed_elapsed_years must be integers")
    actual = ty - fy
    diff = abs(actual - cl)
    tol  = 1
    data = {
        "rule": _YEAR_ARITH_RULE,
        "from_year": fy,
        "to_year": ty,
        "actual_elapsed_years": actual,
        "claimed_elapsed_years": cl,
        "diff": diff,
        "tolerance": tol,
        "note": "sign convention: positive=CE, negative=BCE; no year 0",
    }
    if diff <= tol:
        return confirm(name,
                       f"elapsed {actual} years ({fy} → {ty}) matches claim {cl} (diff {diff})",
                       data)
    return mismatch(name,
                    f"actual elapsed {actual}, claimed {cl} (diff {diff} > tol {tol})",
                    data)


# ---------------------------------------------------------------------------
# history_chronology.century_assignment
# ---------------------------------------------------------------------------

_CENTURY_RULE = (
    "A CE year belongs to century N where N = ceil(year / 100). "
    "Year 1-100 → 1st century; 101-200 → 2nd century; etc. "
    "Only positive (CE) years are accepted by this check."
)


def verify_century_assignment(spec: Dict[str, Any]) -> VerifierResult:
    """CE year → century number. 1-100 = 1st, 101-200 = 2nd, etc."""
    name = "history_chronology.century_assignment"
    year    = spec.get("year_CE")
    claimed = spec.get("claimed_century")
    if year is None or claimed is None:
        return na(name)
    try:
        y  = int(year)
        cl = int(claimed)
    except (TypeError, ValueError):
        return error(name, "year_CE / claimed_century must be integers")
    if y <= 0:
        return error(name, f"year_CE must be a positive CE year, got {y}")
    actual = math.ceil(y / 100)
    data = {
        "rule": _CENTURY_RULE,
        "year_CE": y,
        "actual_century": actual,
        "claimed_century": cl,
        "formula": "century = ceil(year_CE / 100)",
    }
    if actual == cl:
        return confirm(name,
                       f"year {y} CE is in the {actual}{'st' if actual == 1 else 'nd' if actual == 2 else 'rd' if actual == 3 else 'th'} century",
                       data)
    return mismatch(name,
                    f"year {y} CE → century {actual}, claimed {cl}",
                    data)


# ---------------------------------------------------------------------------
# history_chronology.era_classification
# ---------------------------------------------------------------------------

_ERA_RULE = (
    "A year is BCE/BC if year < 0 (or 0, treated as BCE/transition). "
    "A year is CE/AD if year > 0. "
    "Accepted aliases: BCE/BC for Before Common Era; CE/AD for Common Era."
)

_BCE_ALIASES = frozenset(["bce", "bc"])
_CE_ALIASES  = frozenset(["ce", "ad"])


def verify_era_classification(spec: Dict[str, Any]) -> VerifierResult:
    """Year sign → BCE or CE era label."""
    name = "history_chronology.era_classification"
    year    = spec.get("year")
    claimed = spec.get("claimed_era")
    if year is None or claimed is None:
        return na(name)
    try:
        y = int(year)
    except (TypeError, ValueError):
        return error(name, f"year must be an integer, got {year!r}")
    claimed_norm = str(claimed).strip().upper()
    # Validate the claimed label is a known alias
    if claimed_norm.lower() not in (_BCE_ALIASES | _CE_ALIASES):
        return error(name,
                     f"claimed_era={claimed!r} not recognised; expected BCE, BC, CE, or AD")
    actual_is_bce = (y <= 0)
    claimed_is_bce = claimed_norm.lower() in _BCE_ALIASES
    data = {
        "rule": _ERA_RULE,
        "year": y,
        "actual_is_BCE": actual_is_bce,
        "claimed_era": claimed_norm,
        "claimed_is_BCE": claimed_is_bce,
    }
    if actual_is_bce == claimed_is_bce:
        actual_label = "BCE" if actual_is_bce else "CE"
        return confirm(name,
                       f"year {y} is {actual_label}, claim={claimed_norm} agrees",
                       data)
    actual_label = "BCE" if actual_is_bce else "CE"
    return mismatch(name,
                    f"year {y} is {actual_label} but claimed {claimed_norm}",
                    data)


# ---------------------------------------------------------------------------
# history_chronology.elapsed_years_bce_to_ce
# ---------------------------------------------------------------------------

_BCE_TO_CE_RULE = (
    "Elapsed years from a BCE year to a CE year: elapsed = from_BCE + to_CE - 1. "
    "The '−1' accounts for the absence of a year 0 in historical calendars "
    "(1 BCE → 1 CE is 1 year, not 2). "
    "Both inputs must be positive integers. Tolerance: ±1 year."
)


def verify_elapsed_years_bce_to_ce(spec: Dict[str, Any]) -> VerifierResult:
    """from_BCE (positive) + to_CE (positive) → elapsed = from_BCE + to_CE - 1."""
    name = "history_chronology.elapsed_years_bce_to_ce"
    from_bce = spec.get("from_BCE")
    to_ce    = spec.get("to_CE")
    claimed  = spec.get("claimed_elapsed")
    if from_bce is None or to_ce is None or claimed is None:
        return na(name)
    try:
        fb = int(from_bce)
        tc = int(to_ce)
        cl = int(claimed)
    except (TypeError, ValueError):
        return error(name, "from_BCE / to_CE / claimed_elapsed must be integers")
    if fb <= 0:
        return error(name, f"from_BCE must be a positive integer, got {fb}")
    if tc <= 0:
        return error(name, f"to_CE must be a positive integer, got {tc}")
    actual  = fb + tc - 1
    diff    = abs(actual - cl)
    tol     = 1
    data = {
        "rule": _BCE_TO_CE_RULE,
        "from_BCE": fb,
        "to_CE": tc,
        "actual_elapsed": actual,
        "claimed_elapsed": cl,
        "diff": diff,
        "tolerance": tol,
        "formula": "elapsed = from_BCE + to_CE - 1  (no year 0)",
    }
    if diff <= tol:
        return confirm(name,
                       f"{fb} BCE → {tc} CE = {actual} years (matches claim {cl}, diff {diff})",
                       data)
    return mismatch(name,
                    f"{fb} BCE → {tc} CE = {actual} years, claimed {cl} (diff {diff} > tol {tol})",
                    data)


# ---------------------------------------------------------------------------
# history_chronology.decade_assignment
# ---------------------------------------------------------------------------

_DECADE_RULE = (
    "The decade a CE year belongs to starts at (year // 10) * 10. "
    "1980 → decade start 1980 (covers 1980-1989); "
    "1990 → decade start 1990; 2000 → 2000; etc. "
    "Negative (BCE) years are not handled by this check."
)


def verify_decade_assignment(spec: Dict[str, Any]) -> VerifierResult:
    """year_CE → decade_start = (year // 10) * 10."""
    name = "history_chronology.decade_assignment"
    year    = spec.get("year_CE")
    claimed = spec.get("claimed_decade_start")
    if year is None or claimed is None:
        return na(name)
    try:
        y  = int(year)
        cl = int(claimed)
    except (TypeError, ValueError):
        return error(name, "year_CE / claimed_decade_start must be integers")
    actual = (y // 10) * 10
    data = {
        "rule": _DECADE_RULE,
        "year_CE": y,
        "actual_decade_start": actual,
        "claimed_decade_start": cl,
        "formula": "decade_start = (year_CE // 10) * 10",
    }
    if actual == cl:
        return confirm(name,
                       f"year {y} CE → decade starting {actual} (matches claim {cl})",
                       data)
    return mismatch(name,
                    f"year {y} CE → decade start {actual}, claimed {cl}",
                    data)


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    hv = packet.get("HIST_VERIFY") or {}

    if all(k in hv for k in ("from_year", "to_year", "claimed_elapsed_years")):
        results.append(verify_year_arithmetic(hv))

    # century_assignment and decade_assignment share year_CE; trigger independently
    # by checking for the discriminating field
    if "year_CE" in hv and "claimed_century" in hv:
        results.append(verify_century_assignment(hv))

    if "year" in hv and "claimed_era" in hv:
        results.append(verify_era_classification(hv))

    if all(k in hv for k in ("from_BCE", "to_CE", "claimed_elapsed")):
        results.append(verify_elapsed_years_bce_to_ce(hv))

    if "year_CE" in hv and "claimed_decade_start" in hv:
        results.append(verify_decade_assignment(hv))

    if not results:
        results.append(na("history_chronology", "no HIST_VERIFY artifacts present"))
    return results
