"""Medicine / Clinical verifier.

Deterministic checks on clinical calculations using established medical
formulas. All formulas are public-domain (NIH, AHA, WHO standards).

Checks:
  * medicine.bmi                 — BMI = weight_kg / height_m^2 + classification
  * medicine.drug_dosage         — dose_mg = dose_mg_per_kg * weight_kg
  * medicine.blood_pressure      — systolic/diastolic classification (AHA 2017)
  * medicine.a1c_to_eag          — eAG = 28.7 * A1C - 46.7 (ADA formula)
  * medicine.egfr_cockcroft      — Cockcroft-Gault eGFR (mL/min)
  * medicine.ibw_devine          — Ideal body weight, Devine formula (kg)
  * medicine.map                 — Mean arterial pressure = DBP + (SBP-DBP)/3

MED_VERIFY packet shape (any subset):
    {
      "weight_kg": 70.0, "height_m": 1.75,
      "claimed_bmi": 22.9, "claimed_bmi_class": "normal",

      "dose_mg_per_kg": 5.0,
      "claimed_dose_mg": 350.0,

      "systolic": 125, "diastolic": 82,
      "claimed_bp_class": "elevated",

      "a1c_pct": 7.0, "claimed_eag_mg_dl": 154.4,

      "age_years": 45, "sex": "male", "serum_creatinine": 1.1,
      "claimed_egfr": 75.0,

      "height_in": 70, "sex_ibw": "male",
      "claimed_ibw_kg": 75.5,

      "claimed_map_mmhg": 96.3,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

# ── BMI ──────────────────────────────────────────────────────────────────────

_BMI_CLASSES = [
    (18.5, "underweight"),
    (25.0, "normal"),
    (30.0, "overweight"),
    (math.inf, "obese"),
]


def _bmi_class(bmi: float) -> str:
    for threshold, label in _BMI_CLASSES:
        if bmi < threshold:
            return label
    return "obese"


def verify_bmi(spec: Dict[str, Any]) -> VerifierResult:
    name = "medicine.bmi"
    w = spec.get("weight_kg")
    h = spec.get("height_m")
    claimed_bmi = spec.get("claimed_bmi")
    claimed_class = spec.get("claimed_bmi_class")
    if w is None or h is None:
        return na(name)
    try:
        wf, hf = float(w), float(h)
    except (TypeError, ValueError):
        return error(name, "weight_kg and height_m must be numeric")
    if hf <= 0:
        return error(name, f"height_m must be positive, got {hf}")
    bmi = wf / (hf ** 2)
    bmi_cat = _bmi_class(bmi)
    tol = float(spec.get("tolerance_bmi", 0.1))
    data = {"weight_kg": wf, "height_m": hf, "bmi": round(bmi, 2),
            "classification": bmi_cat,
            "formula": "BMI = weight_kg / height_m^2"}
    if claimed_bmi is not None:
        try:
            c = float(claimed_bmi)
        except (TypeError, ValueError):
            return error(name, "claimed_bmi must be numeric")
        diff = abs(bmi - c)
        if diff > tol:
            return mismatch(name, f"BMI = {bmi:.2f}, claimed {c} (diff {diff:.2f})", data)
    if claimed_class is not None:
        if str(claimed_class).lower() != bmi_cat:
            return mismatch(name,
                            f"BMI {bmi:.2f} class is '{bmi_cat}', claimed '{claimed_class}'",
                            data)
    if claimed_bmi is None and claimed_class is None:
        return na(name, "no claimed_bmi or claimed_bmi_class to check")
    return confirm(name, f"BMI = {bmi:.2f} ({bmi_cat})", data)


# ── Drug dosage ───────────────────────────────────────────────────────────────

def verify_drug_dosage(spec: Dict[str, Any]) -> VerifierResult:
    name = "medicine.drug_dosage"
    dose_per_kg = spec.get("dose_mg_per_kg")
    weight = spec.get("weight_kg")
    claimed = spec.get("claimed_dose_mg")
    if dose_per_kg is None or weight is None or claimed is None:
        return na(name)
    try:
        dpk, wf, c = float(dose_per_kg), float(weight), float(claimed)
    except (TypeError, ValueError):
        return error(name, "dose_mg_per_kg, weight_kg, claimed_dose_mg must be numeric")
    actual = dpk * wf
    tol = float(spec.get("tolerance_mg", max(0.5, actual * 0.02)))  # 2% or 0.5mg
    diff = abs(actual - c)
    data = {"dose_mg_per_kg": dpk, "weight_kg": wf,
            "actual_dose_mg": actual, "claimed_dose_mg": c,
            "diff_mg": diff, "formula": "dose = dose_mg_per_kg * weight_kg"}
    if diff <= tol:
        return confirm(name, f"{dpk} mg/kg × {wf} kg = {actual:.1f} mg (matches claim)", data)
    return mismatch(name, f"dose = {actual:.1f} mg, claimed {c} mg (diff {diff:.1f})", data)


# ── Blood pressure classification (AHA 2017) ─────────────────────────────────

_BP_CLASSES = [
    # (systolic_max, diastolic_max, label) — first match wins
    (120, 80, "normal"),
    (130, 80, "elevated"),    # systolic 120-129 and diastolic <80
    (140, 90, "hypertension_stage_1"),
    (180, 120, "hypertension_stage_2"),
    (math.inf, math.inf, "hypertensive_crisis"),
]


def _bp_class(sys: float, dia: float) -> str:
    if sys < 120 and dia < 80:
        return "normal"
    if sys < 130 and dia < 80:
        return "elevated"
    if sys < 140 or dia < 90:
        return "hypertension_stage_1"
    if sys < 180 and dia < 120:
        return "hypertension_stage_2"
    return "hypertensive_crisis"


def verify_blood_pressure(spec: Dict[str, Any]) -> VerifierResult:
    name = "medicine.blood_pressure"
    sys = spec.get("systolic")
    dia = spec.get("diastolic")
    claimed_class = spec.get("claimed_bp_class")
    if sys is None or dia is None or claimed_class is None:
        return na(name)
    try:
        sf, df = float(sys), float(dia)
    except (TypeError, ValueError):
        return error(name, "systolic, diastolic must be numeric")
    bp_cat = _bp_class(sf, df)
    data = {"systolic": sf, "diastolic": df, "classification": bp_cat,
            "standard": "AHA 2017 guidelines"}
    if str(claimed_class).lower() == bp_cat:
        return confirm(name, f"{sf}/{df} mmHg classified as '{bp_cat}'", data)
    return mismatch(name,
                    f"{sf}/{df} mmHg is '{bp_cat}', claimed '{claimed_class}'",
                    data)


# ── A1C to estimated average glucose (ADA) ───────────────────────────────────

def verify_a1c_to_eag(spec: Dict[str, Any]) -> VerifierResult:
    """ADA formula: eAG (mg/dL) = 28.7 * A1C(%) - 46.7"""
    name = "medicine.a1c_to_eag"
    a1c = spec.get("a1c_pct")
    claimed = spec.get("claimed_eag_mg_dl")
    if a1c is None or claimed is None:
        return na(name)
    try:
        af, c = float(a1c), float(claimed)
    except (TypeError, ValueError):
        return error(name, "a1c_pct and claimed_eag_mg_dl must be numeric")
    actual = 28.7 * af - 46.7
    tol = float(spec.get("tolerance_mg_dl", 3.0))
    diff = abs(actual - c)
    data = {"a1c_pct": af, "actual_eag_mg_dl": round(actual, 1),
            "claimed_eag_mg_dl": c, "diff_mg_dl": diff,
            "formula": "eAG = 28.7 * A1C - 46.7 (ADA)"}
    if diff <= tol:
        return confirm(name, f"A1C {af}% → eAG {actual:.1f} mg/dL (matches claim)", data)
    return mismatch(name, f"eAG = {actual:.1f} mg/dL, claimed {c} (diff {diff:.1f})", data)


# ── eGFR Cockcroft-Gault ──────────────────────────────────────────────────────

def verify_egfr_cockcroft(spec: Dict[str, Any]) -> VerifierResult:
    """Cockcroft-Gault: eGFR = ((140-age) * weight * sex_factor) / (72 * Cr)
    sex_factor = 1.0 for male, 0.85 for female.
    """
    name = "medicine.egfr_cockcroft"
    age = spec.get("age_years")
    weight = spec.get("weight_kg")
    creatinine = spec.get("serum_creatinine")
    sex = str(spec.get("sex", "male")).lower()
    claimed = spec.get("claimed_egfr")
    if any(v is None for v in (age, weight, creatinine, claimed)):
        return na(name)
    try:
        af, wf, cr, c = float(age), float(weight), float(creatinine), float(claimed)
    except (TypeError, ValueError):
        return error(name, "age, weight, creatinine, claimed_egfr must be numeric")
    if cr <= 0:
        return error(name, f"serum_creatinine must be > 0, got {cr}")
    sex_factor = 0.85 if sex == "female" else 1.0
    actual = ((140 - af) * wf * sex_factor) / (72 * cr)
    tol = float(spec.get("tolerance_egfr", 5.0))  # ±5 mL/min
    diff = abs(actual - c)
    data = {"age_years": af, "weight_kg": wf, "serum_creatinine": cr,
            "sex": sex, "sex_factor": sex_factor,
            "actual_egfr": round(actual, 1), "claimed_egfr": c,
            "formula": "((140-age)*weight*sex_factor) / (72*Cr)"}
    if diff <= tol:
        return confirm(name, f"eGFR = {actual:.1f} mL/min (matches claim)", data)
    return mismatch(name, f"eGFR = {actual:.1f}, claimed {c} (diff {diff:.1f})", data)


# ── Ideal body weight (Devine formula) ───────────────────────────────────────

def verify_ibw_devine(spec: Dict[str, Any]) -> VerifierResult:
    """Devine formula:
    Male:   IBW = 50 + 2.3 * (height_in - 60)
    Female: IBW = 45.5 + 2.3 * (height_in - 60)
    """
    name = "medicine.ibw_devine"
    height_in = spec.get("height_in")
    sex = str(spec.get("sex_ibw", "male")).lower()
    claimed = spec.get("claimed_ibw_kg")
    if height_in is None or claimed is None:
        return na(name)
    try:
        hf, c = float(height_in), float(claimed)
    except (TypeError, ValueError):
        return error(name, "height_in and claimed_ibw_kg must be numeric")
    base = 50.0 if sex == "male" else 45.5
    actual = base + 2.3 * (hf - 60)
    tol = float(spec.get("tolerance_ibw_kg", 1.0))
    diff = abs(actual - c)
    data = {"height_in": hf, "sex": sex, "base_kg": base,
            "actual_ibw_kg": round(actual, 1), "claimed_ibw_kg": c,
            "formula": f"{base} + 2.3 * (height_in - 60) (Devine)"}
    if diff <= tol:
        return confirm(name, f"IBW = {actual:.1f} kg (matches claim)", data)
    return mismatch(name, f"IBW = {actual:.1f} kg, claimed {c} (diff {diff:.1f})", data)


# ── Mean arterial pressure ────────────────────────────────────────────────────

def verify_map(spec: Dict[str, Any]) -> VerifierResult:
    """MAP = DBP + (SBP - DBP) / 3"""
    name = "medicine.map"
    sys = spec.get("systolic")
    dia = spec.get("diastolic")
    claimed = spec.get("claimed_map_mmhg")
    if sys is None or dia is None or claimed is None:
        return na(name)
    try:
        sf, df, c = float(sys), float(dia), float(claimed)
    except (TypeError, ValueError):
        return error(name, "systolic, diastolic, claimed_map_mmhg must be numeric")
    actual = df + (sf - df) / 3.0
    tol = float(spec.get("tolerance_map_mmhg", 1.0))
    diff = abs(actual - c)
    data = {"systolic": sf, "diastolic": df,
            "actual_map_mmhg": round(actual, 2), "claimed_map_mmhg": c,
            "formula": "MAP = DBP + (SBP - DBP) / 3"}
    if diff <= tol:
        return confirm(name, f"MAP = {actual:.1f} mmHg (matches claim)", data)
    return mismatch(name, f"MAP = {actual:.1f} mmHg, claimed {c} (diff {diff:.1f})", data)


# ── run ───────────────────────────────────────────────────────────────────────

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MED_VERIFY") or {}
    if "weight_kg" in mv and "height_m" in mv:
        results.append(verify_bmi(mv))
    if "dose_mg_per_kg" in mv and "weight_kg" in mv:
        results.append(verify_drug_dosage(mv))
    if "systolic" in mv and "diastolic" in mv:
        if "claimed_bp_class" in mv:
            results.append(verify_blood_pressure(mv))
        if "claimed_map_mmhg" in mv:
            results.append(verify_map(mv))
    if "a1c_pct" in mv and "claimed_eag_mg_dl" in mv:
        results.append(verify_a1c_to_eag(mv))
    if all(k in mv for k in ("age_years", "weight_kg", "serum_creatinine", "claimed_egfr")):
        results.append(verify_egfr_cockcroft(mv))
    if "height_in" in mv and "claimed_ibw_kg" in mv:
        results.append(verify_ibw_devine(mv))
    if not results:
        results.append(na("medicine", "no MED_VERIFY artifacts present"))
    return results
