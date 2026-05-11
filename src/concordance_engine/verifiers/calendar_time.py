"""Calendar / time verifier (cross-cutting like scripture — useful in
many other domains' packets, especially governance which already
relies on epoch math).

Deterministic checks against canonical calendar rules: Gregorian leap
years, ISO-8601 timestamp validity, day-of-week derivation, and
duration arithmetic. All checks use Python stdlib datetime; no
external dependencies.

Public-domain reference: Gregorian calendar (universally adopted
civil time standard); ISO 8601 (international standard, widely
documented in public-domain summaries).

Checks performed:

  * calendar_time.leap_year
      Year is leap iff (year % 4 == 0) and not (year % 100 == 0 and
      year % 400 != 0). Matches claim.
  * calendar_time.iso8601_valid
      Timestamp string parses as a valid ISO 8601 datetime.
  * calendar_time.day_of_week
      Stdlib datetime computes weekday for a given date; matches
      claimed weekday name.
  * calendar_time.duration_addition
      start_iso + duration_seconds == claimed_end_iso (exact match
      modulo timezone normalization).

CAL_VERIFY packet shape (any subset of fields):
    {
      "year": 2024,
      "claimed_leap": true,

      "iso8601_string": "2026-05-02T15:30:00Z",
      "claimed_iso8601_valid": true,

      "date_iso": "2026-05-02",
      "claimed_day_of_week": "Saturday",

      "start_iso": "2026-05-02T00:00:00Z",
      "duration_seconds": 86400,
      "claimed_end_iso": "2026-05-03T00:00:00Z",
    }
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_WEEKDAY_NAMES = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def _is_leap_gregorian(year: int) -> bool:
    """Gregorian calendar leap year rule."""
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0


def verify_leap_year(spec: Dict[str, Any]) -> VerifierResult:
    name = "calendar_time.leap_year"
    year = spec.get("year")
    # Accept both "claimed_leap" and the natural-language alias LLMs often use
    claimed = spec.get("claimed_leap")
    if claimed is None:
        claimed = spec.get("claimed_is_leap_year")
    if year is None or claimed is None:
        return na(name)
    try:
        y = int(year)
    except (TypeError, ValueError):
        return error(name, f"year must be an integer, got {year!r}")
    actual = _is_leap_gregorian(y)
    data = {"year": y, "actual_leap": actual, "claimed_leap": bool(claimed),
            "rule": "Gregorian: divisible by 4, except century not divisible by 400"}
    if actual == bool(claimed):
        return confirm(name, f"{y} leap year = {actual} (matches claim)", data)
    return mismatch(name, f"{y} leap year = {actual}, claimed {bool(claimed)}", data)


def verify_iso8601_valid(spec: Dict[str, Any]) -> VerifierResult:
    name = "calendar_time.iso8601_valid"
    s = spec.get("iso8601_string")
    claimed = spec.get("claimed_iso8601_valid")
    if s is None or claimed is None:
        return na(name)
    try:
        # datetime.fromisoformat handles most ISO 8601 timestamps in 3.11+.
        # For 'Z' suffix (UTC), Python pre-3.11 fails; we replace Z → +00:00.
        normalized = str(s).replace("Z", "+00:00") if isinstance(s, str) else s
        dt = datetime.fromisoformat(normalized)
        actual = True
    except (ValueError, TypeError):
        dt = None
        actual = False
    data = {"input": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "parsed": dt.isoformat() if dt else None}
    if actual == bool(claimed):
        return confirm(name, f"ISO 8601 valid = {actual} (matches claim)", data)
    return mismatch(name,
                    f"ISO 8601 valid = {actual}, claimed {bool(claimed)} for {s!r}",
                    data)


def verify_day_of_week(spec: Dict[str, Any]) -> VerifierResult:
    name = "calendar_time.day_of_week"
    date_iso = spec.get("date_iso")
    claimed = spec.get("claimed_day_of_week")
    if date_iso is None or claimed is None:
        return na(name)
    try:
        normalized = str(date_iso).replace("Z", "+00:00") if isinstance(date_iso, str) else date_iso
        dt = datetime.fromisoformat(normalized)
    except (ValueError, TypeError):
        return error(name, f"date_iso could not be parsed: {date_iso!r}")
    weekday_idx = dt.weekday()  # Monday = 0
    actual_name = _WEEKDAY_NAMES[weekday_idx]
    claimed_norm = str(claimed).lower().strip()
    data = {"date": dt.date().isoformat(), "actual": actual_name,
            "claimed": claimed_norm, "iso_weekday": weekday_idx + 1}
    if actual_name == claimed_norm:
        return confirm(name,
                       f"{dt.date().isoformat()} is a {actual_name} (matches claim)",
                       data)
    return mismatch(name,
                    f"{dt.date().isoformat()} is a {actual_name}, claimed {claimed_norm}",
                    data)


def verify_duration_addition(spec: Dict[str, Any]) -> VerifierResult:
    name = "calendar_time.duration_addition"
    start = spec.get("start_iso")
    duration = spec.get("duration_seconds")
    claimed_end = spec.get("claimed_end_iso")
    if start is None or duration is None or claimed_end is None:
        return na(name)
    try:
        start_norm = str(start).replace("Z", "+00:00") if isinstance(start, str) else start
        dt_start = datetime.fromisoformat(start_norm)
    except (ValueError, TypeError):
        return error(name, f"start_iso parse failure: {start!r}")
    try:
        d = float(duration)
    except (TypeError, ValueError):
        return error(name, f"duration_seconds must be numeric, got {duration!r}")
    try:
        claimed_norm = str(claimed_end).replace("Z", "+00:00") if isinstance(claimed_end, str) else claimed_end
        dt_claimed = datetime.fromisoformat(claimed_norm)
    except (ValueError, TypeError):
        return error(name, f"claimed_end_iso parse failure: {claimed_end!r}")
    actual = dt_start + timedelta(seconds=d)
    # Normalize to UTC for comparison (handle naive vs aware mix).
    if actual.tzinfo is None and dt_claimed.tzinfo is not None:
        actual = actual.replace(tzinfo=dt_claimed.tzinfo)
    elif actual.tzinfo is not None and dt_claimed.tzinfo is None:
        dt_claimed = dt_claimed.replace(tzinfo=actual.tzinfo)
    if actual.tzinfo:
        actual_utc = actual.astimezone(timezone.utc)
        claimed_utc = dt_claimed.astimezone(timezone.utc)
    else:
        actual_utc = actual
        claimed_utc = dt_claimed
    diff_sec = abs((actual_utc - claimed_utc).total_seconds())
    tol = float(spec.get("tolerance_seconds", 0))
    data = {"start": dt_start.isoformat(), "duration_seconds": d,
            "actual_end": actual.isoformat(), "claimed_end": dt_claimed.isoformat(),
            "diff_seconds": diff_sec, "tolerance_seconds": tol}
    if diff_sec <= tol:
        return confirm(name,
                       f"{dt_start.isoformat()} + {d}s = {actual.isoformat()} (matches claim)",
                       data)
    return mismatch(name,
                    f"{dt_start.isoformat()} + {d}s = {actual.isoformat()}, "
                    f"claimed {dt_claimed.isoformat()} (diff {diff_sec}s)",
                    data)


# ── IANA timezone math (Python stdlib zoneinfo) ────────────────────────
# Removed: verify_timezone_exists. Whether "America/New_York" is a valid
# IANA tz name is a political/legal authority claim (the IANA committee
# accepted the name) — it doesn't reduce to math. On the build queue at
# data/build_queue/queue.jsonl.
#
# Kept: verify_utc_offset. Given a tz, computing the UTC offset at a
# datetime is mechanical math (DST rules + offset table), so it survives.


def verify_utc_offset(spec: Dict[str, Any]) -> VerifierResult:
    """Check that a claimed UTC offset for a (timezone, datetime) is correct.
    Useful for DST claims and historical-rule claims."""
    name = "calendar_time.utc_offset"
    tz = (spec.get("timezone") or "").strip()
    iso = (spec.get("at_iso") or "").strip()
    claimed_offset = spec.get("claimed_utc_offset_hours")
    if not tz or not iso or claimed_offset is None:
        return na(name)
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        return na(name)
    try:
        zi = ZoneInfo(tz)
    except Exception:
        return mismatch(name, f"timezone {tz!r} not found in tz database", {"timezone": tz})
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=zi)
        else:
            dt = dt.astimezone(zi)
    except Exception as exc:
        return error(name, f"at_iso parse failure: {exc}")
    actual_offset = dt.utcoffset().total_seconds() / 3600.0
    try:
        co = float(claimed_offset)
    except (TypeError, ValueError):
        return error(name, "claimed_utc_offset_hours must be numeric")
    tol = float(spec.get("offset_tolerance_hours") or 0.001)
    data = {
        "timezone": tz, "at": iso,
        "actual_offset_hours": actual_offset,
        "claimed_offset_hours": co,
        "diff_hours": abs(actual_offset - co),
        "source": "Python stdlib zoneinfo (IANA tz database)",
    }
    if abs(actual_offset - co) <= tol:
        return confirm(
            name,
            f"{tz} at {iso}: UTC offset {actual_offset:+.2f} h (matches claim)",
            data,
        )
    return mismatch(
        name,
        f"{tz} at {iso}: actual UTC offset {actual_offset:+.2f} h, claimed {co:+.2f}",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CAL_VERIFY") or {}

    if "year" in cv and ("claimed_leap" in cv or "claimed_is_leap_year" in cv):
        results.append(verify_leap_year(cv))
    if "iso8601_string" in cv and "claimed_iso8601_valid" in cv:
        results.append(verify_iso8601_valid(cv))
    if "date_iso" in cv and "claimed_day_of_week" in cv:
        results.append(verify_day_of_week(cv))
    if all(k in cv for k in ("start_iso", "duration_seconds", "claimed_end_iso")):
        results.append(verify_duration_addition(cv))
    if "timezone" in cv and "at_iso" in cv and "claimed_utc_offset_hours" in cv:
        results.append(verify_utc_offset(cv))

    if not results:
        results.append(na("calendar_time", "no CAL_VERIFY artifacts present"))
    return results
