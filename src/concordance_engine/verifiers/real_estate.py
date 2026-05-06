"""Real estate verifier.

Deterministic checks on property finance calculations using standard
real-estate formulas (public-domain, no proprietary models).

Checks:
  * real_estate.monthly_mortgage  — M = P * [r(1+r)^n] / [(1+r)^n - 1]
  * real_estate.cap_rate          — cap_rate = NOI / property_value
  * real_estate.gross_rent_mult   — GRM = property_price / annual_gross_rent
  * real_estate.loan_to_value     — LTV = loan_amount / appraised_value
  * real_estate.debt_service_cov  — DSCR = NOI / annual_debt_service
  * real_estate.rental_yield      — yield = annual_rent / property_value

RE_VERIFY packet shape (any subset):
    {
      "loan_principal": 300000, "annual_rate": 0.065,
      "loan_term_months": 360,
      "claimed_monthly_payment": 1896.20,

      "net_operating_income": 24000, "property_value": 400000,
      "claimed_cap_rate": 0.06,

      "property_price": 300000, "annual_gross_rent": 24000,
      "claimed_grm": 12.5,

      "loan_amount": 240000, "appraised_value": 300000,
      "claimed_ltv": 0.80,

      "annual_debt_service": 22755,
      "claimed_dscr": 1.055,

      "annual_rent": 18000,
      "claimed_rental_yield": 0.045,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_monthly_mortgage(spec: Dict[str, Any]) -> VerifierResult:
    """M = P * [r(1+r)^n] / [(1+r)^n - 1]  where r = monthly rate."""
    name = "real_estate.monthly_mortgage"
    P = spec.get("loan_principal")
    annual_rate = spec.get("annual_rate")
    n = spec.get("loan_term_months")
    claimed = spec.get("claimed_monthly_payment")
    if any(v is None for v in (P, annual_rate, n, claimed)):
        return na(name)
    try:
        Pf, ar, nf, c = float(P), float(annual_rate), float(n), float(claimed)
    except (TypeError, ValueError):
        return error(name, "loan_principal, annual_rate, loan_term_months, claimed_monthly_payment must be numeric")
    if ar <= 0 or nf <= 0 or Pf <= 0:
        return error(name, "loan_principal, annual_rate, and loan_term_months must be positive")
    r = ar / 12.0
    actual = Pf * (r * (1 + r) ** nf) / ((1 + r) ** nf - 1)
    tol = float(spec.get("tolerance", max(0.01, actual * 0.001)))
    data = {"loan_principal": Pf, "annual_rate": ar, "monthly_rate": round(r, 6),
            "loan_term_months": nf,
            "actual_monthly_payment": round(actual, 2), "claimed_monthly_payment": c,
            "formula": "M = P * [r(1+r)^n] / [(1+r)^n - 1]"}
    if abs(actual - c) <= tol:
        return confirm(name, f"M = ${actual:.2f}/mo (matches claim)", data)
    return mismatch(name, f"M = ${actual:.2f}/mo, claimed ${c:.2f}", data)


def verify_cap_rate(spec: Dict[str, Any]) -> VerifierResult:
    """Capitalization rate = NOI / property_value"""
    name = "real_estate.cap_rate"
    noi = spec.get("net_operating_income")
    pv = spec.get("property_value")
    claimed = spec.get("claimed_cap_rate")
    if any(v is None for v in (noi, pv, claimed)):
        return na(name)
    try:
        nf, pvf, c = float(noi), float(pv), float(claimed)
    except (TypeError, ValueError):
        return error(name, "net_operating_income, property_value, claimed_cap_rate must be numeric")
    if pvf <= 0:
        return error(name, f"property_value must be > 0, got {pvf}")
    actual = nf / pvf
    tol = float(spec.get("tolerance", 0.001))
    data = {"noi": nf, "property_value": pvf,
            "actual_cap_rate": round(actual, 6), "claimed_cap_rate": c,
            "formula": "cap_rate = NOI / property_value"}
    if abs(actual - c) <= tol:
        return confirm(name, f"cap rate = {actual:.4f} ({actual*100:.2f}%) (matches claim)", data)
    return mismatch(name, f"cap rate = {actual:.4f}, claimed {c:.4f}", data)


def verify_gross_rent_multiplier(spec: Dict[str, Any]) -> VerifierResult:
    """GRM = property_price / annual_gross_rent"""
    name = "real_estate.gross_rent_mult"
    price = spec.get("property_price")
    rent = spec.get("annual_gross_rent")
    claimed = spec.get("claimed_grm")
    if any(v is None for v in (price, rent, claimed)):
        return na(name)
    try:
        pf, rf, c = float(price), float(rent), float(claimed)
    except (TypeError, ValueError):
        return error(name, "property_price, annual_gross_rent, claimed_grm must be numeric")
    if rf <= 0:
        return error(name, f"annual_gross_rent must be > 0, got {rf}")
    actual = pf / rf
    tol = float(spec.get("tolerance", 0.05))
    data = {"property_price": pf, "annual_gross_rent": rf,
            "actual_grm": round(actual, 4), "claimed_grm": c,
            "formula": "GRM = property_price / annual_gross_rent"}
    if abs(actual - c) <= tol:
        return confirm(name, f"GRM = {actual:.2f} (matches claim)", data)
    return mismatch(name, f"GRM = {actual:.2f}, claimed {c:.2f}", data)


def verify_loan_to_value(spec: Dict[str, Any]) -> VerifierResult:
    """LTV = loan_amount / appraised_value"""
    name = "real_estate.loan_to_value"
    loan = spec.get("loan_amount")
    appraised = spec.get("appraised_value")
    claimed = spec.get("claimed_ltv")
    if any(v is None for v in (loan, appraised, claimed)):
        return na(name)
    try:
        lf, af, c = float(loan), float(appraised), float(claimed)
    except (TypeError, ValueError):
        return error(name, "loan_amount, appraised_value, claimed_ltv must be numeric")
    if af <= 0:
        return error(name, f"appraised_value must be > 0, got {af}")
    actual = lf / af
    tol = float(spec.get("tolerance", 0.001))
    pmi_required = actual > 0.80
    data = {"loan_amount": lf, "appraised_value": af,
            "actual_ltv": round(actual, 6), "claimed_ltv": c,
            "pmi_likely_required": pmi_required,
            "formula": "LTV = loan_amount / appraised_value"}
    if abs(actual - c) <= tol:
        return confirm(name, f"LTV = {actual:.4f} ({actual*100:.1f}%) (matches claim)", data)
    return mismatch(name, f"LTV = {actual:.4f}, claimed {c:.4f}", data)


def verify_dscr(spec: Dict[str, Any]) -> VerifierResult:
    """Debt Service Coverage Ratio = NOI / annual_debt_service"""
    name = "real_estate.debt_service_cov"
    noi = spec.get("net_operating_income")
    ads = spec.get("annual_debt_service")
    claimed = spec.get("claimed_dscr")
    if any(v is None for v in (noi, ads, claimed)):
        return na(name)
    try:
        nf, af, c = float(noi), float(ads), float(claimed)
    except (TypeError, ValueError):
        return error(name, "net_operating_income, annual_debt_service, claimed_dscr must be numeric")
    if af <= 0:
        return error(name, f"annual_debt_service must be > 0, got {af}")
    actual = nf / af
    tol = float(spec.get("tolerance", 0.005))
    data = {"noi": nf, "annual_debt_service": af,
            "actual_dscr": round(actual, 4), "claimed_dscr": c,
            "lender_threshold": 1.25,
            "meets_lender_threshold": actual >= 1.25,
            "formula": "DSCR = NOI / annual_debt_service"}
    if abs(actual - c) <= tol:
        return confirm(name, f"DSCR = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"DSCR = {actual:.4f}, claimed {c:.4f}", data)


def verify_rental_yield(spec: Dict[str, Any]) -> VerifierResult:
    """Gross rental yield = annual_rent / property_value"""
    name = "real_estate.rental_yield"
    rent = spec.get("annual_rent")
    pv = spec.get("property_value")
    claimed = spec.get("claimed_rental_yield")
    if any(v is None for v in (rent, pv, claimed)):
        return na(name)
    try:
        rf, pvf, c = float(rent), float(pv), float(claimed)
    except (TypeError, ValueError):
        return error(name, "annual_rent, property_value, claimed_rental_yield must be numeric")
    if pvf <= 0:
        return error(name, f"property_value must be > 0, got {pvf}")
    actual = rf / pvf
    tol = float(spec.get("tolerance", 0.001))
    data = {"annual_rent": rf, "property_value": pvf,
            "actual_yield": round(actual, 6), "claimed_yield": c,
            "formula": "yield = annual_rent / property_value"}
    if abs(actual - c) <= tol:
        return confirm(name, f"rental yield = {actual:.4f} ({actual*100:.2f}%) (matches claim)", data)
    return mismatch(name, f"rental yield = {actual:.4f}, claimed {c:.4f}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    rv = packet.get("RE_VERIFY") or {}
    if "loan_principal" in rv and "annual_rate" in rv and "claimed_monthly_payment" in rv:
        results.append(verify_monthly_mortgage(rv))
    if "net_operating_income" in rv and "property_value" in rv and "claimed_cap_rate" in rv:
        results.append(verify_cap_rate(rv))
    if "property_price" in rv and "annual_gross_rent" in rv and "claimed_grm" in rv:
        results.append(verify_gross_rent_multiplier(rv))
    if "loan_amount" in rv and "appraised_value" in rv and "claimed_ltv" in rv:
        results.append(verify_loan_to_value(rv))
    if "net_operating_income" in rv and "annual_debt_service" in rv and "claimed_dscr" in rv:
        results.append(verify_dscr(rv))
    if "annual_rent" in rv and "property_value" in rv and "claimed_rental_yield" in rv:
        results.append(verify_rental_yield(rv))
    if not results:
        results.append(na("real_estate", "no RE_VERIFY artifacts present"))
    return results
