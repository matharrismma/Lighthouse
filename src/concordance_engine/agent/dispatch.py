"""Rule-based NL → domain + spec dispatch.

Each rule is a (pattern, domain, extractor) triple:
  - pattern: compiled regex that must match the input text
  - domain:  the verify_{domain} tool to call
  - extractor: function(match, text) -> dict of spec fields

Rules run in priority order; first match wins. The caller gets a
DispatchResult with the domain and extracted spec — it still has to
call the verifier. This layer only classifies and extracts.

Design constraint: every rule must be a deterministic regex. No ML,
no API calls, no probabilistic inference. That means this layer can
run on a microSD with zero network access. The oracle (any AI) is
called by the endpoint only when no rule matches, and its output is
logged as a training example so future rules can replace it.

Coverage added here:
  chemistry, physics, statistics, mathematics, computer_science,
  economics, labor, real_estate, construction, soil_science,
  medicine, cybersecurity, nutrition, finance, governance
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class DispatchResult:
    domain: str
    spec: Dict[str, Any]
    rule_id: str
    confidence: float = 1.0  # rule-based is always 1.0; oracle-derived < 1.0
    raw_text: str = ""


# ── helpers ───────────────────────────────────────────────────────────

def _num(s: str) -> float:
    """Parse a number string, handling commas and % signs."""
    return float(s.replace(",", "").replace("%", "").strip())


def _yn(s: str) -> bool:
    return s.lower().strip() in ("yes", "true", "1", "y", "suitable", "secure", "compliant")


# ── Rule definitions ─────────────────────────────────────────────────

_RULES: List[Tuple[str, re.Pattern, str, Callable]] = []


def _rule(rule_id: str, pattern: str, domain: str):
    """Decorator to register a rule."""
    def decorator(fn: Callable) -> Callable:
        _RULES.append((rule_id, re.compile(pattern, re.IGNORECASE), domain, fn))
        return fn
    return decorator


# ── CHEMISTRY ────────────────────────────────────────────────────────

@_rule("chem_balance", r"(?:is|verify|check|balance)\s+(.+?)\s*(?:balanced|->|→)", "chemistry")
def _chem_balance(m, text):
    return {"equation": m.group(1).strip()}


@_rule("chem_molar_mass", r"molar\s+mass\s+of\s+([A-Za-z0-9\(\)]+)", "chemistry")
def _chem_molar_mass(m, text):
    return {"formula": m.group(1).strip(), "claimed_molar_mass": None}


# ── PHYSICS ──────────────────────────────────────────────────────────

@_rule("phys_force", r"F\s*=\s*m\s*[*×]\s*a.*?(\d+\.?\d*)\s*(?:kg|kilogram).*?(\d+\.?\d*)\s*m/s", "physics")
def _phys_force(m, text):
    return {"mass_kg": _num(m.group(1)), "acceleration_ms2": _num(m.group(2))}


@_rule("phys_ke", r"kinetic\s+energy.*?(\d+\.?\d*)\s*kg.*?(\d+\.?\d*)\s*m/s", "physics")
def _phys_ke(m, text):
    return {"mass_kg": _num(m.group(1)), "velocity_ms": _num(m.group(2))}


# ── STATISTICS ───────────────────────────────────────────────────────

@_rule("stat_pvalue", r"p[\s-]?value\s*[=:]\s*(\d+\.?\d*)\s*.*?n\s*=\s*(\d+)", "statistics")
def _stat_pvalue(m, text):
    return {"p_value": _num(m.group(1)), "n": int(m.group(2))}


# ── MATHEMATICS ──────────────────────────────────────────────────────

@_rule("math_quadratic", r"(?:solve|roots?\s+of)\s+(\d+\.?\d*)x\^?2\s*([+-]\s*\d+\.?\d*)x\s*([+-]\s*\d+\.?\d*)", "mathematics")
def _math_quad(m, text):
    return {"a": _num(m.group(1)), "b": _num(m.group(2).replace(" ", "")),
            "c": _num(m.group(3).replace(" ", ""))}


@_rule("math_derivative", r"(?:derivative|d/dx)\s*(?:of)?\s*(.+?)\s*=\s*(.+)", "mathematics")
def _math_deriv(m, text):
    return {"expression": m.group(1).strip(), "claimed_derivative": m.group(2).strip()}


# ── COMPUTER SCIENCE ─────────────────────────────────────────────────

@_rule("cs_complexity", r"(merge\s+sort|quick\s+sort|bubble\s+sort|binary\s+search|linear\s+search|bfs|dfs|dijkstra|heap\s+sort).+?O\(([^)]+)\)", "computer_science")
def _cs_complexity(m, text):
    return {"algorithm": m.group(1).strip(), "claimed_complexity": f"O({m.group(2)})"}


@_rule("cs_bit_ops", r"(\d+)\s*(?:<<|left\s+shift)\s*(\d+)", "computer_science")
def _cs_shift(m, text):
    return {"value": int(m.group(1)), "shift": int(m.group(2))}


# ── ECONOMICS ────────────────────────────────────────────────────────

@_rule("econ_simple_interest", r"simple\s+interest.*?\$?(\d[\d,]*\.?\d*)\s*(?:at|@)\s*(\d+\.?\d*)\s*%.*?(\d+\.?\d*)\s*(?:year|yr)", "economics")
def _econ_si(m, text):
    P, r, t = _num(m.group(1)), _num(m.group(2)) / 100, _num(m.group(3))
    return {"principal": P, "rate": r, "time_years": t,
            "claimed_simple_interest": P * r * t}


@_rule("econ_compound_interest", r"compound\s+interest.*?\$?(\d[\d,]*\.?\d*)\s*(?:at|@)\s*(\d+\.?\d*)\s*%.*?(\d+\.?\d*)\s*(?:year|yr)", "economics")
def _econ_ci(m, text):
    P, r, t = _num(m.group(1)), _num(m.group(2)) / 100, _num(m.group(3))
    n = 12.0  # assume monthly compounding
    A = P * (1 + r / n) ** (n * t)
    return {"principal": P, "rate": r, "time_years": t,
            "compounding_periods": n, "claimed_compound_amount": round(A, 2)}


@_rule("econ_rule_72", r"rule\s+of\s+72.*?(\d+\.?\d*)\s*%", "economics")
def _econ_r72(m, text):
    rate = _num(m.group(1))
    return {"rate_percent": rate, "claimed_doubling_years": round(72.0 / rate, 2)}


@_rule("econ_pv", r"present\s+value.*?\$?(\d[\d,]*\.?\d*).*?(\d+\.?\d*)\s*%.*?(\d+\.?\d*)\s*(?:year|yr)", "economics")
def _econ_pv(m, text):
    import math
    FV, r, t = _num(m.group(1)), _num(m.group(2)) / 100, _num(m.group(3))
    return {"future_value": FV, "discount_rate": r, "time_years": t,
            "claimed_present_value": round(FV / (1 + r) ** t, 2)}


@_rule("econ_gdp_capita", r"gdp\s+per\s+capita.*?\$?(\d[\d,]*\.?\d*)\s*(?:trillion|billion|million)?.*?(\d[\d,]*\.?\d*)\s*(?:million|billion|people|population)", "economics")
def _econ_gdp(m, text):
    raw_gdp = _num(m.group(1))
    raw_pop = _num(m.group(2))
    t = text.lower()
    if "trillion" in t:
        raw_gdp *= 1e12
    elif "billion" in t and "gdp" in t:
        raw_gdp *= 1e9
    if "million" in t and "population" in t or "million people" in t:
        raw_pop *= 1e6
    elif "billion" in t and "population" in t:
        raw_pop *= 1e9
    return {"gdp": raw_gdp, "population": raw_pop,
            "claimed_gdp_per_capita": round(raw_gdp / raw_pop, 2)}


# ── LABOR ────────────────────────────────────────────────────────────

@_rule("labor_gross_pay", r"\$?(\d+\.?\d*)\s*(?:per\s+hour|/hr|/hour).*?(\d+\.?\d*)\s*hours?", "labor")
def _labor_gross(m, text):
    rate, hours = _num(m.group(1)), _num(m.group(2))
    return {"hourly_rate": rate, "hours_worked": hours,
            "claimed_gross_pay": round(rate * hours, 2)}


@_rule("labor_overtime", r"overtime.*?\$?(\d+\.?\d*)\s*(?:per\s+hour|/hr).*?(\d+\.?\d*)\s*(?:regular|normal|straight).*?(\d+\.?\d*)\s*(?:overtime|ot)", "labor")
def _labor_ot(m, text):
    rate, reg, ot = _num(m.group(1)), _num(m.group(2)), _num(m.group(3))
    total = rate * reg + rate * 1.5 * ot
    return {"hourly_rate": rate, "regular_hours": reg, "overtime_hours": ot,
            "claimed_overtime_pay": round(total, 2)}


@_rule("labor_annual_to_hourly", r"\$?(\d[\d,]*\.?\d*)\s*(?:per\s+year|annual|/year|salary).*?hourly", "labor")
def _labor_a2h(m, text):
    annual = _num(m.group(1))
    return {"annual_salary": annual,
            "claimed_hourly_equivalent": round(annual / 2080, 4)}


# ── REAL ESTATE ──────────────────────────────────────────────────────

@_rule("re_mortgage", r"mortgage.*?\$?(\d[\d,]*\.?\d*)\s*(?:loan|at|@)\s*(\d+\.?\d*)\s*%.*?(\d+)\s*(?:year|yr)", "real_estate")
def _re_mortgage(m, text):
    import math
    P, annual_rate, years = _num(m.group(1)), _num(m.group(2)) / 100, int(m.group(3))
    r = annual_rate / 12
    n = years * 12
    M = P * (r * (1 + r) ** n) / ((1 + r) ** n - 1)
    return {"loan_principal": P, "annual_rate": annual_rate,
            "loan_term_months": n, "claimed_monthly_payment": round(M, 2)}


@_rule("re_cap_rate", r"cap\s+rate.*?(?:noi|income)\s*[=:$]?\s*\$?(\d[\d,]*\.?\d*).*?(?:value|price)\s*[=:$]?\s*\$?(\d[\d,]*\.?\d*)", "real_estate")
def _re_cap(m, text):
    noi, val = _num(m.group(1)), _num(m.group(2))
    return {"net_operating_income": noi, "property_value": val,
            "claimed_cap_rate": round(noi / val, 6)}


@_rule("re_ltv", r"ltv|loan.to.value.*?\$?(\d[\d,]*\.?\d*).*?(?:appraised|valued?)\s+(?:at\s+)?\$?(\d[\d,]*\.?\d*)", "real_estate")
def _re_ltv(m, text):
    loan, val = _num(m.group(1)), _num(m.group(2))
    return {"loan_amount": loan, "appraised_value": val,
            "claimed_ltv": round(loan / val, 6)}


# ── CONSTRUCTION ─────────────────────────────────────────────────────

@_rule("constr_concrete", r"concrete.*?(\d+\.?\d*)\s*(?:m|meter).*?(\d+\.?\d*)\s*(?:m|meter).*?(\d+\.?\d*)\s*(?:m|meter|thick)", "construction")
def _constr_conc(m, text):
    L, W, D = _num(m.group(1)), _num(m.group(2)), _num(m.group(3))
    return {"length_m": L, "width_m": W, "depth_m": D,
            "claimed_concrete_m3": round(L * W * D, 4)}


@_rule("constr_tiles", r"(?:floor\s+)?tiles?.*?(\d+\.?\d*)\s*(?:m²|m2|sq\.?\s*m).*?(\d+\.?\d*)\s*(?:m²|m2|sq\.?\s*m)\s*(?:each|per\s+tile|tile\s+size)", "construction")
def _constr_tiles(m, text):
    import math
    area, tile_size = _num(m.group(1)), _num(m.group(2))
    waste = 0.10
    tiles = math.ceil(math.ceil(area / tile_size) * (1 + waste))
    return {"tile_area_m2": area, "tile_size_m2": tile_size,
            "waste_factor": waste, "claimed_tile_count": tiles}


# ── SOIL SCIENCE ─────────────────────────────────────────────────────

@_rule("soil_ph", r"(?:soil\s+)?ph\s*[=:]\s*(\d+\.?\d*).*?(maize|corn|wheat|rice|soybean|potato|tomato|cassava|sorghum|cotton|groundnut|peanut|coffee|tea|barley)", "soil_science")
def _soil_ph(m, text):
    from concordance_engine.verifiers.soil_science import _CROP_PH
    ph, crop = _num(m.group(1)), m.group(2).lower()
    rng = _CROP_PH.get(crop, (5.5, 7.0))
    return {"soil_ph": ph, "crop": crop,
            "claimed_ph_suitable": rng[0] <= ph <= rng[1]}


@_rule("soil_irrigation", r"et0\s*[=:]\s*(\d+\.?\d*).*?kc\s*[=:]\s*(\d+\.?\d*)", "soil_science")
def _soil_irr(m, text):
    et0, kc = _num(m.group(1)), _num(m.group(2))
    return {"reference_et0_mm_per_day": et0, "crop_coefficient": kc,
            "claimed_etc_mm_per_day": round(et0 * kc, 4)}


# ── MEDICINE ─────────────────────────────────────────────────────────

@_rule("med_bmi", r"bmi.*?(\d+\.?\d*)\s*kg.*?(\d+\.?\d*)\s*(?:m|meter)", "medicine")
def _med_bmi(m, text):
    w, h = _num(m.group(1)), _num(m.group(2))
    bmi = w / h ** 2
    from concordance_engine.verifiers.medicine import _bmi_class
    return {"weight_kg": w, "height_m": h,
            "claimed_bmi": round(bmi, 2), "claimed_bmi_class": _bmi_class(bmi)}


@_rule("med_dosage", r"(\d+\.?\d*)\s*mg/kg.*?(\d+\.?\d*)\s*kg", "medicine")
def _med_dose(m, text):
    dpk, w = _num(m.group(1)), _num(m.group(2))
    return {"dose_mg_per_kg": dpk, "weight_kg": w,
            "claimed_dose_mg": round(dpk * w, 2)}


@_rule("med_map", r"map.*?systolic.*?(\d+\.?\d*).*?diastolic.*?(\d+\.?\d*)", "medicine")
def _med_map(m, text):
    sys, dia = _num(m.group(1)), _num(m.group(2))
    map_val = dia + (sys - dia) / 3.0
    return {"systolic": sys, "diastolic": dia,
            "claimed_map_mmhg": round(map_val, 2)}


# ── CYBERSECURITY ────────────────────────────────────────────────────

@_rule("cyber_entropy", r"(?:password\s+)?entropy.*?(\d+)\s*(?:-?char|-?character).*?(\d+)\s*(?:charset|characters?\s+possible|character\s+set)", "cybersecurity")
def _cyber_ent(m, text):
    import math
    L, N = int(m.group(1)), int(m.group(2))
    return {"password_length": L, "charset_size": N,
            "claimed_entropy_bits": round(L * math.log2(N), 2)}


@_rule("cyber_subnet", r"/(\d+)\s*(?:network|subnet|cidr).*?(\d+)\s*(?:hosts?|addresses?)", "cybersecurity")
def _cyber_subnet(m, text):
    prefix, claimed = int(m.group(1)), int(m.group(2))
    return {"cidr_prefix": prefix, "claimed_host_count": claimed}


@_rule("cyber_port", r"port\s+(\d+)\s+is\s+(well.?known|registered|dynamic|ephemeral)", "cybersecurity")
def _cyber_port(m, text):
    port = int(m.group(1))
    cls = m.group(2).lower().replace("-", "_").replace(" ", "_")
    if "dynamic" in cls or "ephemeral" in cls:
        cls = "dynamic"
    elif "registered" in cls:
        cls = "registered"
    else:
        cls = "well_known"
    return {"port_number": port, "claimed_port_class": cls}


# ── NUTRITION ────────────────────────────────────────────────────────

@_rule("nutr_calories", r"(\d+\.?\d*)\s*g\s+(?:of\s+)?(?:protein|carb|fat).*?calorie", "nutrition")
def _nutr_cal(m, text):
    val = _num(m.group(1))
    t = text.lower()
    if "protein" in t:
        return {"protein_g": val, "claimed_protein_calories": round(val * 4, 1)}
    if "carb" in t:
        return {"carbs_g": val, "claimed_carb_calories": round(val * 4, 1)}
    return {"fat_g": val, "claimed_fat_calories": round(val * 9, 1)}


# ── GOVERNANCE ───────────────────────────────────────────────────────

@_rule("gov_witnesses", r"(\d+)\s+witnesses?.*?(?:decision|proposal|admit|approve)", "governance")
def _gov_wit(m, text):
    count = int(m.group(1))
    return {"witness_count": count, "claimed_quorum_met": count >= 2}


# ── Dispatch function ─────────────────────────────────────────────────

def dispatch(text: str) -> Optional[DispatchResult]:
    """Try every rule in priority order. Return the first match or None.

    None means no rule matched — the caller should fall through to the
    oracle (any AI) and log the result as a training example.
    """
    if not text or not text.strip():
        return None
    for rule_id, pattern, domain, extractor in _RULES:
        m = pattern.search(text)
        if m:
            try:
                spec = extractor(m, text)
                if spec:
                    return DispatchResult(
                        domain=domain,
                        spec=spec,
                        rule_id=rule_id,
                        confidence=1.0,
                        raw_text=text,
                    )
            except Exception:
                continue
    return None


def list_rules() -> List[Dict[str, Any]]:
    """Return all registered rules for introspection / debugging."""
    return [
        {"rule_id": rid, "domain": dom, "pattern": pat.pattern}
        for rid, pat, dom, _ in _RULES
    ]
