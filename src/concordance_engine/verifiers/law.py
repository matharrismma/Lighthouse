"""Law verifier — US federal law, public domain / constitutional text only.

Deterministic checks against publicly available statutory and constitutional
text. Covers contract formation elements, constitutional age requirements,
FLSA overtime arithmetic, and Miranda warning completeness.

IMPORTANT: This verifier outputs CONFIRMED / MISMATCH / NOT_APPLICABLE based
on publicly available legal text. It does NOT give legal advice. Results are
structural/mathematical checks only — consult a licensed attorney for legal
guidance.

LAW_VERIFY packet shape (any subset of fields):
    {
      # contract formation
      "has_offer": true, "has_acceptance": true, "has_consideration": true,
      "has_capacity": true, "has_legality": true, "claimed_contract_valid": true,

      # constitutional age requirement
      "office": "president",   # "president" | "senator" | "representative"
      "age": 36, "claimed_meets_age_requirement": true,

      # FLSA overtime
      "hours_worked": 48, "regular_rate": 20.00, "claimed_overtime_pay": 240.00,

      # Miranda
      "warnings_given": ["You have the right to remain silent. ..."],
      "claimed_miranda_complete": true,
    }

Grid axes: authority/trust (constitutional text as canonical source),
           information/encoding (statutory rule encoding).
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# ---------------------------------------------------------------------------
# law.contract_formation
# ---------------------------------------------------------------------------

_CONTRACT_FORMATION_RULE = (
    "A valid contract requires: offer, acceptance, consideration, capacity, "
    "and legality. All five elements must be present (Restatement (Second) of "
    "Contracts §§ 17, 22, 71, 12, 178 — public domain)."
)


def verify_contract_formation(spec: Dict[str, Any]) -> VerifierResult:
    """All five contract elements must be present for a valid contract.

    Elements: offer, acceptance, consideration, capacity, legality.
    """
    name = "law.contract_formation"
    fields = ("has_offer", "has_acceptance", "has_consideration",
              "has_capacity", "has_legality")
    claimed = spec.get("claimed_contract_valid")
    if claimed is None or not all(f in spec for f in fields):
        return na(name)
    try:
        offer       = bool(spec["has_offer"])
        acceptance  = bool(spec["has_acceptance"])
        consideration = bool(spec["has_consideration"])
        capacity    = bool(spec["has_capacity"])
        legality    = bool(spec["has_legality"])
    except (TypeError, ValueError):
        return error(name, "has_* fields must be boolean")
    actual_valid = all([offer, acceptance, consideration, capacity, legality])
    missing = [f.replace("has_", "") for f, v in
               zip(fields, [offer, acceptance, consideration, capacity, legality])
               if not v]
    data = {
        "rule": _CONTRACT_FORMATION_RULE,
        "source": "Restatement (Second) of Contracts — public domain",
        "has_offer": offer,
        "has_acceptance": acceptance,
        "has_consideration": consideration,
        "has_capacity": capacity,
        "has_legality": legality,
        "actual_valid": actual_valid,
        "claimed_contract_valid": bool(claimed),
        "missing_elements": missing,
    }
    if actual_valid == bool(claimed):
        detail = ("all five contract elements present" if actual_valid
                  else f"contract invalid — missing: {missing}")
        return confirm(name, detail, data)
    if actual_valid and not bool(claimed):
        return mismatch(name,
                        "all five elements present but claimed_contract_valid=False", data)
    return mismatch(name,
                    f"claimed valid but missing elements: {missing}", data)


# ---------------------------------------------------------------------------
# law.constitutional_age_requirement
# ---------------------------------------------------------------------------

_AGE_REQUIREMENTS: Dict[str, int] = {
    "president": 35,
    "senator": 30,
    "representative": 25,
}

_CONST_AGE_RULE = (
    "US Constitutional age minimums: President=35 (Art. II §1), "
    "Senator=30 (Art. I §3), Representative=25 (Art. I §2). "
    "Source: US Constitution — public domain."
)


def verify_constitutional_age_requirement(spec: Dict[str, Any]) -> VerifierResult:
    """Age must meet the constitutional minimum for the specified federal office."""
    name = "law.constitutional_age_requirement"
    office  = spec.get("office")
    age     = spec.get("age")
    claimed = spec.get("claimed_meets_age_requirement")
    if office is None or age is None or claimed is None:
        return na(name)
    office_key = str(office).lower().strip()
    if office_key not in _AGE_REQUIREMENTS:
        return error(name,
                     f"office={office!r} not recognised; expected: "
                     f"{list(_AGE_REQUIREMENTS.keys())}")
    try:
        age_int = int(age)
    except (TypeError, ValueError):
        return error(name, f"age must be an integer, got {age!r}")
    requirement = _AGE_REQUIREMENTS[office_key]
    actual_meets = age_int >= requirement
    data = {
        "rule": _CONST_AGE_RULE,
        "office": office_key,
        "age": age_int,
        "minimum_age": requirement,
        "actual_meets": actual_meets,
        "claimed_meets_age_requirement": bool(claimed),
    }
    if actual_meets == bool(claimed):
        detail = (f"age {age_int} meets {office_key} minimum ({requirement})"
                  if actual_meets
                  else f"age {age_int} does not meet {office_key} minimum ({requirement})")
        return confirm(name, detail, data)
    return mismatch(name,
                    f"actual_meets={actual_meets}, claimed={bool(claimed)} "
                    f"(age {age_int}, minimum {requirement} for {office_key})",
                    data)


# ---------------------------------------------------------------------------
# law.flsa_overtime
# ---------------------------------------------------------------------------

_FLSA_RULE = (
    "FLSA 29 U.S.C. § 207: non-exempt employees must receive overtime pay at "
    "1.5× the regular rate for hours worked beyond 40 per workweek. "
    "Source: Fair Labor Standards Act — public domain federal statute."
)
_FLSA_TOLERANCE = 0.01


def verify_flsa_overtime(spec: Dict[str, Any]) -> VerifierResult:
    """FLSA overtime = max(0, hours - 40) × regular_rate × 1.5."""
    name = "law.flsa_overtime"
    hours   = spec.get("hours_worked")
    rate    = spec.get("regular_rate")
    claimed = spec.get("claimed_overtime_pay")
    if hours is None or rate is None or claimed is None:
        return na(name)
    try:
        h = float(hours)
        r = float(rate)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "hours_worked / regular_rate / claimed_overtime_pay must be numeric")
    if h < 0:
        return error(name, f"hours_worked cannot be negative ({h})")
    if r < 0:
        return error(name, f"regular_rate cannot be negative ({r})")
    overtime_hours = max(0.0, h - 40.0)
    actual_ot_pay  = overtime_hours * r * 1.5
    diff = abs(actual_ot_pay - c)
    data = {
        "rule": _FLSA_RULE,
        "source": "29 U.S.C. § 207 — public domain",
        "hours_worked": h,
        "regular_rate": r,
        "overtime_hours": overtime_hours,
        "actual_overtime_pay": actual_ot_pay,
        "claimed_overtime_pay": c,
        "diff": diff,
        "tolerance": _FLSA_TOLERANCE,
        "formula": "OT_pay = max(0, hours - 40) × rate × 1.5",
    }
    if diff <= _FLSA_TOLERANCE:
        return confirm(name,
                       f"OT = {overtime_hours}h × {r} × 1.5 = {actual_ot_pay:.2f} "
                       f"(matches claim {c:.2f}, diff {diff:.4f})",
                       data)
    return mismatch(name,
                    f"actual OT pay = {actual_ot_pay:.2f}, claimed {c:.2f} "
                    f"(diff {diff:.4f} > tol {_FLSA_TOLERANCE})",
                    data)


# ---------------------------------------------------------------------------
# law.miranda_requirements
# ---------------------------------------------------------------------------

_MIRANDA_RULE = (
    "Miranda v. Arizona, 384 U.S. 436 (1966): prior to custodial interrogation, "
    "a suspect must be informed of: (1) the right to remain silent, "
    "(2) that statements can be used against them in court, "
    "(3) the right to an attorney, and "
    "(4) the right to an appointed attorney if they cannot afford one. "
    "Source: US Supreme Court decision — public domain."
)

_MIRANDA_REQUIRED_KEYWORDS: List[str] = [
    "remain silent",
    "used against",
    "attorney",
    "appointed",
]


def _warnings_contain(warnings: List[str], keyword: str) -> bool:
    """Return True if any warning string contains the keyword (case-insensitive)."""
    kw_lower = keyword.lower()
    return any(kw_lower in w.lower() for w in warnings)


def verify_miranda_requirements(spec: Dict[str, Any]) -> VerifierResult:
    """All four Miranda warning elements must be present in the warnings given."""
    name = "law.miranda_requirements"
    warnings_raw = spec.get("warnings_given")
    claimed      = spec.get("claimed_miranda_complete")
    if warnings_raw is None or claimed is None:
        return na(name)
    if not isinstance(warnings_raw, list):
        return error(name, "warnings_given must be a list of strings")
    # Coerce each element to string
    warnings: List[str] = [str(w) for w in warnings_raw]
    present  = {kw: _warnings_contain(warnings, kw) for kw in _MIRANDA_REQUIRED_KEYWORDS}
    missing  = [kw for kw, found in present.items() if not found]
    actual_complete = len(missing) == 0
    data = {
        "rule": _MIRANDA_RULE,
        "source": "Miranda v. Arizona 384 U.S. 436 (1966) — public domain",
        "required_keywords": _MIRANDA_REQUIRED_KEYWORDS,
        "keyword_presence": present,
        "missing_keywords": missing,
        "actual_complete": actual_complete,
        "claimed_miranda_complete": bool(claimed),
        "warning_count": len(warnings),
    }
    if actual_complete == bool(claimed):
        detail = ("all four Miranda elements present"
                  if actual_complete
                  else f"Miranda incomplete — missing keyword coverage: {missing}")
        return confirm(name, detail, data)
    if actual_complete and not bool(claimed):
        return mismatch(name,
                        "all four elements present but claimed_miranda_complete=False", data)
    return mismatch(name,
                    f"claimed complete but missing keyword coverage: {missing}", data)


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    lv = packet.get("LAW_VERIFY") or {}

    contract_fields = ("has_offer", "has_acceptance", "has_consideration",
                       "has_capacity", "has_legality")
    if any(f in lv for f in contract_fields) and "claimed_contract_valid" in lv:
        results.append(verify_contract_formation(lv))

    if "office" in lv and "age" in lv and "claimed_meets_age_requirement" in lv:
        results.append(verify_constitutional_age_requirement(lv))

    if all(k in lv for k in ("hours_worked", "regular_rate", "claimed_overtime_pay")):
        results.append(verify_flsa_overtime(lv))

    if "warnings_given" in lv and "claimed_miranda_complete" in lv:
        results.append(verify_miranda_requirements(lv))

    if not results:
        results.append(na("law", "no LAW_VERIFY artifacts present"))
    return results
