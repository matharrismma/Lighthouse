"""Exercise science verifier (biology umbrella, metabolism/lifecycle axis
sibling to nutrition + agriculture + genetics).

Deterministic checks against public-domain exercise-physiology reference
data: MET (Metabolic Equivalent of Task) values from the Compendium of
Physical Activities, Karvonen and Tanaka heart-rate formulas, and basic
energy-expenditure arithmetic.

Note on MET data: the Ainsworth Compendium of Physical Activities is
widely published and the *concept* + canonical MET values are public-domain
reference. We embed only a small dictionary of ~25 common activities; for
exhaustive coverage callers can supply their own table via spec.

Checks performed:

  * exercise_science.energy_expenditure
      kcal = MET × weight_kg × duration_hours. Total expenditure for
      an activity at a given weight & duration matches claim.
  * exercise_science.target_heart_rate_zone
      Karvonen-style HR zone bounds at given intensity_low/intensity_high
      (decimals 0-1) match claim within tolerance.
  * exercise_science.max_heart_rate
      Tanaka 2001 formula HRmax = 208 - 0.7·age (more accurate than
      220-age across adult range) matches claim.
  * exercise_science.met_lookup
      Activity name resolves to a known MET value (within tolerance of
      claim).

EX_VERIFY packet shape (any subset of fields):
    {
      "activity": "running_6mph",
      "claimed_met": 9.8,
      "weight_kg": 70,
      "duration_hours": 0.5,
      "claimed_kcal": 343,
      "tolerance_kcal": 5,
      "age_years": 30,
      "claimed_max_hr": 187,
      "resting_hr": 60,
      "intensity_low": 0.5, "intensity_high": 0.7,
      "claimed_zone_low_bpm": 124, "claimed_zone_high_bpm": 149,
      "tolerance_bpm": 1,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


# Public-domain reference MET values for common activities.
# Derived from the Compendium of Physical Activities (Ainsworth et al.).
# Single representative value per activity name; for finer distinctions
# callers can pass `claimed_met` explicitly via spec and the lookup check
# will compare against the embedded value.
_MET_TABLE: Dict[str, float] = {
    "sleeping":             0.95,
    "sitting_quietly":      1.3,
    "standing":             1.5,
    "walking_2mph":         2.8,
    "walking_3mph":         3.3,
    "walking_4mph":         5.0,
    "running_5mph":         8.3,
    "running_6mph":         9.8,
    "running_7mph":        11.0,
    "running_8mph":        11.8,
    "cycling_leisure":      4.0,
    "cycling_moderate":     6.8,
    "cycling_vigorous":    10.0,
    "swimming_freestyle_moderate": 5.8,
    "swimming_freestyle_vigorous": 9.8,
    "yoga_hatha":           2.5,
    "yoga_power":           4.0,
    "weight_lifting_general": 3.5,
    "weight_lifting_vigorous": 6.0,
    "rowing_moderate":      6.0,
    "rowing_vigorous":      8.5,
    "hiking":               6.0,
    "stretching":           2.3,
    "chopping_wood":        4.5,
    "shoveling_snow":       5.3,
}


def verify_energy_expenditure(spec: Dict[str, Any]) -> VerifierResult:
    """kcal = MET × weight_kg × duration_hours."""
    name = "exercise_science.energy_expenditure"
    met = spec.get("claimed_met")
    weight = spec.get("weight_kg")
    duration = spec.get("duration_hours")
    claimed = spec.get("claimed_kcal")
    if met is None or weight is None or duration is None or claimed is None:
        return na(name)
    try:
        m = float(met)
        w = float(weight)
        d = float(duration)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"non-numeric input")
    if m <= 0 or w <= 0 or d < 0:
        return error(name, f"MET, weight must be > 0; duration >= 0 (got {m}, {w}, {d})")
    actual = m * w * d
    tol = float(spec.get("tolerance_kcal", 5.0))
    diff = abs(actual - c)
    data = {"actual_kcal": actual, "claimed_kcal": c, "diff_kcal": diff,
            "met": m, "weight_kg": w, "duration_hours": d, "tolerance_kcal": tol}
    if diff <= tol:
        return confirm(name,
                       f"{m} MET × {w}kg × {d}h = {actual:.1f} kcal (matches claim {c}, diff {diff:.1f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"{m} MET × {w}kg × {d}h = {actual:.1f} kcal, claimed {c} (diff {diff:.1f} > tol {tol})",
                    data)


def verify_max_heart_rate(spec: Dict[str, Any]) -> VerifierResult:
    """Tanaka 2001: HRmax = 208 - 0.7·age (more accurate than 220-age)."""
    name = "exercise_science.max_heart_rate"
    age = spec.get("age_years")
    claimed = spec.get("claimed_max_hr")
    if age is None or claimed is None:
        return na(name)
    try:
        a = float(age)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"age and claimed_max_hr must be numeric")
    if a < 0 or a > 130:
        return error(name, f"age out of plausible range [0, 130], got {a}")
    actual = 208.0 - 0.7 * a
    tol = float(spec.get("tolerance_bpm", 2.0))
    diff = abs(actual - c)
    data = {"actual_bpm": actual, "claimed_bpm": c, "diff_bpm": diff,
            "age_years": a, "formula": "Tanaka 2001 (208 - 0.7·age)"}
    if diff <= tol:
        return confirm(name,
                       f"HRmax = 208 - 0.7·{a} = {actual:.1f} bpm (matches claim {c}, diff {diff:.1f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"HRmax = 208 - 0.7·{a} = {actual:.1f} bpm, claimed {c} (diff {diff:.1f} > tol {tol})",
                    data)


def verify_target_heart_rate_zone(spec: Dict[str, Any]) -> VerifierResult:
    """Karvonen formula: target = ((HRmax - HRrest) × intensity) + HRrest."""
    name = "exercise_science.target_heart_rate_zone"
    age = spec.get("age_years")
    rest = spec.get("resting_hr")
    intensity_low = spec.get("intensity_low")
    intensity_high = spec.get("intensity_high")
    claimed_low = spec.get("claimed_zone_low_bpm")
    claimed_high = spec.get("claimed_zone_high_bpm")
    if (age is None or rest is None or intensity_low is None
            or intensity_high is None
            or claimed_low is None or claimed_high is None):
        return na(name)
    try:
        a = float(age)
        rest_v = float(rest)
        il = float(intensity_low)
        ih = float(intensity_high)
        cl = float(claimed_low)
        ch = float(claimed_high)
    except (TypeError, ValueError):
        return error(name, "all fields must be numeric")
    if a < 0 or a > 130:
        return error(name, f"age out of plausible range, got {a}")
    if rest_v <= 0 or rest_v > 120:
        return error(name, f"resting_hr out of plausible range, got {rest_v}")
    if not (0.0 <= il <= 1.0) or not (0.0 <= ih <= 1.0):
        return error(name, f"intensity must be a fraction in [0, 1], got {il}, {ih}")
    if il > ih:
        return error(name, f"intensity_low ({il}) > intensity_high ({ih})")
    hrmax = 208.0 - 0.7 * a
    hrr = hrmax - rest_v
    actual_low = (hrr * il) + rest_v
    actual_high = (hrr * ih) + rest_v
    tol = float(spec.get("tolerance_bpm", 1.0))
    data = {"hrmax": hrmax, "hrr": hrr,
            "actual_low_bpm": actual_low, "actual_high_bpm": actual_high,
            "claimed_low_bpm": cl, "claimed_high_bpm": ch,
            "intensity_low": il, "intensity_high": ih, "tolerance_bpm": tol}
    if abs(actual_low - cl) <= tol and abs(actual_high - ch) <= tol:
        return confirm(name,
                       f"zone {il:.0%}-{ih:.0%}: {actual_low:.0f}–{actual_high:.0f} bpm "
                       f"(matches claim {cl:.0f}–{ch:.0f} within {tol})",
                       data)
    return mismatch(name,
                    f"zone {il:.0%}-{ih:.0%}: {actual_low:.0f}–{actual_high:.0f} bpm, "
                    f"claimed {cl:.0f}–{ch:.0f}",
                    data)


def verify_met_lookup(spec: Dict[str, Any]) -> VerifierResult:
    """Activity name resolves to a known MET value within tolerance of claim."""
    name = "exercise_science.met_lookup"
    activity = (spec.get("activity") or "").lower().strip()
    claimed = spec.get("claimed_met")
    if not activity or claimed is None:
        return na(name)
    if activity not in _MET_TABLE:
        return na(name, f"no MET data for activity {activity!r}")
    try:
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_met must be numeric, got {claimed!r}")
    actual = _MET_TABLE[activity]
    tol = float(spec.get("tolerance_met", 0.5))
    diff = abs(actual - c)
    data = {"activity": activity, "actual_met": actual, "claimed_met": c,
            "diff": diff, "tolerance_met": tol}
    if diff <= tol:
        return confirm(name,
                       f"{activity} MET = {actual} (matches claim {c}, diff {diff:.1f} ≤ {tol})",
                       data)
    return mismatch(name,
                    f"{activity} MET = {actual} per Compendium, claimed {c} (diff {diff:.1f} > tol {tol})",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    ev = packet.get("EX_VERIFY") or {}

    if all(k in ev for k in ("claimed_met", "weight_kg", "duration_hours", "claimed_kcal")):
        results.append(verify_energy_expenditure(ev))
    if "age_years" in ev and "claimed_max_hr" in ev:
        results.append(verify_max_heart_rate(ev))
    if all(k in ev for k in ("age_years", "resting_hr", "intensity_low",
                             "intensity_high", "claimed_zone_low_bpm",
                             "claimed_zone_high_bpm")):
        results.append(verify_target_heart_rate_zone(ev))
    if "activity" in ev and "claimed_met" in ev:
        results.append(verify_met_lookup(ev))

    if not results:
        results.append(na("exercise_science", "no EX_VERIFY artifacts present"))
    return results
