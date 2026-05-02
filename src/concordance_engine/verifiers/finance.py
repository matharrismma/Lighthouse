"""Finance verifier (economic governance umbrella sibling).

Deterministic checks against public-domain financial-math identities:
the accounting equation (assets = liabilities + equity), discounted
cash-flow valuations (NPV, IRR), compound-interest formulas, and
present-value / future-value of money.

All formulas are public-domain (GAAP / IFRS basics, generic finance
literature). No external data required.

Checks performed:

  * finance.accounting_identity
      Assets == Liabilities + Equity (the fundamental balance-sheet
      identity). Tolerance configurable for floating-point.
  * finance.compound_interest
      A = P · (1 + r/n)^(n·t). Future value matches claim.
  * finance.npv
      NPV = Σ CF_t / (1 + r)^t. Computes against a list of cashflows
      and discount rate; matches claim.
  * finance.present_value
      PV = FV / (1 + r)^t. Single-period discount.

FIN_VERIFY packet shape (any subset of fields):
    {
      "assets": 1000.0, "liabilities": 600.0, "equity": 400.0,
      "tolerance": 1e-2,

      "principal": 1000.0, "rate": 0.05,
      "compounding_per_year": 12, "years": 10,
      "claimed_future_value": 1647.01,

      "cashflows": [-1000, 300, 400, 500, 200],
      "discount_rate": 0.10,
      "claimed_npv": 64.36,

      "future_value": 1100.0, "pv_discount_rate": 0.10, "pv_periods": 1,
      "claimed_present_value": 1000.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_accounting_identity(spec: Dict[str, Any]) -> VerifierResult:
    """Assets == Liabilities + Equity."""
    name = "finance.accounting_identity"
    a = spec.get("assets")
    l = spec.get("liabilities")
    e = spec.get("equity")
    if a is None or l is None or e is None:
        return na(name)
    try:
        af, lf, ef = float(a), float(l), float(e)
    except (TypeError, ValueError):
        return error(name, "assets/liabilities/equity must be numeric")
    tol = float(spec.get("tolerance", 1e-2))
    actual_le = lf + ef
    diff = abs(af - actual_le)
    data = {"assets": af, "liabilities": lf, "equity": ef,
            "liab_plus_equity": actual_le, "diff": diff, "tolerance": tol,
            "reference": "Balance Sheet Identity (GAAP / IFRS)"}
    if diff <= tol:
        return confirm(name,
                       f"{af} = {lf} + {ef} = {actual_le} (diff {diff:.4f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"{af} ≠ {lf} + {ef} = {actual_le} (diff {diff:.4f} > tol {tol})",
                    data)


def verify_compound_interest(spec: Dict[str, Any]) -> VerifierResult:
    """A = P · (1 + r/n)^(n·t)."""
    name = "finance.compound_interest"
    p = spec.get("principal")
    r = spec.get("rate")
    n = spec.get("compounding_per_year", 1)
    t = spec.get("years")
    claimed = spec.get("claimed_future_value")
    if p is None or r is None or t is None or claimed is None:
        return na(name)
    try:
        pf = float(p)
        rf = float(r)
        nf = float(n)
        tf = float(t)
        cf = float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if pf < 0:
        return error(name, f"principal cannot be negative ({pf})")
    if nf <= 0:
        return error(name, f"compounding_per_year must be > 0, got {nf}")
    if tf < 0:
        return error(name, f"years cannot be negative ({tf})")
    actual = pf * (1.0 + rf / nf) ** (nf * tf)
    rel_tol = float(spec.get("tolerance_relative", 1e-4))
    abs_tol = float(spec.get("tolerance_absolute", 1e-2))
    diff = abs(actual - cf)
    threshold = max(abs_tol, rel_tol * abs(actual))
    data = {"principal": pf, "rate": rf, "compounding_per_year": nf, "years": tf,
            "actual_future_value": actual, "claimed_future_value": cf,
            "diff": diff, "formula": "A = P·(1 + r/n)^(n·t)"}
    if diff <= threshold:
        return confirm(name,
                       f"FV = {pf}·(1+{rf}/{nf})^({nf}·{tf}) = {actual:.4f} (matches claim {cf}, diff {diff:.4f})",
                       data)
    return mismatch(name,
                    f"FV = {actual:.4f}, claimed {cf} (diff {diff:.4f} > tol {threshold:.4f})",
                    data)


def verify_npv(spec: Dict[str, Any]) -> VerifierResult:
    """NPV = Σ CF_t / (1 + r)^t. CF_0 is the initial outlay (typically negative)."""
    name = "finance.npv"
    cfs = spec.get("cashflows")
    rate = spec.get("discount_rate")
    claimed = spec.get("claimed_npv")
    if cfs is None or rate is None or claimed is None:
        return na(name)
    if not isinstance(cfs, (list, tuple)) or len(cfs) == 0:
        return error(name, "cashflows must be a non-empty list")
    try:
        cfs_f = [float(x) for x in cfs]
        r = float(rate)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "cashflows / discount_rate / claimed_npv must be numeric")
    if r <= -1.0:
        return error(name, f"discount_rate must be > -1, got {r}")
    actual = sum(cf / ((1 + r) ** t) for t, cf in enumerate(cfs_f))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 0.5))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual))
    data = {"cashflows": cfs_f, "discount_rate": r,
            "actual_npv": actual, "claimed_npv": c, "diff": diff,
            "n_periods": len(cfs_f),
            "formula": "NPV = Σ CF_t / (1+r)^t"}
    if diff <= threshold:
        return confirm(name,
                       f"NPV @ {r:.2%} over {len(cfs_f)} periods = {actual:.4f} (matches claim {c})",
                       data)
    return mismatch(name,
                    f"NPV = {actual:.4f}, claimed {c} (diff {diff:.4f} > tol {threshold:.4f})",
                    data)


def verify_present_value(spec: Dict[str, Any]) -> VerifierResult:
    """PV = FV / (1 + r)^t."""
    name = "finance.present_value"
    fv = spec.get("future_value")
    r = spec.get("pv_discount_rate")
    t = spec.get("pv_periods")
    claimed = spec.get("claimed_present_value")
    if fv is None or r is None or t is None or claimed is None:
        return na(name)
    try:
        fvf = float(fv)
        rf = float(r)
        tf = float(t)
        cf = float(claimed)
    except (TypeError, ValueError):
        return error(name, "future_value / pv_discount_rate / pv_periods / claimed_present_value must be numeric")
    if rf <= -1.0:
        return error(name, f"discount_rate must be > -1, got {rf}")
    if tf < 0:
        return error(name, f"periods cannot be negative ({tf})")
    actual = fvf / ((1 + rf) ** tf)
    rel_tol = float(spec.get("tolerance_relative", 1e-4))
    abs_tol = float(spec.get("tolerance_absolute", 1e-2))
    diff = abs(actual - cf)
    threshold = max(abs_tol, rel_tol * abs(actual))
    data = {"future_value": fvf, "discount_rate": rf, "periods": tf,
            "actual_present_value": actual, "claimed_present_value": cf,
            "diff": diff, "formula": "PV = FV / (1+r)^t"}
    if diff <= threshold:
        return confirm(name,
                       f"PV = {fvf}/(1+{rf})^{tf} = {actual:.4f} (matches claim {cf})",
                       data)
    return mismatch(name,
                    f"PV = {actual:.4f}, claimed {cf} (diff {diff:.4f} > tol {threshold:.4f})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    fv = packet.get("FIN_VERIFY") or {}

    if all(k in fv for k in ("assets", "liabilities", "equity")):
        results.append(verify_accounting_identity(fv))
    if all(k in fv for k in ("principal", "rate", "years", "claimed_future_value")):
        results.append(verify_compound_interest(fv))
    if all(k in fv for k in ("cashflows", "discount_rate", "claimed_npv")):
        results.append(verify_npv(fv))
    if all(k in fv for k in ("future_value", "pv_discount_rate", "pv_periods", "claimed_present_value")):
        results.append(verify_present_value(fv))

    if not results:
        results.append(na("finance", "no FIN_VERIFY artifacts present"))
    return results
