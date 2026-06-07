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

# a chemical species: optional coefficient + one-or-more element/paren groups
_CHEM_SPECIES = r'(?:\d+\s+)?(?:[A-Z][a-z]?\d*|\([A-Za-z0-9]+\)\d*)+'
_CHEM_EQ = (r'(' + _CHEM_SPECIES + r'(?:\s*\+\s*' + _CHEM_SPECIES + r')*'
            r'\s*(?:->|→)\s*'
            + _CHEM_SPECIES + r'(?:\s*\+\s*' + _CHEM_SPECIES + r')*)')


@_rule("chem_balance",
       r"(?=.*(?:balanc|equation|reaction))(?=.*(?:->|→))",
       "chemistry")
def _chem_balance(m, text):
    import re as _re
    # capture ONLY the 'LHS -> RHS' species (prose like "Is ... balanced" corrupts
    # the atom count — "Is"/"is" parse as elements -> false MISMATCH).
    eqm = _re.search(_CHEM_EQ, text)
    if not eqm:
        return None
    eq = _re.sub(r'\s+', ' ', eqm.group(1)).strip()
    # require a real formula (element with subscript) or multiple species ('+'),
    # not arbitrary 'A -> B' prose
    if not (_re.search(r'[A-Z][a-z]?\d', eq) or '+' in eq):
        return None
    return {"equation": eq}


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
# (No deterministic rule — by design.) You cannot verify a p-value without the
# underlying data: the statistics verifier RECOMPUTES p from the test statistic
# + df, not from a claimed p alone. A bare "p = X, n = Y" scraped by regex can't
# be checked, so these claims route to the oracle (which can extract the full
# test setup) or are declined. Removed the old dead rule 2026-06-06: its domain
# "statistics" had no verifier, and its {p_value, n} spec didn't fit the
# verifier even if renamed — keeping it would have produced silent false-NAs.


# ── MATHEMATICS ──────────────────────────────────────────────────────

@_rule("math_quadratic", r"(?:solve|roots?\s+of)\s+(\d+\.?\d*)x\^?2\s*([+-]\s*\d+\.?\d*)x\s*([+-]\s*\d+\.?\d*)", "mathematics")
def _math_quad(m, text):
    return {"a": _num(m.group(1)), "b": _num(m.group(2).replace(" ", "")),
            "c": _num(m.group(3).replace(" ", ""))}


@_rule("math_derivative", r"(?:derivative|d/dx)\s*(?:of\s+)?(.+?)\s*(?:=|\bis\b)\s*(.+)", "mathematics")
def _math_deriv(m, text):
    import re as _re
    # verify_mathematics(mode, params) — derivative mode reads params["function"]
    # + params["claimed_derivative"]. Normalize for sympy: '^'->'**' (powers) and
    # insert '*' for implicit multiplication ("2x"->"2*x", "3x^2"->"3*x**2").
    def _norm(s):
        s = s.strip().strip(".;:").replace("^", "**")
        return _re.sub(r'(\d)([a-zA-Z(])', r'\1*\2', s)
    expr, claimed = _norm(m.group(1)), _norm(m.group(2))
    if not expr or not claimed:
        return None
    return {"mode": "derivative",
            "params": {"function": expr, "claimed_derivative": claimed, "variable": "x"}}


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
    import re as _re
    val = _num(m.group(1))  # grams of the macronutrient
    t = text.lower()
    # The CLAIMED calorie figure from the text (not computed — we verify the
    # user's claim, not our own arithmetic). verify_macronutrient_calories reads
    # `calories_claimed` against 4*carb_g + 4*protein_g + 9*fat_g.
    cal_m = _re.search(r'(\d+\.?\d*)\s*(?:kcal|calorie|cal\b)', t)
    spec = {"calories_claimed": _num(cal_m.group(1)) if cal_m else None}
    if "protein" in t:
        spec["protein_g"] = val
    elif "carb" in t:
        spec["carb_g"] = val
    else:
        spec["fat_g"] = val
    return spec


# ── GOVERNANCE ───────────────────────────────────────────────────────
# (No deterministic rule — by design.) The governance verifier checks a FULL
# decision packet (red_items, floor_items, way_path, execution_steps, and a
# witnesses LIST); a witness count scraped from prose isn't enough to build it.
# These claims route to the oracle, which can assemble the structured packet.
# Removed the old dead rule 2026-06-06: domain "governance" had no verifier and
# its {witness_count} spec didn't fit the verifier even if renamed.


# ── ACOUSTICS ────────────────────────────────────────────────────────────────

@_rule("acous_wave_relation",
       r"(\d+\.?\d*)\s*Hz.*?(\d+\.?\d*)\s*m(?:eter)?.*?(\d+\.?\d*)\s*m/s"
       r"|(\d+\.?\d*)\s*m/s.*?(\d+\.?\d*)\s*Hz.*?(\d+\.?\d*)\s*m",
       "acoustics")
def _acous_wave(m, text):
    import re as _re
    spd = _re.search(r'(\d+\.?\d*)\s*m/s', text)
    frq = _re.search(r'(\d+\.?\d*)\s*Hz', text)
    wvl = _re.search(r'wavelength[^=]*=?\s*(\d+\.?\d*)\s*m|(\d+\.?\d*)\s*m(?:eter)?\s+wavelength', text, _re.I)
    if not (spd and frq and wvl):
        return None
    return {"speed_of_wave": _num(spd.group(1)), "frequency_hz": _num(frq.group(1)),
            "wavelength_m": _num(wvl.group(1) or wvl.group(2))}


@_rule("acous_harmonic",
       r"harmonic.*?(\d+\.?\d*)\s*Hz"
       r"|(\d+\.?\d*)\s*Hz.*?harmonic",
       "acoustics")
def _acous_harmonic(m, text):
    import re as _re
    fund = _re.search(r'(\d+\.?\d*)\s*Hz\s+fundamental|fundamental[^=\d]*(\d+\.?\d*)\s*Hz', text, _re.I)
    n_m = _re.search(r'(\d+)(?:st|nd|rd|th)\s+harmonic|harmonic\s+#?(\d+)', text, _re.I)
    claimed = _re.search(r'(?:is|=)\s*(\d+\.?\d*)\s*Hz', text, _re.I)
    if not (fund and n_m and claimed):
        return None
    fund_hz = _num(fund.group(1) or fund.group(2))
    n = int(n_m.group(1) or n_m.group(2))
    return {"fundamental_hz": fund_hz, "harmonic_n": n,
            "claimed_harmonic_hz": _num(claimed.group(1))}


# ── ASTRONOMY ─────────────────────────────────────────────────────────────────

@_rule("astro_kepler",
       r"(?:orbital\s+period|kepler).*?(\d+\.?\d*)\s*(?:years?|yr).*?(\d+\.?\d*)\s*AU"
       r"|(\d+\.?\d*)\s*AU.*?(\d+\.?\d*)\s*(?:years?|yr)",
       "astronomy")
def _astro_kepler(m, text):
    import re as _re, math as _math
    T_m = _re.search(r'(\d+\.?\d*)\s*(?:years?|yr)', text, _re.I)
    a_m = _re.search(r'(\d+\.?\d*)\s*AU', text, _re.I)
    if not (T_m and a_m):
        return None
    T, a = _num(T_m.group(1)), _num(a_m.group(1))
    consistent = abs(T**2 - a**3) / max(a**3, 1e-9) < 0.01
    return {"orbital_period_years": T, "semi_major_axis_au": a, "claimed_kepler_consistent": consistent}


@_rule("astro_parallax",
       r"parallax.*?(\d+\.?\d*)\s*arcsec.*?(\d+\.?\d*)\s*parsec"
       r"|(\d+\.?\d*)\s*arcsec.*?parallax.*?(\d+\.?\d*)\s*(?:pc|parsec)",
       "astronomy")
def _astro_parallax(m, text):
    import re as _re
    par = _re.search(r'(\d+\.?\d*)\s*arcsec', text, _re.I)
    dist = _re.search(r'(\d+\.?\d*)\s*(?:pc|parsec)', text, _re.I)
    if not (par and dist):
        return None
    return {"parallax_arcsec": _num(par.group(1)), "claimed_distance_parsec": _num(dist.group(1))}


# ── CALENDAR / TIME ───────────────────────────────────────────────────────────

@_rule("cal_leap_year",
       r"(\d{4})\s+is\s+(?:a\s+)?(?:not\s+a\s+)?leap\s+year"
       r"|(?:is\s+)?(\d{4})\s+(?:is\s+)?(?:a\s+)?leap\s+year",
       "calendar_time")
def _cal_leap(m, text):
    import re as _re
    yr_m = _re.search(r'(\d{4})', text)
    if not yr_m:
        return None
    yr = int(yr_m.group(1))
    is_leap = (yr % 4 == 0 and yr % 100 != 0) or (yr % 400 == 0)
    claimed = "not" not in text.lower()
    return {"year": yr, "claimed_leap": claimed}


@_rule("cal_day_of_week",
       r"(\d{4}-\d{2}-\d{2})\s+(?:(?:is|was|fell\s+on)\s+(?:a\s+)?)?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
       r"|(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday).*?(\d{4}-\d{2}-\d{2})",
       "calendar_time")
def _cal_dow(m, text):
    import re as _re
    date = _re.search(r'(\d{4}-\d{2}-\d{2})', text)
    day = _re.search(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', text, _re.I)
    if not (date and day):
        return None
    return {"date_iso": date.group(1), "claimed_day_of_week": day.group(1).capitalize()}


# ── COMBINATORICS ─────────────────────────────────────────────────────────────

@_rule("comb_choose",
       r"C\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*(?:=|is|equals)?\s*(\d+)"
       r"|(\d+)\s+choose\s+(\d+)\s*(?:=|is|equals|:)?\s*(\d+)",
       "combinatorics")
def _comb_choose(m, text):
    import re as _re
    # C(n,k) or "n choose k", with =, "is", or "equals" before the count.
    explicit = _re.search(r'C\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*(?:=|is|equals)?\s*(\d+)', text, _re.I)
    nck = _re.search(r'(\d+)\s+choose\s+(\d+)\s*(?:=|is|equals|:)?\s*(\d+)', text, _re.I)
    hit = explicit or nck
    if hit:
        return {"comb_n": int(hit.group(1)), "comb_k": int(hit.group(2)),
                "claimed_combinations": int(hit.group(3))}
    return None


@_rule("comb_permute",
       r"P\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*(?:=|is|equals)\s*(\d+)"
       r"|permutations?\s+of\s+(\d+).*?(\d+).*?(?:=|is|equals)\s*(\d+)",
       "combinatorics")
def _comb_perm(m, text):
    import re as _re
    explicit = _re.search(r'P\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*(?:=|is|equals)?\s*(\d+)', text, _re.I)
    if explicit:
        return {"perm_n": int(explicit.group(1)), "perm_k": int(explicit.group(2)),
                "claimed_permutations": int(explicit.group(3))}
    # natural language: "permutations of 5 items taken 2 at a time is 20"
    nat = _re.search(r'permutations?\s+of\s+(\d+)\s+(?:items?|things?|objects?|elements?)?\s*'
                     r'(?:taken\s+)?(\d+)\s*(?:at\s+a\s+time)?.*?(?:=|is|equals)\s*(\d+)', text, _re.I)
    if nat:
        return {"perm_n": int(nat.group(1)), "perm_k": int(nat.group(2)),
                "claimed_permutations": int(nat.group(3))}
    return None


# ── CRYPTOGRAPHY ──────────────────────────────────────────────────────────────

@_rule("crypto_hash",
       r"(?:sha-?256|sha-?512|sha-?1|md5)\s+(?:hash\s+(?:of\s+)?)?['\"]?(\w+)['\"]?\s+is\s+([a-f0-9]{32,128})"
       r"|([a-f0-9]{32,128})\s+is\s+the\s+(?:sha-?256|sha-?512|sha-?1|md5)\s+hash",
       "cryptography")
def _crypto_hash(m, text):
    import re as _re
    algo_m = _re.search(r'sha-?256|sha-?512|sha-?1|md5', text, _re.I)
    hash_m = _re.search(r'([a-f0-9]{32,128})', text)
    data_m = _re.search(r"(?:hash\s+of\s+)?['\"]([^'\"]+)['\"]", text)
    if not (algo_m and hash_m):
        return None
    algo = algo_m.group(0).lower().replace("-", "")
    # Normalize algorithm name
    algo = {"sha256": "sha256", "sha512": "sha512", "sha1": "sha1", "md5": "md5",
            "sha2": "sha256"}.get(algo, algo)
    data = data_m.group(1) if data_m else "hello"
    return {"hash_algorithm": algo, "data": data, "claimed_hash_hex": hash_m.group(1).lower()}


@_rule("crypto_key_strength",
       r"(?:AES|RSA)-?(\d+)\s+(?:key\s+)?is\s+(strong|weak)",
       "cryptography")
def _crypto_key(m, text):
    import re as _re
    cipher_m = _re.search(r'(AES|RSA)', text, _re.I)
    bits_m = _re.search(r'(AES|RSA)-?(\d+)', text, _re.I)
    strength_m = _re.search(r'\b(strong|weak)\b', text, _re.I)
    if not (bits_m and strength_m):
        return None
    return {"cipher": bits_m.group(1).upper(), "key_bits": int(bits_m.group(2)),
            "claimed_key_strength": strength_m.group(1).lower()}


# ── GENETICS ──────────────────────────────────────────────────────────────────

@_rule("gen_complement",
       r"complement\s+of\s+([ATCGU]{4,})\s+is\s+([ATCGU]{4,})"
       r"|([ATCGU]{4,})\s+(?:DNA\s+)?complement\s+is\s+([ATCGU]{4,})",
       "genetics")
def _gen_comp(m, text):
    import re as _re
    seqs = _re.findall(r'[ATCGU]{4,}', text)
    if len(seqs) < 2:
        return None
    return {"sequence": seqs[0], "claimed_complement": seqs[1]}


# verify_genetics translates on DNA (T, not U) and reports SINGLE-LETTER codes,
# so the extractor must normalize both to match (else a true claim MISMATCHes).
_AA_SINGLE = set("ARNDCQEGHILKMFPSTWYV")
_AA_TO_LETTER = {
    "alanine": "A", "ala": "A",
    "arginine": "R", "arg": "R",
    "asparagine": "N", "asn": "N",
    "aspartate": "D", "aspartic acid": "D", "asp": "D",
    "cysteine": "C", "cys": "C",
    "glutamine": "Q", "gln": "Q",
    "glutamate": "E", "glutamic acid": "E", "glu": "E",
    "glycine": "G", "gly": "G",
    "histidine": "H", "his": "H",
    "isoleucine": "I", "ile": "I",
    "leucine": "L", "leu": "L",
    "lysine": "K", "lys": "K",
    "methionine": "M", "met": "M",
    "phenylalanine": "F", "phe": "F",
    "proline": "P", "pro": "P",
    "serine": "S", "ser": "S",
    "threonine": "T", "thr": "T",
    "tryptophan": "W", "trp": "W",
    "tyrosine": "Y", "tyr": "Y",
    "valine": "V", "val": "V",
    "stop": "*", "ter": "*", "termination": "*",
}


@_rule("gen_codon",
       r"codon\s+([A-Za-z]{3})\s+(?:codes?|translates?)\s+(?:for|to|into)?\s*(\w+)"
       r"|([A-Za-z]{3})\s+codon.*?(?:amino\s+acid\s+is\s+|encodes?\s+)(\w+)",
       "genetics")
def _gen_codon(m, text):
    import re as _re
    codon_m = _re.search(r'\b([ACGTUacgtu]{3})\b', text)
    aa_m = _re.search(r'(?:codes?\s+for|translates?\s+(?:to|into)|encodes?|amino\s+acid\s+is)\s+([A-Za-z][A-Za-z ]*?)\b',
                      text, _re.I)
    if not (codon_m and aa_m):
        return None
    codon = codon_m.group(1).upper().replace("U", "T")
    tok = aa_m.group(1).strip()
    if len(tok) == 1:
        # a bare single letter is only an amino-acid CODE if written upper-case
        aa = tok.upper() if (tok.isupper() and tok.upper() in _AA_SINGLE) else None
    else:
        aa = _AA_TO_LETTER.get(tok.lower())
    if aa is None:
        return None  # not a recognized amino acid -> let the oracle handle it
    return {"codon": codon, "claimed_amino_acid": aa}


# ── GEOGRAPHY ─────────────────────────────────────────────────────────────────

@_rule("geo_haversine",
       r"(?=.*(?:km|kilomet))(?=.*-?\d+\.\d+\s*,\s*-?\d+\.\d+)"
       r"|(?:distance|kilometer).*?lat.*?lon.*?lat.*?lon"
       r"|(\d+\.?\d*)\s*[NS].*?(\d+\.?\d*)\s*[EW].*?(\d+\.?\d*)\s*[NS].*?(\d+\.?\d*)\s*[EW]",
       "geography")
def _geo_haversine(m, text):
    import re as _re
    dist_m = _re.search(r'(\d+\.?\d*)\s*(?:km|kilomet(?:er|re)s?)\b', text, _re.I)
    if not dist_m:
        return None
    # prefer explicit "lat, lon" decimal pairs (order-independent, ignores the distance number)
    pairs = _re.findall(r'(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)', text)
    if len(pairs) >= 2:
        (la1, lo1), (la2, lo2) = pairs[0], pairs[1]
        return {"lat1": float(la1), "lon1": float(lo1),
                "lat2": float(la2), "lon2": float(lo2),
                "claimed_distance_km": _num(dist_m.group(1))}
    # fall back to hemisphere-tagged coords (require the N/S/E/W letter, not optional)
    coords = _re.findall(r'(-?\d+\.?\d*)\s*[NSEWnsew]', text)
    if len(coords) >= 4:
        return {"lat1": float(coords[0]), "lon1": float(coords[1]),
                "lat2": float(coords[2]), "lon2": float(coords[3]),
                "claimed_distance_km": _num(dist_m.group(1))}
    return None


# ── GEOLOGY ───────────────────────────────────────────────────────────────────

@_rule("geo_mohs",
       r"(\w+)\s+(?:can\s+)?scratches?\s+(\w+)|mohs\s+hardness.*?(\d+\.?\d*).*?(\d+\.?\d*)",
       "geology")
def _geo_mohs(m, text):
    import re as _re
    mohs_vals = {"talc": 1, "gypsum": 2, "calcite": 3, "fluorite": 4,
                 "apatite": 5, "orthoclase": 6, "quartz": 7, "topaz": 8,
                 "corundum": 9, "diamond": 10}
    s_m = _re.search(r'(\w+)\s+(?:can\s+)?scratches?\s+(\w+)', text, _re.I)
    if s_m:
        a, b = s_m.group(1).lower(), s_m.group(2).lower()
        ha = mohs_vals.get(a)
        hb = mohs_vals.get(b)
        if ha and hb:
            return {"harder_mineral_mohs": max(ha, hb), "softer_mineral_mohs": min(ha, hb),
                    "claimed_can_scratch": ha > hb}
    return None


@_rule("geo_richter",
       r"magnitude\s+(\d+\.?\d*)\s+is\s+(\d+)\s*times?\s+(?:stronger|larger|amplitude)",
       "geology")
def _geo_richter(m, text):
    import re as _re
    mags = _re.findall(r'magnitude\s+(\d+\.?\d*)', text, _re.I)
    ratio_m = _re.search(r'(\d+\.?\d*)\s*times?\s+(?:stronger|larger|amplitude)', text, _re.I)
    if len(mags) >= 2 and ratio_m:
        return {"richter_M1": _num(mags[0]), "richter_M2": _num(mags[1]),
                "claimed_amplitude_ratio": _num(ratio_m.group(1))}
    return None


# ── GEOMETRY ──────────────────────────────────────────────────────────────────

@_rule("geom_pythagorean",
       r"(\d+\.?\d*)\^?2\s*\+\s*(\d+\.?\d*)\^?2\s*=\s*(\d+\.?\d*)\^?2"
       r"|(?:right\s+triangle|pythagorean).*?sides?.*?(\d+\.?\d*).*?(\d+\.?\d*).*?(\d+\.?\d*)",
       "geometry")
def _geom_pyth(m, text):
    import re as _re
    triple = _re.search(r'(\d+\.?\d*)\^?2\s*\+\s*(\d+\.?\d*)\^?2\s*=\s*(\d+\.?\d*)\^?2', text)
    if triple:
        a, b, c = _num(triple.group(1)), _num(triple.group(2)), _num(triple.group(3))
        return {"pyth_a": a, "pyth_b": b, "pyth_c": c,
                "claimed_right_triangle": abs(a**2 + b**2 - c**2) < 0.01 * c**2}
    sides = _re.findall(r'(\d+\.?\d*)', text)
    if len(sides) >= 3:
        a, b, c = sorted([_num(s) for s in sides[:3]])
        return {"pyth_a": a, "pyth_b": b, "pyth_c": c,
                "claimed_right_triangle": abs(a**2 + b**2 - c**2) < 0.01 * c**2}
    return None


@_rule("geom_polygon_angles",
       r"(\d+)-(?:sided|gon)|(?:polygon|interior\s+angles?)\s+(?:with\s+)?(\d+)\s+sides?",
       "geometry")
def _geom_poly(m, text):
    import re as _re
    n_m = _re.search(r'(\d+)[-\s]?(?:sided|gon|sides?)', text, _re.I)
    angle_m = _re.search(r'(\d+\.?\d*)\s*(?:deg|°|degree)', text, _re.I)
    # Require a REAL claimed angle. Without one there is nothing to verify, and
    # defaulting to the computed value self-confirms (and collides with non-
    # geometry "N-sided" phrasings like "6-sided die").
    if not (n_m and angle_m):
        return None
    n = int(n_m.group(1))
    return {"polygon_n": n, "claimed_interior_angle_sum_deg": _num(angle_m.group(1))}


@_rule("geom_circle_area",
       r"circle.*?radius\s*=?\s*(\d+\.?\d*).*?area.*?=?\s*(\d+\.?\d*)"
       r"|area.*?circle.*?radius\s*=?\s*(\d+\.?\d*).*?(\d+\.?\d*)",
       "geometry")
def _geom_circle(m, text):
    import re as _re, math as _math
    r_m = _re.search(r'radius\s*(?:of|=|is)?\s*(\d+\.?\d*)', text, _re.I)
    a_m = _re.search(r'area\s*(?:is|=|of)?\s*(\d+\.?\d*)', text, _re.I)
    if not r_m:
        return None
    r = _num(r_m.group(1))
    claimed = _num(a_m.group(1)) if a_m else round(_math.pi * r**2, 4)
    return {"circle_radius": r, "claimed_circle_area": claimed}


# ── INFORMATION THEORY ────────────────────────────────────────────────────────

@_rule("info_entropy",
       r"(?=.*entropy)(?=.*\bbits?\b)",
       "information_theory")
def _info_entropy(m, text):
    import re as _re, math as _math
    probs = _re.findall(r'0\.\d+', text)
    claimed_m = _re.search(r'(\d+\.?\d*)\s*bits?', text, _re.I)
    if not (probs and claimed_m):
        return None
    prob_floats = [float(p) for p in probs]
    return {"probabilities": prob_floats, "claimed_entropy_bits": _num(claimed_m.group(1))}


@_rule("info_hamming",
       r"hamming\s+distance.*?([01]{4,}|[A-Za-z]{4,}).*?([01]{4,}|[A-Za-z]{4,}).*?=\s*(\d+)"
       r"|distance\s+between\s+['\"]?([01]+)['\"]?.*?['\"]?([01]+)['\"]?\s*(?:is|=)\s*(\d+)",
       "information_theory")
def _info_hamming(m, text):
    import re as _re
    seqs = _re.findall(r"[01]{4,}", text)
    claimed_m = _re.search(r"(?:is|=|distance\s+of)\s*(\d+)", text)
    if len(seqs) >= 2 and claimed_m:
        return {"string_a": seqs[0], "string_b": seqs[1],
                "claimed_hamming": int(claimed_m.group(1))}
    return None


# ── METEOROLOGY ───────────────────────────────────────────────────────────────

@_rule("met_dew_point",
       r"(?=.*dew\s*point)(?=.*humidity)(?=.*\d\s*%)(?=.*\d\s*°?\s*C)",
       "meteorology")
def _met_dew(m, text):
    import re as _re
    dp_m = _re.search(r'dew\s*point[^\d-]*(-?\d+\.?\d*)\s*°?\s*C', text, _re.I)
    rh_m = _re.search(r'(\d+\.?\d*)\s*%', text)
    if not (dp_m and rh_m):
        return None
    dp = _num(dp_m.group(1))
    # Air temperature: an explicit "temperature N C", else the first "N C"
    # appearing before "dew point" (handles "at 25 C and 60% RH, dew point 16.7 C").
    tm = _re.search(r'(?:temperature|temp|air)[^\d-]*(-?\d+\.?\d*)\s*°?\s*C', text, _re.I)
    temp = _num(tm.group(1)) if tm else None
    if temp is None:
        for cm in _re.finditer(r'(-?\d+\.?\d*)\s*°?\s*C\b', text, _re.I):
            if cm.start() < dp_m.start():
                temp = _num(cm.group(1)); break
    if temp is None:
        return None
    return {"temperature_c": temp, "relative_humidity_pct": _num(rh_m.group(1)),
            "claimed_dew_point_c": dp}


@_rule("met_wind_chill",
       r"wind\s+chill.*?(\d+\.?\d*)\s*[°]?F.*?(\d+\.?\d*)\s*mph.*?(\d+\.?\d*)"
       r"|(\d+\.?\d*)\s*[°]?F.*?(\d+\.?\d*)\s*mph.*?wind\s+chill.*?(\d+\.?\d*)",
       "meteorology")
def _met_wc(m, text):
    import re as _re
    temp_m = _re.search(r'(-?\d+\.?\d*)\s*[°]?F', text, _re.I)
    wind_m = _re.search(r'(\d+\.?\d*)\s*mph', text, _re.I)
    wc_m = _re.search(r'wind\s+chill[^\d-]*(-?\d+\.?\d*)', text, _re.I)
    if not (temp_m and wind_m and wc_m):
        return None
    return {"temperature_f_for_wc": _num(temp_m.group(1)), "wind_speed_mph": _num(wind_m.group(1)),
            "claimed_wind_chill_f": _num(wc_m.group(1))}


# ── MUSIC THEORY ──────────────────────────────────────────────────────────────

@_rule("mus_midi_freq",
       r"MIDI\s+note\s+(\d+).*?(\d+\.?\d*)\s*Hz|(\d+\.?\d*)\s*Hz.*?MIDI\s+note\s+(\d+)",
       "music_theory")
def _mus_midi(m, text):
    import re as _re
    midi_m = _re.search(r'MIDI\s+note\s+(\d+)', text, _re.I)
    freq_m = _re.search(r'(\d+\.?\d*)\s*Hz', text, _re.I)
    if not (midi_m and freq_m):
        return None
    return {"midi_note": int(midi_m.group(1)), "claimed_frequency_hz": _num(freq_m.group(1))}


@_rule("mus_interval_semitones",
       r"(?:major\s+third|minor\s+third|perfect\s+fifth|major\s+sixth|octave|tritone).*?(\d+)\s*semitone"
       r"|(\d+)\s+semitones?\s+(?:is|=|for)\s+(?:a\s+)?(\w+\s+\w+)"
       r"|([A-G][#b]?\d)\s*(?:to|->|-)\s*([A-G][#b]?\d).*?(\d+)\s*semitone",
       "music_theory")
def _mus_interval(m, text):
    import re as _re
    # Note-pair form ("C4 to G4 is 7 semitones") -> note_a/note_b, which
    # verify_music_theory actually reads. This also keeps such claims from
    # falling through to ling_strongs (G4 is a Strong's number too).
    note_m = _re.search(r"\b([A-G][#b]?\d)\s*(?:to|->|-)\s*([A-G][#b]?\d)\b", text)
    semis_m = _re.search(r'(\d+)\s*semitone', text, _re.I)
    if note_m and semis_m:
        return {"note_a": note_m.group(1), "note_b": note_m.group(2),
                "claimed_semitones": int(semis_m.group(1))}
    INTERVALS = {"major second": 2, "minor third": 3, "major third": 4,
                 "perfect fourth": 5, "tritone": 6, "perfect fifth": 7,
                 "major sixth": 9, "minor seventh": 10, "major seventh": 11, "octave": 12}
    for name, semis in INTERVALS.items():
        if name in text.lower():
            claimed_m = _re.search(r'(\d+)\s*semitone', text, _re.I)
            if claimed_m:
                return {"claimed_interval": name, "claimed_semitones": int(claimed_m.group(1))}
    return None


# ── NETWORKING ────────────────────────────────────────────────────────────────

@_rule("net_ip_valid",
       r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+is\s+(?:a\s+)?(?:valid|invalid)\s+IP",
       "networking")
def _net_ip(m, text):
    import re as _re
    ip_m = _re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
    valid = "invalid" not in text.lower()
    if not ip_m:
        return None
    return {"address": ip_m.group(1), "claimed_format_valid": valid}


@_rule("net_subnet_hosts",
       r"/(\d+)\s+(?:subnet|network|CIDR).*?(\d+)\s+usable\s+hosts?"
       r"|(\d+)\s+usable\s+hosts?.*?/(\d+)",
       "networking")
def _net_subnet(m, text):
    import re as _re
    prefix_m = _re.search(r'/(\d+)', text)
    hosts_m = _re.search(r'(\d+)\s+usable\s+hosts?', text, _re.I)
    if not (prefix_m and hosts_m):
        return None
    return {"subnet_prefix": int(prefix_m.group(1)), "claimed_usable_hosts": int(hosts_m.group(1))}


@_rule("net_cidr_member",
       r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+).*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?"
       r"(?:is|not)\s+in\s+(?:the\s+)?(?:subnet|range|network)",
       "networking")
def _net_cidr(m, text):
    import re as _re
    cidr_m = _re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+)', text)
    ips = _re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})(?!/)', text)
    if not (cidr_m and len(ips) >= 1):
        return None
    ip = ips[-1] if len(ips) >= 2 else ips[0]
    in_range = "not in" not in text.lower()
    return {"cidr": cidr_m.group(1), "ip_to_check": ip, "claimed_in_subnet": in_range}


# ── NUMBER THEORY ─────────────────────────────────────────────────────────────

@_rule("num_prime",
       r"\bis\s+(\d+)\s+(?:a\s+)?(?:not\s+(?:a\s+)?)?prime"
       r"|\b(\d+)\s+is\s+(?:a\s+)?(?:not\s+(?:a\s+)?)?prime",
       "number_theory")
def _num_prime(m, text):
    import re as _re
    low = text.lower()
    # "is 17 (a) prime" OR "17 is (a/not) prime" — both natural phrasings.
    n_m = (_re.search(r'\bis\s+(\d+)\s+(?:a\s+)?(?:not\s+(?:a\s+)?)?prime', low)
           or _re.search(r'\b(\d+)\s+is\s+(?:a\s+)?(?:not\s+(?:a\s+)?)?prime', low))
    if not n_m:
        return None
    return {"n_prime": int(n_m.group(1)), "claimed_prime": "not" not in low}


@_rule("num_gcd",
       r"gcd\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*=\s*(\d+)"
       r"|(?:greatest\s+common\s+(?:divisor|factor)).*?(\d+).*?(\d+).*?=\s*(\d+)",
       "number_theory")
def _num_gcd(m, text):
    import re as _re
    explicit = _re.search(r'gcd\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*=?\s*(\d+)', text, _re.I)
    # "gcd of 12 and 18 is 6" or "greatest common divisor of 12 and 18 is 6"
    natural = _re.search(r'(?:gcd|divisor|factor)\s+of\s+(\d+)\s+and\s+(\d+)\s+is\s+(\d+)', text, _re.I)
    # "12 and 18 ... gcd ... 6" (rare)
    alt = _re.search(r'(\d+)\s+and\s+(\d+).*?(?:gcd|divisor).*?(?:is|=)\s*(\d+)', text, _re.I)
    for pat in (explicit, natural, alt):
        if pat:
            return {"gcd_a": int(pat.group(1)), "gcd_b": int(pat.group(2)),
                    "claimed_gcd": int(pat.group(3))}
    return None


@_rule("num_factorial",
       r"(\d+)!\s*=\s*(\d[\d,]*)"
       r"|factorial\s+of\s+(\d+)\s+is\s+(\d[\d,]*)",
       "number_theory")
def _num_fact(m, text):
    import re as _re
    explicit = _re.search(r'(\d+)!\s*=?\s*([\d,]+)', text)
    natural = _re.search(r'factorial\s+of\s+(\d+)\s+(?:is|=)\s*([\d,]+)', text, _re.I)
    match = explicit or natural
    if not match:
        return None
    return {"factorial_n": int(match.group(1)), "claimed_factorial": int(match.group(2).replace(",", ""))}


# ── OPTICS ────────────────────────────────────────────────────────────────────

@_rule("opt_snell",
       r"n1?\s*=\s*(\d+\.?\d*).*?(?:theta|angle).*?(\d+\.?\d*)\s*deg.*?n2?\s*=\s*(\d+\.?\d*).*?(\d+\.?\d*)\s*deg"
       r"|snell.*?(\d+\.?\d*).*?(\d+\.?\d*)\s*deg.*?(\d+\.?\d*).*?(\d+\.?\d*)\s*deg",
       "optics")
def _opt_snell(m, text):
    import re as _re
    n_vals = _re.findall(r'n[12]?\s*=\s*(\d+\.?\d*)', text, _re.I)
    angles = _re.findall(r'(\d+\.?\d*)\s*deg', text, _re.I)
    if len(n_vals) >= 2 and len(angles) >= 2:
        return {"n1": _num(n_vals[0]), "theta1_deg": _num(angles[0]),
                "n2": _num(n_vals[1]), "claimed_theta2_deg": _num(angles[1])}
    return None


@_rule("opt_thin_lens",
       r"focal\s+length.*?(\d+\.?\d*)\s*(?:cm|m).*?object.*?(\d+\.?\d*)\s*(?:cm|m).*?image.*?(\d+\.?\d*)",
       "optics")
def _opt_thin_lens(m, text):
    import re as _re
    f_m = _re.search(r'focal\s+length\s*(?:is|=|of)?\s*(\d+\.?\d*)\s*(cm|m)', text, _re.I)
    obj_m = _re.search(r'object\s+(?:distance\s*)?(?:is|=|of|at)?\s*(\d+\.?\d*)\s*(cm|m)', text, _re.I)
    img_m = _re.search(r'image\s+(?:distance\s*)?(?:is|=|of|at)?\s*(\d+\.?\d*)\s*(cm|m)', text, _re.I)
    if not (f_m and obj_m and img_m):
        return None
    scale = 0.01  # cm to m
    unit = f_m.group(2).lower()
    s = scale if unit == "cm" else 1.0
    f = _num(f_m.group(1)) * s
    obj = _num(obj_m.group(1)) * s
    img = _num(img_m.group(1)) * s
    # Verify 1/f = 1/obj + 1/img
    consistent = abs(1/f - (1/obj + 1/img)) < 0.01 * (1/f)
    return {"focal_length_m": f, "object_distance_m": obj, "image_distance_m": img,
            "claimed_thin_lens_consistent": consistent}


# ── ELECTRICAL ────────────────────────────────────────────────────────────────

@_rule("elec_ohms_law",
       r"(?=.*(?:volt|\d\s*V))(?=.*(?:amp|\d\s*A))(?=.*(?:ohm|Ω|omega))",
       "electrical")
def _elec_ohm(m, text):
    import re as _re
    # Order-independent: the verifier (verify_ohms_law) reads voltage_V/current_A/
    # resistance_ohm and checks V = I*R. The trigger requires all three units.
    v_m = _re.search(r'(\d+\.?\d*)\s*V(?:olt)?s?\b', text, _re.I)
    i_m = _re.search(r'(\d+\.?\d*)\s*(?:A|amp)(?:ere)?s?\b', text, _re.I)
    r_m = _re.search(r'(\d+\.?\d*)\s*(?:ohm|Ω|omega)', text, _re.I)
    if not (v_m and i_m and r_m):
        return None
    return {"voltage_V": _num(v_m.group(1)), "current_A": _num(i_m.group(1)),
            "resistance_ohm": _num(r_m.group(1))}


@_rule("elec_power",
       r"(\d+\.?\d*)\s*W(?:att)?s?.*?(\d+\.?\d*)\s*V.*?(\d+\.?\d*)\s*(?:A|amp)"
       r"|(\d+\.?\d*)\s*V.*?(\d+\.?\d*)\s*(?:A|amp).*?(\d+\.?\d*)\s*W",
       "electrical")
def _elec_power(m, text):
    import re as _re
    v_m = _re.search(r'(\d+\.?\d*)\s*V(?:olt)?', text, _re.I)
    i_m = _re.search(r'(\d+\.?\d*)\s*(?:A|amp)', text, _re.I)
    p_m = _re.search(r'(\d+\.?\d*)\s*W(?:att)?', text, _re.I)
    if not (v_m and i_m and p_m):
        return None
    return {"voltage_V": _num(v_m.group(1)), "current_A": _num(i_m.group(1)),
            "power_W_claim": _num(p_m.group(1))}


# ── FINANCE ───────────────────────────────────────────────────────────────────

@_rule("fin_compound",
       r"(?:compound|interest|invest|principal|deposit|grows?\s+to).*?\d.*?%.*?(?:year|yr)",
       "finance")
def _fin_compound(m, text):
    import re as _re
    P_m = _re.search(r'\$?(\d[\d,]*\.?\d*)\s*(?:principal|at|invested|deposit)', text, _re.I)
    r_m = _re.search(r'(\d+\.?\d*)\s*%\s*(?:per\s+year|annually|p\.?a\.?)?', text, _re.I)
    t_m = _re.search(r'(\d+\.?\d*)\s*(?:year|yr)', text, _re.I)
    fv_m = _re.search(r'(?:amount|total|value|grows?\s+to)\s*\$?(\d[\d,]*\.?\d*)', text, _re.I)
    if not (P_m and r_m and t_m and fv_m):
        return None
    n_m = _re.search(r'(?:monthly|quarterly|semi.?annually|daily)', text, _re.I)
    n = {"monthly": 12, "quarterly": 4, "semi-annually": 2, "semiannually": 2, "daily": 365}.get(
        (n_m.group(0).lower().replace("-", "") if n_m else ""), 1)
    return {"principal": _num(P_m.group(1)), "rate": _num(r_m.group(1)) / 100,
            "years": _num(t_m.group(1)), "claimed_future_value": _num(fv_m.group(1)),
            "compounding_per_year": n}


@_rule("fin_accounting_identity",
       r"assets?\s*=\s*liabilities?\s*\+\s*equity|A\s*=\s*L\s*\+\s*E",
       "finance")
def _fin_identity(m, text):
    import re as _re
    vals = _re.findall(r'\$?(\d[\d,]*\.?\d*)', text)
    if len(vals) >= 3:
        a, l, e = _num(vals[0]), _num(vals[1]), _num(vals[2])
        return {"assets": a, "liabilities": l, "equity": e}
    return None


# ── ENERGY ────────────────────────────────────────────────────────────────────

@_rule("energy_kwh_wh",
       r"(\d+\.?\d*)\s*kWh\s*=\s*(\d[\d,]*\.?\d*)\s*Wh"
       r"|(\d[\d,]*\.?\d*)\s*Wh\s*=\s*(\d+\.?\d*)\s*kWh",
       "energy")
def _energy_kwh(m, text):
    import re as _re
    kwh_m = _re.search(r'(\d+\.?\d*)\s*kWh', text, _re.I)
    wh_m = _re.search(r'(\d[\d,]*\.?\d*)\s*Wh\b', text, _re.I)
    if not (kwh_m and wh_m):
        return None
    return {"kwh": _num(kwh_m.group(1)), "claimed_wh": _num(wh_m.group(1))}


@_rule("energy_solar_yield",
       r"(\d+\.?\d*)\s*W(?:att)?\s+panel.*?(\d+\.?\d*)\s*(?:PSH|peak\s+sun).*?(\d+\.?\d*)\s*kWh/day"
       r"|solar.*?(\d+\.?\d*)\s*W.*?(\d+\.?\d*)\s*hours?.*?(\d+\.?\d*)\s*kWh",
       "energy")
def _energy_solar(m, text):
    import re as _re
    panel_m = _re.search(r'(\d+\.?\d*)\s*W(?:att)?(?:\s+panel)?', text, _re.I)
    psh_m = _re.search(r'(\d+\.?\d*)\s*(?:PSH|peak\s+sun\s+hours?)', text, _re.I)
    eff_m = _re.search(r'(\d+\.?\d*)\s*%\s*(?:efficiency|eff)', text, _re.I)
    kwh_m = _re.search(r'(\d+\.?\d*)\s*kWh/day', text, _re.I)
    if not (panel_m and psh_m and kwh_m):
        return None
    eff = _num(eff_m.group(1)) / 100 if eff_m else 0.85
    return {"panel_W": _num(panel_m.group(1)), "peak_sun_hours": _num(psh_m.group(1)),
            "system_efficiency": eff, "claimed_daily_kwh": _num(kwh_m.group(1))}


# ── SPORTS ANALYTICS ─────────────────────────────────────────────────────────

@_rule("sport_pythagorean",
       r"(\d+)\s+runs?\s+scored.*?(\d+)\s+runs?\s+allowed.*?(\d+\.?\d*)\s*%?\s*win"
       r"|pythagorean.*?(\d+)\s+RS.*?(\d+)\s+RA.*?(\d+\.?\d*)",
       "sports_analytics")
def _sport_pyth(m, text):
    import re as _re
    rs_m = _re.search(r'(\d+)\s+runs?\s+scored', text, _re.I)
    ra_m = _re.search(r'(\d+)\s+runs?\s+allowed', text, _re.I)
    wp_m = _re.search(r'(\d+\.?\d*)\s*%?\s*win(?:ning)?\s+pct|win\s+pct.*?(\d+\.?\d*)', text, _re.I)
    if not (rs_m and ra_m and wp_m):
        return None
    rs, ra = int(rs_m.group(1)), int(ra_m.group(1))
    claimed = _num(wp_m.group(1) or wp_m.group(2))
    claimed = claimed / 100 if claimed > 1 else claimed
    return {"runs_scored": rs, "runs_allowed": ra, "claimed_winning_pct": claimed}


@_rule("sport_elo",
       r"Elo.*?(\d+).*?(\d+).*?expected.*?(\d+\.?\d*)"
       r"|expected\s+score.*?Elo\s+(\d+).*?(\d+).*?(\d+\.?\d*)",
       "sports_analytics")
def _sport_elo(m, text):
    import re as _re
    elos = _re.findall(r'\b(\d{3,4})\b', text)
    expected_m = _re.search(r'expected.*?(?:score|prob).*?(\d+\.?\d*)', text, _re.I)
    if len(elos) >= 2 and expected_m:
        return {"elo_a": int(elos[0]), "elo_b": int(elos[1]),
                "claimed_expected_score_a": _num(expected_m.group(1))}
    return None


# ── QUANTUM COMPUTING ─────────────────────────────────────────────────────────

@_rule("qc_normalize",
       r"amplitudes?\s*(?:are\s+)?\[([0-9.,\s]+)\].*?(?:normalized|norm\s*=\s*1)"
       r"|qubit.*?\[([0-9.,\s]+)\].*?normalized",
       "quantum_computing")
def _qc_norm(m, text):
    import re as _re
    amp_m = _re.search(r'\[([0-9.,\s]+)\]', text)
    if not amp_m:
        return None
    amps = [float(x.strip()) for x in amp_m.group(1).split(",") if x.strip()]
    if not amps:
        return None
    norm_sum = sum(a**2 for a in amps)
    claimed = abs(norm_sum - 1.0) < 0.01
    return {"amplitudes": amps, "claimed_normalized": claimed}


@_rule("qc_grover",
       r"(\d+)\s+items?.*?(\d+)\s+grover\s+iterations?"
       r"|grover.*?(\d+)\s+items?.*?(\d+)\s+iterations?",
       "quantum_computing")
def _qc_grover(m, text):
    import re as _re
    items_m = _re.search(r'(\d+)\s+items?', text, _re.I)
    iter_m = _re.search(r'(\d+)\s+(?:grover\s+)?iterations?', text, _re.I)
    if not (items_m and iter_m):
        return None
    return {"n_items": int(items_m.group(1)), "claimed_grover_iterations": int(iter_m.group(1))}


# ── NUTRITION ─────────────────────────────────────────────────────────────────

@_rule("nutr_macros",
       r"(\d+\.?\d*)\s*g\s+protein.*?(\d+\.?\d*)\s*g\s+(?:carb|carbohydrate).*?(\d+\.?\d*)\s*g\s+fat.*?(\d+\.?\d*)\s*(?:kcal|calories?)"
       r"|(\d+\.?\d*)\s*g\s+carb.*?(\d+\.?\d*)\s*g\s+protein.*?(\d+\.?\d*)\s*g\s+fat.*?(\d+\.?\d*)\s*(?:kcal|calories?)",
       "nutrition")
def _nutr_macros(m, text):
    import re as _re
    prot_m = _re.search(r'(\d+\.?\d*)\s*g\s+protein', text, _re.I)
    carb_m = _re.search(r'(\d+\.?\d*)\s*g\s+(?:carb|carbohydrate)', text, _re.I)
    fat_m = _re.search(r'(\d+\.?\d*)\s*g\s+fat', text, _re.I)
    cal_m = _re.search(r'(\d+\.?\d*)\s*(?:kcal|calories?)', text, _re.I)
    if not (prot_m and carb_m and fat_m and cal_m):
        return None
    return {"protein_g": _num(prot_m.group(1)), "carb_g": _num(carb_m.group(1)),
            "fat_g": _num(fat_m.group(1)), "calories_claimed": _num(cal_m.group(1))}


# ── EXERCISE SCIENCE ──────────────────────────────────────────────────────────

@_rule("ex_met_calories",
       r"MET\s*(?:value\s*)?(?:of\s*)?(\d+\.?\d*).*?(\d+\.?\d*)\s*kg.*?(\d+\.?\d*)\s*hours?.*?(\d+\.?\d*)\s*(?:kcal|cal)"
       r"|(\d+\.?\d*)\s*(?:kcal|cal).*?MET\s*=?\s*(\d+\.?\d*).*?(\d+\.?\d*)\s*kg.*?(\d+\.?\d*)\s*hours?",
       "exercise_science")
def _ex_met(m, text):
    import re as _re
    met_m = _re.search(r'MET\s*(?:value\s*)?(?:of\s*|=\s*)?(\d+\.?\d*)', text, _re.I)
    wt_m = _re.search(r'(\d+\.?\d*)\s*kg', text, _re.I)
    dur_m = _re.search(r'(\d+\.?\d*)\s*hours?', text, _re.I)
    kcal_m = _re.search(r'(\d+\.?\d*)\s*(?:kcal|calories?)', text, _re.I)
    if not (met_m and wt_m and dur_m and kcal_m):
        return None
    return {"claimed_met": _num(met_m.group(1)), "weight_kg": _num(wt_m.group(1)),
            "duration_hours": _num(dur_m.group(1)), "claimed_kcal": _num(kcal_m.group(1))}


@_rule("ex_max_hr",
       r"max(?:imum)?\s+heart\s+rate.*?(\d+)\s*(?:year|age|yr).*?(\d+)\s*bpm"
       r"|(\d+)\s*bpm.*?max(?:imum)?\s+heart\s+rate.*?(\d+)\s*(?:year|age|yr)",
       "exercise_science")
def _ex_max_hr(m, text):
    import re as _re
    age_m = _re.search(r'(\d+)\s*(?:year|age|yr)s?', text, _re.I)
    hr_m = _re.search(r'(\d+)\s*bpm', text, _re.I)
    if not (age_m and hr_m):
        return None
    return {"age_years": int(age_m.group(1)), "claimed_max_hr": int(hr_m.group(1))}


# ── PHOTOGRAPHY ───────────────────────────────────────────────────────────────

@_rule("photo_ev",
       r"f/?(\d+\.?\d*).*?(\d+/?\.?\d*)\s*s(?:ec)?.*?ISO\s*(\d+).*?EV\s*=?\s*(\d+\.?\d*)"
       r"|EV\s*=?\s*(\d+\.?\d*).*?f/?(\d+\.?\d*).*?(\d+/?\.?\d*)\s*s.*?ISO\s*(\d+)",
       "photography")
def _photo_ev(m, text):
    import re as _re, math as _math
    f_m = _re.search(r'f/?(\d+\.?\d*)', text, _re.I)
    t_m = _re.search(r'1/(\d+)\s*s|(\d+\.?\d*)\s*s(?:ec)?', text, _re.I)
    iso_m = _re.search(r'ISO\s*(\d+)', text, _re.I)
    ev_m = _re.search(r'EV\s*=?\s*(\d+\.?\d*)', text, _re.I)
    if not (f_m and t_m and iso_m and ev_m):
        return None
    f_num = _num(f_m.group(1))
    shutter = 1.0 / _num(t_m.group(1)) if t_m.group(1) else _num(t_m.group(2))
    return {"f_number": f_num, "shutter_seconds": shutter, "iso": int(iso_m.group(1)),
            "claimed_exposure_value": _num(ev_m.group(1))}


# ── MANUFACTURING ─────────────────────────────────────────────────────────────

@_rule("mfg_cpk",
       r"(?=.*\bUSL\b)(?=.*\bLSL\b)(?=.*\bmean\b)(?=.*\bsigma\b)(?=.*capable)",
       "manufacturing")
def _mfg_cpk(m, text):
    import re as _re
    usl_m = _re.search(r'USL\s*=?\s*(\d+\.?\d*)', text, _re.I)
    lsl_m = _re.search(r'LSL\s*=?\s*(\d+\.?\d*)', text, _re.I)
    mean_m = _re.search(r'mean\s*=?\s*(\d+\.?\d*)', text, _re.I)
    sigma_m = _re.search(r'sigma\s*=?\s*(\d+\.?\d*)', text, _re.I)
    if not (usl_m and lsl_m and mean_m and sigma_m):
        return None
    capable = "capable" in text.lower() and "not capable" not in text.lower()
    return {"usl": _num(usl_m.group(1)), "lsl": _num(lsl_m.group(1)),
            "process_mean": _num(mean_m.group(1)), "process_sigma": _num(sigma_m.group(1)),
            "claimed_cp_capable": capable}


# ── AGRICULTURE ───────────────────────────────────────────────────────────────

@_rule("agri_hardiness_zone",
       r"(?=.*hardiness\s+zone)(?=.*zone\s+\d)"
       r"|(\w+)\s+(?:grows?|thrives?|hardy|suitable|cultivat\w+)(?:\s+\w+){0,2}?\s+in\s+(?:hardiness\s+)?zone\s+(\d+[ab]?)",
       "agriculture")
def _agri_zone(m, text):
    import re as _re
    zone_m = _re.search(r'zone\s+(\d+[ab]?)', text, _re.I)
    # crops the verifier's hardiness reference table actually knows ("maize" -> "corn")
    crops = ["tomato", "wheat", "corn", "maize", "apple", "peach",
             "strawberry", "blueberry", "soybean", "cotton"]
    crop = next((c for c in crops if c in text.lower()), None)
    if not (zone_m and crop):
        return None
    if crop == "maize":
        crop = "corn"
    return {"claimed_zone": zone_m.group(1), "crop": crop}


# ── FORMAL LOGIC ──────────────────────────────────────────────────────────────

@_rule("logic_tautology",
       r"([A-Z](?:\s*(?:>>|&|\|)\s*[~]?[A-Z])+)\s+is\s+(?:a\s+)?tautology"
       r"|\(([A-Z](?:\s*(?:>>|&|\|)\s*[~]?[A-Z])+)\)\s+is\s+(?:a\s+)?tautology",
       "formal_logic")
def _logic_taut(m, text):
    formula = (m.group(1) or m.group(2)).strip()
    return {"formula": formula, "claimed_tautology": True}


@_rule("logic_satisfiable",
       r"([A-Z](?:\s*(?:>>|&|\|)\s*[~]?[A-Z])+)\s+is\s+(?:not\s+)?satisfiable",
       "formal_logic")
def _logic_sat(m, text):
    formula = m.group(1).strip()
    claimed = "not satisfiable" not in text.lower()
    return {"formula": formula, "claimed_satisfiable": claimed}


# ── HYDROLOGY ─────────────────────────────────────────────────────────────────

@_rule("hyd_manning",
       r"manning.*?n\s*=\s*(\d+\.?\d*).*?radius\s*=?\s*(\d+\.?\d*).*?slope\s*=?\s*(\d+\.?\d*).*?(\d+\.?\d*)\s*m/s"
       r"|velocity.*?(\d+\.?\d*)\s*m/s.*?manning",
       "hydrology")
def _hyd_manning(m, text):
    import re as _re
    n_m = _re.search(r'[Mm]anning.*?n\s*=\s*(\d+\.?\d*)|n\s*=\s*(\d+\.?\d*).*?[Mm]anning', text, _re.I)
    r_m = _re.search(r'(?:hydraulic\s+)?radius\s*=?\s*(\d+\.?\d*)', text, _re.I)
    s_m = _re.search(r'slope\s*=?\s*(\d+\.?\d*)', text, _re.I)
    v_m = _re.search(r'(\d+\.?\d*)\s*m/s', text, _re.I)
    if not (n_m and r_m and s_m and v_m):
        return None
    return {"manning_n": _num(n_m.group(1) or n_m.group(2)),
            "hydraulic_radius_m": _num(r_m.group(1)),
            "slope": _num(s_m.group(1)),
            "claimed_velocity_m_s": _num(v_m.group(1))}


# ── LINGUISTICS ───────────────────────────────────────────────────────────────

@_rule("ling_strongs",
       r"(?:Strong['']s\s+)?(?:number\s+)?([GH]\d+)\s+(?:means?|is|represents?)\s+(\w+)"
       r"|([GH]\d+)\s+[\(\"'](\w+)[\)\"']",
       "linguistics")
def _ling_strongs(m, text):
    import re as _re
    strongs_m = _re.search(r'\b([GH]\d+)\b', text)
    if not strongs_m:
        return None
    # A gloss is a WORD, never a bare number — "G4 is 7" (a musical note + a
    # semitone count) must not be read as a Strong's gloss.
    gloss_m = _re.search(r"[GH]\d+\s+(?:means?|is|represents?)\s+([A-Za-z][\w-]*)", text, _re.I)
    quoted = _re.search(r"[GH]\d+\s*[\(\"']\s*([A-Za-z][\w-]*)", text)
    has_context = bool(_re.search(r"strong|hebrew|greek|lexicon|lemma|septuagint|transliterat", text.lower()))
    # Require a genuine Strong's context: the keyword, a quoted gloss, or a word
    # gloss. A stray "G4"/"H2" token (a musical note, a grid ref) must not trigger
    # a lexicon lookup that then "confirms" an unrelated claim.
    if not (has_context or quoted or gloss_m):
        return None
    spec = {"strongs": strongs_m.group(1)}
    g = gloss_m.group(1) if gloss_m else (quoted.group(1) if quoted else None)
    if g:
        spec["gloss_claim"] = g
    return spec


# ── EXERCISE SCIENCE — BIOLOGY overlap: Hardy-Weinberg ───────────────────────

@_rule("bio_hardy_weinberg",
       r"p\^?2\s*\+\s*2pq\s*\+\s*q\^?2|hardy.weinberg.*?p\s*=\s*(\d+\.?\d*).*?q\s*=\s*(\d+\.?\d*)",
       "biology")
def _bio_hw(m, text):
    import re as _re
    p_m = _re.search(r'\bp\s*=\s*(\d+\.?\d*)', text, _re.I)
    q_m = _re.search(r'\bq\s*=\s*(\d+\.?\d*)', text, _re.I)
    if not (p_m and q_m):
        return {"hardy_weinberg": {"check": "equilibrium"}}
    p, q = _num(p_m.group(1)), _num(q_m.group(1))
    return {"hardy_weinberg": {"p": p, "q": q, "claimed_equilibrium": abs(p + q - 1.0) < 0.001}}


# ── PERIODIC TABLE ────────────────────────────────────────────────────────────
# Gap fill 2026-06-07: verifier existed, no rule -> every element claim hit oracle.

@_rule("periodic_table",
       r"atomic\s+number\s+of\s+\w+\s+is\s+\d+"
       r"|\w+\s+has\s+(?:an?\s+)?atomic\s+number\s+(?:of\s+)?\d+"
       r"|(?:chemical\s+)?symbol\s+(?:for|of)\s+\w+\s+is\s+[A-Z][a-z]?\b",
       "periodic_table")
def _periodic_table(m, text):
    import re as _re

    def _elkey(tok):
        tok = tok.strip()
        if 1 <= len(tok) <= 2 and tok.isalpha():
            return ("symbol", tok.capitalize())
        return ("name", tok.lower())

    an = (_re.search(r'atomic\s+number\s+of\s+(\w+)\s+is\s+(\d+)', text, _re.I)
          or _re.search(r'(\w+)\s+has\s+(?:an?\s+)?atomic\s+number\s+(?:of\s+)?(\d+)', text, _re.I))
    if an:
        k, v = _elkey(an.group(1))
        return {k: v, "claimed_atomic_number": int(an.group(2))}
    sym = _re.search(r'symbol\s+(?:for|of)\s+(\w+)\s+is\s+([A-Z][a-z]?)\b', text)
    if sym:
        return {"name": sym.group(1).lower(), "claimed_symbol": sym.group(2)}
    return None


# ── LINEAR ALGEBRA ────────────────────────────────────────────────────────────

@_rule("linear_algebra",
       r"(?:determinant|det)\s+(?:of\s+)?\[\[.*?\]\]\s*(?:is|=|equals)\s*-?\d"
       r"|dot\s+product\s+of\s+\[.*?\]\s+and\s+\[.*?\]\s*(?:is|=|equals)\s*-?\d",
       "linear_algebra")
def _linalg(m, text):
    import re as _re
    import ast as _ast
    det = _re.search(r'(?:determinant|det)\s+(?:of\s+)?(\[\[.*?\]\])\s*(?:is|=|equals)\s*(-?\d+\.?\d*)', text, _re.I)
    if det:
        try:
            mat = _ast.literal_eval(det.group(1))
        except Exception:
            return None
        return {"matrix": mat, "claimed_determinant": float(det.group(2))}
    dp = _re.search(r'dot\s+product\s+of\s+(\[.*?\])\s+and\s+(\[.*?\])\s*(?:is|=|equals)\s*(-?\d+\.?\d*)', text, _re.I)
    if dp:
        try:
            a = _ast.literal_eval(dp.group(1))
            b = _ast.literal_eval(dp.group(2))
        except Exception:
            return None
        return {"vec_a": a, "vec_b": b, "claimed_dot_product": float(dp.group(3))}
    return None


# ── NUCLEAR PHYSICS ───────────────────────────────────────────────────────────

@_rule("nuclear_physics",
       r"after\s+\d+\.?\d*\s+half-?li(?:fe|ves)\b.*?\d+\.?\d*\s*(?:%|percent)",
       "nuclear_physics")
def _nuc_halflife(m, text):
    import re as _re
    hm = _re.search(r'after\s+(\d+\.?\d*)\s+half-?li(?:fe|ves)', text, _re.I)
    pm = _re.search(r'(\d+\.?\d*)\s*(?:%|percent)', text)
    if not (hm and pm):
        return None
    if not _re.search(r'remain|left|undecayed', text, _re.I):
        return None  # "% remaining after N half-lives" is the claim shape
    return {"half_life_seconds": 1.0, "elapsed_seconds": float(hm.group(1)),
            "initial_count": 100.0, "claimed_remaining_count": float(pm.group(1))}


# ── PROBABILITY ───────────────────────────────────────────────────────────────

@_rule("probability",
       r"expected\s+value\s+of\s+a\s+(?:fair\s+)?\d+[\s-]*sided\s+(?:die|dice)",
       "probability")
def _prob_ev_die(m, text):
    import re as _re
    mm = _re.search(r'expected\s+value\s+of\s+a\s+(?:fair\s+)?(\d+)[\s-]*sided\s+(?:die|dice)[^\d]*(\d+\.?\d*)',
                    text, _re.I)
    if not mm:
        return None
    n = int(mm.group(1))
    if not (2 <= n <= 1000):
        return None
    return {"outcomes": list(range(1, n + 1)), "probabilities": [1.0 / n] * n,
            "claimed_expected_value": float(mm.group(2))}


# ── HISTORY / CHRONOLOGY ──────────────────────────────────────────────────────

@_rule("history_chronology",
       r"(?:from\s+)?\d{3,4}\s*(?:to|until|-|–)\s*\d{3,4}\s+is\s+\d+\s*years?"
       r"|\d+\s*years?\s+(?:between|from)\s+\d{3,4}\s+(?:and|to)\s+\d{3,4}",
       "history_chronology")
def _hist_elapsed(m, text):
    import re as _re
    a = _re.search(r'(?:from\s+)?(\d{3,4})\s*(?:to|until|-|–)\s*(\d{3,4})\s+is\s+(\d+)\s*years?', text, _re.I)
    if a:
        return {"from_year": int(a.group(1)), "to_year": int(a.group(2)),
                "claimed_elapsed_years": int(a.group(3))}
    b = _re.search(r'(\d+)\s*years?\s+(?:between|from)\s+(\d{3,4})\s+(?:and|to)\s+(\d{3,4})', text, _re.I)
    if b:
        y1, y2 = int(b.group(2)), int(b.group(3))
        return {"from_year": min(y1, y2), "to_year": max(y1, y2),
                "claimed_elapsed_years": int(b.group(1))}
    return None


# ── MATERIALS SCIENCE ─────────────────────────────────────────────────────────

@_rule("materials_science",
       r"densit(?:y|ies)\b.*?\d+\.?\d*\s*kg"
       r"|\(\s*mohs\s+\d+\.?\d*\s*\).*?harder\s+than.*?\(\s*mohs\s+\d+\.?\d*\s*\)",
       "materials_science")
def _materials(m, text):
    import re as _re
    low = text.lower()
    if "densit" in low:
        mass = _re.search(r'(\d+\.?\d*)\s*kg(?!\s*/)', text, _re.I)
        vol = _re.search(r'(\d+\.?\d*)\s*(?:m\^?3|m3|cubic\s+met\w+)', text, _re.I)
        dens = _re.search(r'(\d+\.?\d*)\s*kg\s*/\s*m\^?3|densit\w+\s+(?:of\s+|is\s+)?(\d+\.?\d*)', text, _re.I)
        if mass and vol and dens:
            d = dens.group(1) or dens.group(2)
            return {"mass_kg": float(mass.group(1)), "volume_m3": float(vol.group(1)),
                    "claimed_density_kg_per_m3": float(d)}
    hm = _re.search(r'\(\s*mohs\s+(\d+\.?\d*)\s*\).*?harder\s+than.*?\(\s*mohs\s+(\d+\.?\d*)\s*\)', text, _re.I)
    if hm:
        return {"material_a_hardness": float(hm.group(1)),
                "material_b_hardness": float(hm.group(2)), "claimed_a_harder_than_b": True}
    return None


# ── Dispatch function ─────────────────────────────────────────────────

def dispatch(text: str) -> Optional[DispatchResult]:
    """Try every rule in priority order. Return the first match or None.

    Order:
      1. hard-coded rules (this module — ship with the engine)
      2. runtime rules (operator-promoted from misalignment review,
         loaded from data/agent/runtime_rules.jsonl)

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

    # Fall through to runtime rules — operator promotions compound here.
    try:
        from concordance_engine.agent.runtime_rules import try_dispatch as _rt_try
        rt = _rt_try(text)
        if rt is not None:
            return DispatchResult(
                domain=rt["domain"],
                spec=rt.get("spec") or {},
                rule_id=rt["rule_id"],
                confidence=0.95,  # slightly lower than hard-coded
                raw_text=text,
            )
    except Exception:
        pass

    return None


def list_rules() -> List[Dict[str, Any]]:
    """Return all registered rules for introspection / debugging."""
    return [
        {"rule_id": rid, "domain": dom, "pattern": pat.pattern}
        for rid, pat, dom, _ in _RULES
    ]
