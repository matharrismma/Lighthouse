"""Economics verifier.

Deterministic checks on economic and financial calculations using
public-domain formulas (standard economic theory, no proprietary models).
All formulas are textbook / public-domain.

Checks:
  * economics.simple_interest      — I = P * r * t
  * economics.compound_interest    — A = P * (1 + r/n)^(n*t)
  * economics.present_value        — PV = FV / (1 + r)^t
  * economics.future_value         — FV = PV * (1 + r)^t
  * economics.rule_of_72           — years ≈ 72 / rate_percent
  * economics.inflation_adjusted   — real = nominal / (1 + rate)^years
  * economics.inflation_rate       — inflation = (CPI_t - CPI_prev) / CPI_prev
  * economics.gdp_per_capita       — gdp_per_capita = gdp / population
  * economics.price_elasticity     — PED = (Δq/q) / (Δp/p)

ECON_VERIFY packet shape (any subset):
    {
      "principal": 1000, "rate": 0.05, "time_years": 3,
      "claimed_simple_interest": 150,

      "compounding_periods": 12,
      "claimed_compound_amount": 1161.62,

      "future_value": 1000, "discount_rate": 0.05, "time_years": 3,
      "claimed_present_value": 863.84,

      "present_value": 1000, "growth_rate": 0.05, "time_years": 3,
      "claimed_future_value": 1157.63,

      "rate_percent": 7,
      "claimed_doubling_years": 10.3,

      "nominal_value": 1000, "inflation_rate": 0.03, "years": 10,
      "claimed_real_value": 744.09,

      "gdp": 21000000000000, "population": 331000000,
      "claimed_gdp_per_capita": 63444,

      "pct_change_quantity": -10, "pct_change_price": 5,
      "claimed_price_elasticity": -2.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_simple_interest(spec: Dict[str, Any]) -> VerifierResult:
    """I = P * r * t"""
    name = "economics.simple_interest"
    P = spec.get("principal")
    r = spec.get("rate")
    t = spec.get("time_years")
    claimed = spec.get("claimed_simple_interest")
    if any(v is None for v in (P, r, t, claimed)):
        return na(name)
    try:
        Pf, rf, tf, c = float(P), float(r), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, "principal, rate, time_years, claimed_simple_interest must be numeric")
    actual = Pf * rf * tf
    tol = float(spec.get("tolerance", max(0.01, abs(actual) * 0.001)))
    data = {"principal": Pf, "rate": rf, "time_years": tf,
            "actual_interest": round(actual, 4), "claimed_interest": c,
            "formula": "I = P * r * t"}
    if abs(actual - c) <= tol:
        return confirm(name, f"I = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"I = {actual:.4f}, claimed {c}", data)


def verify_compound_interest(spec: Dict[str, Any]) -> VerifierResult:
    """A = P * (1 + r/n)^(n*t)"""
    name = "economics.compound_interest"
    P = spec.get("principal")
    r = spec.get("rate")
    t = spec.get("time_years")
    n = spec.get("compounding_periods", 1)
    claimed = spec.get("claimed_compound_amount")
    if any(v is None for v in (P, r, t, claimed)):
        return na(name)
    try:
        Pf, rf, tf, nf, c = float(P), float(r), float(t), float(n), float(claimed)
    except (TypeError, ValueError):
        return error(name, "principal, rate, time_years, claimed_compound_amount must be numeric")
    if nf <= 0:
        return error(name, f"compounding_periods must be > 0, got {nf}")
    actual = Pf * (1 + rf / nf) ** (nf * tf)
    tol = float(spec.get("tolerance", max(0.01, abs(actual) * 0.001)))
    data = {"principal": Pf, "rate": rf, "time_years": tf,
            "compounding_periods": nf,
            "actual_amount": round(actual, 4), "claimed_amount": c,
            "formula": "A = P * (1 + r/n)^(n*t)"}
    if abs(actual - c) <= tol:
        return confirm(name, f"A = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"A = {actual:.4f}, claimed {c}", data)


def verify_present_value(spec: Dict[str, Any]) -> VerifierResult:
    """PV = FV / (1 + r)^t"""
    name = "economics.present_value"
    FV = spec.get("future_value")
    r = spec.get("discount_rate")
    t = spec.get("time_years")
    claimed = spec.get("claimed_present_value")
    if any(v is None for v in (FV, r, t, claimed)):
        return na(name)
    try:
        FVf, rf, tf, c = float(FV), float(r), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, "future_value, discount_rate, time_years, claimed_present_value must be numeric")
    if (1 + rf) ** tf == 0:
        return error(name, "discount rate produces zero denominator")
    actual = FVf / (1 + rf) ** tf
    tol = float(spec.get("tolerance", max(0.01, abs(actual) * 0.001)))
    data = {"future_value": FVf, "discount_rate": rf, "time_years": tf,
            "actual_pv": round(actual, 4), "claimed_pv": c,
            "formula": "PV = FV / (1 + r)^t"}
    if abs(actual - c) <= tol:
        return confirm(name, f"PV = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"PV = {actual:.4f}, claimed {c}", data)


def verify_future_value(spec: Dict[str, Any]) -> VerifierResult:
    """FV = PV * (1 + r)^t"""
    name = "economics.future_value"
    PV = spec.get("present_value")
    r = spec.get("growth_rate")
    t = spec.get("time_years")
    claimed = spec.get("claimed_future_value")
    if any(v is None for v in (PV, r, t, claimed)):
        return na(name)
    try:
        PVf, rf, tf, c = float(PV), float(r), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, "present_value, growth_rate, time_years, claimed_future_value must be numeric")
    actual = PVf * (1 + rf) ** tf
    tol = float(spec.get("tolerance", max(0.01, abs(actual) * 0.001)))
    data = {"present_value": PVf, "growth_rate": rf, "time_years": tf,
            "actual_fv": round(actual, 4), "claimed_fv": c,
            "formula": "FV = PV * (1 + r)^t"}
    if abs(actual - c) <= tol:
        return confirm(name, f"FV = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"FV = {actual:.4f}, claimed {c}", data)


def verify_rule_of_72(spec: Dict[str, Any]) -> VerifierResult:
    """Years to double ≈ 72 / rate_percent"""
    name = "economics.rule_of_72"
    rate_pct = spec.get("rate_percent")
    claimed = spec.get("claimed_doubling_years")
    if rate_pct is None or claimed is None:
        return na(name)
    try:
        rp, c = float(rate_pct), float(claimed)
    except (TypeError, ValueError):
        return error(name, "rate_percent and claimed_doubling_years must be numeric")
    if rp <= 0:
        return error(name, f"rate_percent must be > 0, got {rp}")
    actual = 72.0 / rp
    tol = float(spec.get("tolerance", 0.5))
    data = {"rate_percent": rp, "actual_doubling_years": round(actual, 2),
            "claimed_doubling_years": c, "formula": "years ≈ 72 / rate_percent"}
    if abs(actual - c) <= tol:
        return confirm(name, f"72 / {rp}% = {actual:.2f} years (matches claim)", data)
    return mismatch(name, f"doubling time = {actual:.2f} years, claimed {c}", data)


def verify_inflation_adjusted(spec: Dict[str, Any]) -> VerifierResult:
    """real_value = nominal_value / (1 + inflation_rate)^years"""
    name = "economics.inflation_adjusted"
    nominal = spec.get("nominal_value")
    rate = spec.get("inflation_rate")
    years = spec.get("years")
    claimed = spec.get("claimed_real_value")
    if any(v is None for v in (nominal, rate, years, claimed)):
        return na(name)
    try:
        nf, rf, yf, c = float(nominal), float(rate), float(years), float(claimed)
    except (TypeError, ValueError):
        return error(name, "nominal_value, inflation_rate, years, claimed_real_value must be numeric")
    actual = nf / (1 + rf) ** yf
    tol = float(spec.get("tolerance", max(0.01, abs(actual) * 0.001)))
    data = {"nominal_value": nf, "inflation_rate": rf, "years": yf,
            "actual_real_value": round(actual, 4), "claimed_real_value": c,
            "formula": "real = nominal / (1 + inflation_rate)^years"}
    if abs(actual - c) <= tol:
        return confirm(name, f"real value = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"real value = {actual:.4f}, claimed {c}", data)


def verify_inflation_rate(spec: Dict[str, Any]) -> VerifierResult:
    """Inflation as the rate of change of a price index:
        inflation = (CPI_t - CPI_prev) / CPI_prev

    The two index LEVELS are operator-supplied measured inputs — the BLS
    aggregate level is authority, not math, and is NOT confirmed here. The
    engine confirms only that the rate is computed correctly from the two
    supplied levels. claimed_inflation_rate may be a fraction (0.065) or a
    percent (6.5); both are accepted.
    """
    name = "economics.inflation_rate"
    cpi_t = spec.get("cpi_current")
    cpi_prev = spec.get("cpi_previous")
    claimed = spec.get("claimed_inflation_rate")
    if any(v is None for v in (cpi_t, cpi_prev, claimed)):
        return na(name)
    try:
        ct, cp, c = float(cpi_t), float(cpi_prev), float(claimed)
    except (TypeError, ValueError):
        return error(name, "cpi_current, cpi_previous, claimed_inflation_rate must be numeric")
    if cp == 0:
        return error(name, "cpi_previous cannot be zero (division)")
    actual_frac = (ct - cp) / cp
    actual_pct = actual_frac * 100.0
    tol_frac = float(spec.get("tolerance", 0.0005))
    tol_pct = tol_frac * 100.0
    matched = abs(actual_frac - c) <= tol_frac or abs(actual_pct - c) <= tol_pct
    data = {"cpi_current": ct, "cpi_previous": cp,
            "actual_rate_fraction": round(actual_frac, 6),
            "actual_rate_percent": round(actual_pct, 4),
            "claimed_inflation_rate": c,
            "formula": "inflation = (CPI_t - CPI_prev) / CPI_prev"}
    if matched:
        return confirm(name, f"inflation = {actual_pct:.4f}% (matches claim {c})", data)
    return mismatch(name, f"inflation = {actual_pct:.4f}% / {actual_frac:.6f}, claimed {c}", data)


def verify_gdp_per_capita(spec: Dict[str, Any]) -> VerifierResult:
    """GDP per capita = GDP / population"""
    name = "economics.gdp_per_capita"
    gdp = spec.get("gdp")
    pop = spec.get("population")
    claimed = spec.get("claimed_gdp_per_capita")
    if any(v is None for v in (gdp, pop, claimed)):
        return na(name)
    try:
        gf, pf, c = float(gdp), float(pop), float(claimed)
    except (TypeError, ValueError):
        return error(name, "gdp, population, claimed_gdp_per_capita must be numeric")
    if pf <= 0:
        return error(name, f"population must be > 0, got {pf}")
    actual = gf / pf
    tol = float(spec.get("tolerance", max(1.0, abs(actual) * 0.005)))
    data = {"gdp": gf, "population": pf,
            "actual_gdp_per_capita": round(actual, 2), "claimed_gdp_per_capita": c,
            "formula": "GDP per capita = GDP / population"}
    if abs(actual - c) <= tol:
        return confirm(name, f"GDP per capita = {actual:.2f} (matches claim)", data)
    return mismatch(name, f"GDP per capita = {actual:.2f}, claimed {c}", data)


def verify_price_elasticity(spec: Dict[str, Any]) -> VerifierResult:
    """PED = (% change in quantity) / (% change in price)"""
    name = "economics.price_elasticity"
    pct_q = spec.get("pct_change_quantity")
    pct_p = spec.get("pct_change_price")
    claimed = spec.get("claimed_price_elasticity")
    if any(v is None for v in (pct_q, pct_p, claimed)):
        return na(name)
    try:
        qf, pf, c = float(pct_q), float(pct_p), float(claimed)
    except (TypeError, ValueError):
        return error(name, "pct_change_quantity, pct_change_price, claimed_price_elasticity must be numeric")
    if pf == 0:
        return error(name, "pct_change_price cannot be zero")
    actual = qf / pf
    tol = float(spec.get("tolerance", 0.05))
    data = {"pct_change_quantity": qf, "pct_change_price": pf,
            "actual_ped": round(actual, 4), "claimed_ped": c,
            "interpretation": "elastic" if abs(actual) > 1 else "inelastic",
            "formula": "PED = (%Δquantity) / (%Δprice)"}
    if abs(actual - c) <= tol:
        return confirm(name, f"PED = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"PED = {actual:.4f}, claimed {c}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("ECON_VERIFY") or {}
    if "principal" in ev and "rate" in ev and "time_years" in ev:
        if "claimed_simple_interest" in ev:
            results.append(verify_simple_interest(ev))
        if "claimed_compound_amount" in ev:
            results.append(verify_compound_interest(ev))
    if "future_value" in ev and "discount_rate" in ev and "claimed_present_value" in ev:
        results.append(verify_present_value(ev))
    if "present_value" in ev and "growth_rate" in ev and "claimed_future_value" in ev:
        results.append(verify_future_value(ev))
    if "rate_percent" in ev and "claimed_doubling_years" in ev:
        results.append(verify_rule_of_72(ev))
    if "nominal_value" in ev and "inflation_rate" in ev and "claimed_real_value" in ev:
        results.append(verify_inflation_adjusted(ev))
    if "cpi_current" in ev and "cpi_previous" in ev and "claimed_inflation_rate" in ev:
        results.append(verify_inflation_rate(ev))
    if "gdp" in ev and "population" in ev and "claimed_gdp_per_capita" in ev:
        results.append(verify_gdp_per_capita(ev))
    if "pct_change_quantity" in ev and "pct_change_price" in ev and "claimed_price_elasticity" in ev:
        results.append(verify_price_elasticity(ev))
    if not results:
        results.append(na("economics", "no ECON_VERIFY artifacts present"))
    return results
