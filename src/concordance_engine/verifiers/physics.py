"""Physics verifier.

Checks performed:
  * dimensional_consistency: parses both sides of an equation and verifies
    that they reduce to the same SI dimension tuple
    (mass, length, time, current, temperature, amount, luminous_intensity)
  * conservation: given before/after dictionaries of conserved quantities
    (mass, energy, momentum, charge, ...), verify within tolerance

Equation format for dimensional check:
    "F = m * a"           # symbolic — uses sympy.physics.units
    "v = sqrt(2 * g * h)" # mixed numeric/symbolic
    Each named symbol must appear in `symbols`, mapping name -> unit string,
    e.g. {"F": "newton", "m": "kilogram", "a": "meter/second**2"}.

Conservation format:
    {"before": {"momentum": 12.5, "energy": 100.0},
     "after":  {"momentum": 12.499, "energy": 99.998},
     "tolerance_relative": 0.001}
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import VerifierResult, na, confirm, mismatch, error

import sympy
from sympy import sympify, simplify, Symbol
from sympy.physics import units as u
from sympy.physics.units.systems.si import SI


# Map common unit strings to sympy unit objects
_UNIT_TABLE = {
    # length
    "m": u.meter, "meter": u.meter, "meters": u.meter,
    "cm": u.centimeter, "mm": u.millimeter, "km": u.kilometer,
    # mass
    "kg": u.kilogram, "kilogram": u.kilogram, "kilograms": u.kilogram,
    "g": u.gram, "gram": u.gram, "grams": u.gram,
    # time
    "s": u.second, "sec": u.second, "second": u.second, "seconds": u.second,
    "ms": u.millisecond, "min": u.minute, "hr": u.hour, "h": u.hour,
    # force/energy/power
    "N": u.newton, "newton": u.newton, "newtons": u.newton,
    "J": u.joule, "joule": u.joule, "joules": u.joule,
    "W": u.watt, "watt": u.watt,
    # charge / current
    "C": u.coulomb, "coulomb": u.coulomb,
    "A": u.ampere, "ampere": u.ampere,
    # temperature
    "K": u.kelvin, "kelvin": u.kelvin,
    # pressure
    "Pa": u.pascal, "pascal": u.pascal, "atm": u.atmosphere, "atmosphere": u.atmosphere,
    # frequency
    "Hz": u.hertz, "hertz": u.hertz,
}


def _parse_unit(unit_str: str):
    """Parse 'meter/second**2' or 'kg*m/s**2' into a sympy units expression."""
    s = unit_str.replace("^", "**")
    # Replace bare unit tokens with sympify-friendly wrappers
    expr = sympify(s, locals=_UNIT_TABLE)
    return expr


def verify_dimensional_consistency(
    equation: str,
    symbols: Dict[str, str],
) -> VerifierResult:
    """Verify both sides of an equation have the same SI dimensions.

    Strategy: substitute each symbol with its unit expression, then convert
    both sides to a fixed set of SI base units and compare unit signatures.
    """
    if "=" not in equation:
        return error("physics.dimensional", f"no '=' in equation {equation!r}")

    lhs_str, rhs_str = equation.split("=", 1)

    # Parse equation with ONLY the user's variable names as locals so
    # that 'm', 's', etc. are read as variables, not as unit tokens.
    eq_locals = {name: Symbol(name) for name in symbols.keys()}
    try:
        lhs = sympify(lhs_str.strip(), locals=eq_locals)
        rhs = sympify(rhs_str.strip(), locals=eq_locals)
    except Exception as e:
        return error("physics.dimensional", f"equation parse failure: {e}")

    # Parse units with the unit table (separate namespace).
    try:
        subs = {Symbol(name): _parse_unit(unit_str) for name, unit_str in symbols.items()}
    except Exception as e:
        return error("physics.dimensional", f"unit parse failure: {e}")

    base_units = [u.kilogram, u.meter, u.second, u.ampere, u.kelvin, u.mol, u.candela]
    try:
        lhs_base = u.convert_to(lhs.subs(subs), base_units).n()
        rhs_base = u.convert_to(rhs.subs(subs), base_units).n()
    except Exception as e:
        return error("physics.dimensional", f"unit conversion failure: {e}")

    def _unit_signature(expr):
        if expr.is_number:
            return sympify(1)
        coeff, rest = expr.as_coeff_Mul()
        return rest

    lhs_sig = _unit_signature(lhs_base)
    rhs_sig = _unit_signature(rhs_base)

    if simplify(lhs_sig - rhs_sig) == 0:
        return confirm(
            "physics.dimensional",
            f"both sides reduce to {lhs_sig}",
            {"lhs_units": str(lhs_sig), "rhs_units": str(rhs_sig)},
        )
    return mismatch(
        "physics.dimensional",
        f"LHS units {lhs_sig} != RHS units {rhs_sig}",
        {"lhs_units": str(lhs_sig), "rhs_units": str(rhs_sig)},
    )


def verify_conservation(
    before: Dict[str, float],
    after: Dict[str, float],
    *,
    tolerance_relative: float = 1e-6,
    tolerance_absolute: float = 0.0,
) -> VerifierResult:
    """Check each named quantity is conserved within tolerance."""
    if not before or not after:
        return na("physics.conservation", "missing before or after dict")

    keys = sorted(set(before) | set(after))
    failures = []
    details = {}
    for k in keys:
        b = before.get(k)
        a = after.get(k)
        if b is None or a is None:
            failures.append(f"{k}: present in only one of before/after")
            continue
        diff = abs(a - b)
        scale = max(abs(b), abs(a), 1e-30)
        rel = diff / scale
        details[k] = {"before": b, "after": a, "abs_diff": diff, "rel_diff": rel}
        if rel > tolerance_relative and diff > tolerance_absolute:
            failures.append(f"{k}: {b} -> {a} (rel diff {rel:.3e})")
    if failures:
        return mismatch("physics.conservation", "; ".join(failures), details)
    return confirm("physics.conservation", f"all {len(keys)} quantities conserved", details)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    pv = packet.get("PHYS_VERIFY") or {}

    if "equation" in pv and "symbols" in pv:
        results.append(verify_dimensional_consistency(pv["equation"], pv["symbols"]))

    if "before" in pv and "after" in pv:
        if pv.get("law"):
            results.append(
                verify_named_conservation(
                    pv["law"],
                    pv["before"],
                    pv["after"],
                    tolerance_relative=pv.get("tolerance_relative", 1e-6),
                    tolerance_absolute=pv.get("tolerance_absolute", 0.0),
                )
            )
        else:
            results.append(
                verify_conservation(
                    pv["before"],
                    pv["after"],
                    tolerance_relative=pv.get("tolerance_relative", 1e-6),
                    tolerance_absolute=pv.get("tolerance_absolute", 0.0),
                )
            )

    if not results:
        results.append(na("physics", "no PHYS_VERIFY artifacts present"))
    return results


# ---------------------------------------------------------------------
# V5: named-law conservation presets
# ---------------------------------------------------------------------

_LAW_PROFILES = {
    "energy": {
        "required_keys_any_of": [
            ("kinetic_energy", "potential_energy"),
            ("KE", "PE"),
            ("E_total",),
            ("E",),
        ],
        "preferred_unit": "joule",
    },
    "momentum": {
        "required_keys_any_of": [
            ("p",), ("p_x", "p_y"), ("momentum",), ("p_x", "p_y", "p_z"),
        ],
        "preferred_unit": "kilogram*meter/second",
    },
    "charge": {
        "required_keys_any_of": [("Q",), ("q",), ("charge",), ("total_charge",)],
        "preferred_unit": "coulomb",
    },
    "mass": {
        "required_keys_any_of": [("m",), ("mass",), ("total_mass",)],
        "preferred_unit": "kilogram",
    },
}


def verify_named_conservation(
    law: str, before, after,
    tolerance_relative: float = 1e-6, tolerance_absolute: float = 0.0,
):
    """Conservation check that also enforces a named-law key profile.

    Confirms that the keys in `before` and `after` match a recognized profile
    for the named law, then runs the numeric conservation check.
    """
    law_key = (law or "").lower()
    profile = _LAW_PROFILES.get(law_key)
    if profile is None:
        return error(
            "physics.named_conservation",
            f"unknown law {law!r}; recognized: {sorted(_LAW_PROFILES)}",
        )
    keys = set(before.keys()) | set(after.keys())
    matched_profile = None
    for required in profile["required_keys_any_of"]:
        if all(k in keys for k in required):
            matched_profile = required
            break
    if matched_profile is None:
        return mismatch(
            "physics.named_conservation",
            f"{law} conservation requires one of {profile['required_keys_any_of']!r}; "
            f"got keys {sorted(keys)}",
        )
    # For multi-key profiles (e.g. KE + PE), sum into a total and compare.
    # For single-key profiles, fall back to per-quantity verify_conservation.
    if len(matched_profile) > 1:
        try:
            total_before = sum(float(before[k]) for k in matched_profile)
            total_after = sum(float(after[k]) for k in matched_profile)
        except Exception as e:
            return error("physics.named_conservation", f"sum failed: {e}")
        diff = abs(total_after - total_before)
        rel = diff / abs(total_before) if total_before != 0 else diff
        ok = (diff <= tolerance_absolute) or (rel <= tolerance_relative)
        data = {"law": law, "matched_profile": list(matched_profile),
                "total_before": total_before, "total_after": total_after,
                "abs_diff": diff, "rel_diff": rel,
                "preferred_unit": profile["preferred_unit"]}
        if ok:
            return confirm("physics.named_conservation",
                           f"{law} conserved: total {total_before} -> {total_after} "
                           f"(rel {rel:.2e})", data)
        return mismatch("physics.named_conservation",
                        f"{law} not conserved: total {total_before} -> {total_after} "
                        f"(diff {diff}, rel {rel:.2e})", data)

    result = verify_conservation(
        before, after,
        tolerance_relative=tolerance_relative,
        tolerance_absolute=tolerance_absolute,
    )
    if result.status == "CONFIRMED":
        return confirm("physics.named_conservation",
                       f"{law} conserved (profile {matched_profile}): " + result.detail,
                       {**(result.data or {}), "law": law,
                        "matched_profile": list(matched_profile),
                        "preferred_unit": profile["preferred_unit"]})
    if result.status == "MISMATCH":
        return mismatch("physics.named_conservation",
                        f"{law} not conserved: " + result.detail,
                        {**(result.data or {}), "law": law,
                         "matched_profile": list(matched_profile)})
    return result
                        "matched_profile": list(matched_profile),
                        "preferred_unit": profile["preferred_unit"]})
    if result.status == "MISMATCH":
        return mismatch("physics.named_conservation",
                        f"{law} not conserved: " + result.detail,
                        {**(result.data or {}), "law": law,
                         "matched_profile": list(matched_profile)})
    return result
