"""Labor / employment verifier.

Deterministic checks on wage, overtime, and compensation calculations
using US FLSA standards and public-domain formulas. All thresholds are
from public law (FLSA 29 USC § 207, IRS Publication 15-T brackets).

Checks:
  * labor.gross_pay           — hourly_rate * hours_worked
  * labor.overtime_pay        — FLSA: regular (≤40h) + 1.5x (>40h)
  * labor.annual_to_hourly    — annual / 2080 (52 weeks × 40 hours)
  * labor.take_home_pay       — gross * (1 - total_tax_rate)
  * labor.minimum_wage_check  — compare claimed_hourly_rate to threshold

LABOR_VERIFY packet shape (any subset):
    {
      "hourly_rate": 18.50, "hours_worked": 45,
      "claimed_gross_pay": 850.75,

      "regular_hours": 40, "overtime_hours": 5,
      "claimed_overtime_pay": 878.75,

      "annual_salary": 52000,
      "claimed_hourly_equivalent": 25.0,

      "gross_pay": 1000, "total_tax_rate": 0.28,
      "claimed_take_home": 720.0,

      "claimed_hourly_rate": 7.25,
      "minimum_wage_threshold": 7.25,
      "claimed_compliant": true,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

# US federal minimum wage (effective 2009, public law)
_US_FEDERAL_MIN_WAGE = 7.25
_STANDARD_ANNUAL_HOURS = 2080  # 52 weeks × 40 hours


def verify_gross_pay(spec: Dict[str, Any]) -> VerifierResult:
    """Gross pay = hourly_rate * hours_worked (no overtime split)."""
    name = "labor.gross_pay"
    rate = spec.get("hourly_rate")
    hours = spec.get("hours_worked")
    claimed = spec.get("claimed_gross_pay")
    if any(v is None for v in (rate, hours, claimed)):
        return na(name)
    try:
        rf, hf, c = float(rate), float(hours), float(claimed)
    except (TypeError, ValueError):
        return error(name, "hourly_rate, hours_worked, claimed_gross_pay must be numeric")
    if rf < 0 or hf < 0:
        return error(name, "hourly_rate and hours_worked must be non-negative")
    actual = rf * hf
    tol = float(spec.get("tolerance", max(0.01, actual * 0.001)))
    data = {"hourly_rate": rf, "hours_worked": hf,
            "actual_gross_pay": round(actual, 2), "claimed_gross_pay": c,
            "formula": "gross = hourly_rate * hours_worked"}
    if abs(actual - c) <= tol:
        return confirm(name, f"gross pay = ${actual:.2f} (matches claim)", data)
    return mismatch(name, f"gross pay = ${actual:.2f}, claimed ${c:.2f}", data)


def verify_overtime_pay(spec: Dict[str, Any]) -> VerifierResult:
    """FLSA overtime: regular_hours * rate + overtime_hours * rate * 1.5"""
    name = "labor.overtime_pay"
    rate = spec.get("hourly_rate")
    reg_h = spec.get("regular_hours")
    ot_h = spec.get("overtime_hours", 0)
    claimed = spec.get("claimed_overtime_pay")
    if any(v is None for v in (rate, reg_h, claimed)):
        return na(name)
    try:
        rf, rh, oh, c = float(rate), float(reg_h), float(ot_h), float(claimed)
    except (TypeError, ValueError):
        return error(name, "hourly_rate, regular_hours, overtime_hours, claimed_overtime_pay must be numeric")
    if rf < 0 or rh < 0 or oh < 0:
        return error(name, "all inputs must be non-negative")
    actual = rf * rh + rf * 1.5 * oh
    tol = float(spec.get("tolerance", max(0.01, actual * 0.001)))
    data = {"hourly_rate": rf, "regular_hours": rh, "overtime_hours": oh,
            "overtime_multiplier": 1.5,
            "actual_total_pay": round(actual, 2), "claimed_total_pay": c,
            "formula": "pay = rate * reg_hours + rate * 1.5 * ot_hours (FLSA)",
            "standard": "FLSA 29 USC §207"}
    if abs(actual - c) <= tol:
        return confirm(name, f"FLSA pay = ${actual:.2f} (matches claim)", data)
    return mismatch(name, f"FLSA pay = ${actual:.2f}, claimed ${c:.2f}", data)


def verify_annual_to_hourly(spec: Dict[str, Any]) -> VerifierResult:
    """Hourly equivalent = annual_salary / 2080 (52 × 40 hours)"""
    name = "labor.annual_to_hourly"
    annual = spec.get("annual_salary")
    claimed = spec.get("claimed_hourly_equivalent")
    if annual is None or claimed is None:
        return na(name)
    annual_hours = float(spec.get("annual_hours", _STANDARD_ANNUAL_HOURS))
    try:
        af, c = float(annual), float(claimed)
    except (TypeError, ValueError):
        return error(name, "annual_salary and claimed_hourly_equivalent must be numeric")
    if annual_hours <= 0:
        return error(name, f"annual_hours must be > 0, got {annual_hours}")
    actual = af / annual_hours
    tol = float(spec.get("tolerance", max(0.01, actual * 0.001)))
    data = {"annual_salary": af, "annual_hours": annual_hours,
            "actual_hourly": round(actual, 4), "claimed_hourly": c,
            "formula": f"hourly = annual / {annual_hours}"}
    if abs(actual - c) <= tol:
        return confirm(name, f"hourly = ${actual:.4f} (matches claim)", data)
    return mismatch(name, f"hourly = ${actual:.4f}, claimed ${c:.4f}", data)


def verify_take_home_pay(spec: Dict[str, Any]) -> VerifierResult:
    """Take-home = gross * (1 - total_tax_rate)"""
    name = "labor.take_home_pay"
    gross = spec.get("gross_pay")
    tax_rate = spec.get("total_tax_rate")
    claimed = spec.get("claimed_take_home")
    if any(v is None for v in (gross, tax_rate, claimed)):
        return na(name)
    try:
        gf, tf, c = float(gross), float(tax_rate), float(claimed)
    except (TypeError, ValueError):
        return error(name, "gross_pay, total_tax_rate, claimed_take_home must be numeric")
    if not (0.0 <= tf < 1.0):
        return error(name, f"total_tax_rate must be 0.0–0.99, got {tf}")
    actual = gf * (1.0 - tf)
    tol = float(spec.get("tolerance", max(0.01, actual * 0.001)))
    data = {"gross_pay": gf, "total_tax_rate": tf,
            "actual_take_home": round(actual, 2), "claimed_take_home": c,
            "formula": "take_home = gross * (1 - total_tax_rate)"}
    if abs(actual - c) <= tol:
        return confirm(name, f"take-home = ${actual:.2f} (matches claim)", data)
    return mismatch(name, f"take-home = ${actual:.2f}, claimed ${c:.2f}", data)


def verify_minimum_wage_check(spec: Dict[str, Any]) -> VerifierResult:
    """Verify a wage meets or exceeds a minimum threshold."""
    name = "labor.minimum_wage_check"
    rate = spec.get("claimed_hourly_rate")
    threshold = spec.get("minimum_wage_threshold", _US_FEDERAL_MIN_WAGE)
    claimed_compliant = spec.get("claimed_compliant")
    if rate is None or claimed_compliant is None:
        return na(name)
    try:
        rf, tf = float(rate), float(threshold)
    except (TypeError, ValueError):
        return error(name, "claimed_hourly_rate and minimum_wage_threshold must be numeric")
    actually_compliant = rf >= tf
    data = {"claimed_hourly_rate": rf, "minimum_wage_threshold": tf,
            "compliant": actually_compliant,
            "standard": f"US federal minimum wage ${_US_FEDERAL_MIN_WAGE}/hr (FLSA)"}
    if bool(claimed_compliant) == actually_compliant:
        status = "compliant" if actually_compliant else "non-compliant"
        return confirm(name, f"${rf:.2f}/hr is {status} vs ${tf:.2f} threshold (claim correct)", data)
    return mismatch(name,
                    f"${rf:.2f}/hr {'meets' if actually_compliant else 'does not meet'} "
                    f"${tf:.2f} threshold — claim says {'compliant' if claimed_compliant else 'non-compliant'}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    lv = packet.get("LABOR_VERIFY") or {}
    if "hourly_rate" in lv and "hours_worked" in lv and "claimed_gross_pay" in lv:
        results.append(verify_gross_pay(lv))
    if "hourly_rate" in lv and "regular_hours" in lv and "claimed_overtime_pay" in lv:
        results.append(verify_overtime_pay(lv))
    if "annual_salary" in lv and "claimed_hourly_equivalent" in lv:
        results.append(verify_annual_to_hourly(lv))
    if "gross_pay" in lv and "total_tax_rate" in lv and "claimed_take_home" in lv:
        results.append(verify_take_home_pay(lv))
    if "claimed_hourly_rate" in lv and "claimed_compliant" in lv:
        results.append(verify_minimum_wage_check(lv))
    if not results:
        results.append(na("labor", "no LABOR_VERIFY artifacts present"))
    return results
