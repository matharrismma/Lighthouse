"""Tests for the calendar_time verifier."""
from __future__ import annotations

from concordance_engine.verifiers import calendar_time as cal


# ── leap year ──────────────────────────────────────────────────────────

def test_leap_2024_yes():
    r = cal.verify_leap_year({"year": 2024, "claimed_leap": True})
    assert r.status == "CONFIRMED"


def test_leap_2023_no():
    r = cal.verify_leap_year({"year": 2023, "claimed_leap": False})
    assert r.status == "CONFIRMED"


def test_leap_2000_yes_century_div_400():
    r = cal.verify_leap_year({"year": 2000, "claimed_leap": True})
    assert r.status == "CONFIRMED"


def test_leap_1900_no_century_not_div_400():
    r = cal.verify_leap_year({"year": 1900, "claimed_leap": False})
    assert r.status == "CONFIRMED"


def test_leap_wrong_claim():
    r = cal.verify_leap_year({"year": 2023, "claimed_leap": True})
    assert r.status == "MISMATCH"


def test_leap_non_int_year_error():
    r = cal.verify_leap_year({"year": "twenty-twenty-four", "claimed_leap": True})
    assert r.status == "ERROR"


# ── ISO 8601 validity ──────────────────────────────────────────────────

def test_iso8601_valid_z_suffix():
    r = cal.verify_iso8601_valid({
        "iso8601_string": "2026-05-02T15:30:00Z",
        "claimed_iso8601_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_iso8601_valid_offset():
    r = cal.verify_iso8601_valid({
        "iso8601_string": "2026-05-02T15:30:00+00:00",
        "claimed_iso8601_valid": True,
    })
    assert r.status == "CONFIRMED"


def test_iso8601_invalid_string():
    r = cal.verify_iso8601_valid({
        "iso8601_string": "not a timestamp",
        "claimed_iso8601_valid": False,
    })
    assert r.status == "CONFIRMED"


def test_iso8601_wrong_claim():
    r = cal.verify_iso8601_valid({
        "iso8601_string": "garbage",
        "claimed_iso8601_valid": True,
    })
    assert r.status == "MISMATCH"


# ── day of week ────────────────────────────────────────────────────────

def test_day_of_week_2026_05_02_saturday():
    r = cal.verify_day_of_week({
        "date_iso": "2026-05-02", "claimed_day_of_week": "saturday",
    })
    assert r.status == "CONFIRMED"


def test_day_of_week_2024_01_01_monday():
    r = cal.verify_day_of_week({
        "date_iso": "2024-01-01", "claimed_day_of_week": "Monday",
    })
    assert r.status == "CONFIRMED"


def test_day_of_week_wrong_claim():
    r = cal.verify_day_of_week({
        "date_iso": "2026-05-02", "claimed_day_of_week": "monday",
    })
    assert r.status == "MISMATCH"


def test_day_of_week_invalid_date_error():
    r = cal.verify_day_of_week({
        "date_iso": "not a date", "claimed_day_of_week": "monday",
    })
    assert r.status == "ERROR"


# ── duration addition ──────────────────────────────────────────────────

def test_duration_one_day():
    r = cal.verify_duration_addition({
        "start_iso": "2026-05-02T00:00:00+00:00",
        "duration_seconds": 86400,
        "claimed_end_iso": "2026-05-03T00:00:00+00:00",
    })
    assert r.status == "CONFIRMED"


def test_duration_one_hour():
    r = cal.verify_duration_addition({
        "start_iso": "2026-05-02T00:00:00+00:00",
        "duration_seconds": 3600,
        "claimed_end_iso": "2026-05-02T01:00:00+00:00",
    })
    assert r.status == "CONFIRMED"


def test_duration_wrong_claim():
    r = cal.verify_duration_addition({
        "start_iso": "2026-05-02T00:00:00+00:00",
        "duration_seconds": 3600,
        "claimed_end_iso": "2026-05-03T00:00:00+00:00",
    })
    assert r.status == "MISMATCH"


# ── run dispatch ───────────────────────────────────────────────────────

def test_run_no_artifacts_returns_na():
    r = cal.run({"domain": "calendar_time"})
    assert len(r) == 1 and r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all():
    packet = {
        "domain": "calendar_time",
        "CAL_VERIFY": {
            "year": 2024, "claimed_leap": True,
            "iso8601_string": "2026-05-02T15:30:00Z", "claimed_iso8601_valid": True,
            "date_iso": "2026-05-02", "claimed_day_of_week": "saturday",
            "start_iso": "2026-05-02T00:00:00+00:00",
            "duration_seconds": 86400,
            "claimed_end_iso": "2026-05-03T00:00:00+00:00",
        },
    }
    results = cal.run(packet)
    assert len(results) == 4
    assert all(r.status == "CONFIRMED" for r in results)
