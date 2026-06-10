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

# sympy (with sympy.physics.units) is a ~4s import. Only the dimensional-
# consistency check needs it, so it loads on first use rather than at module
# import — this keeps the engine's cold start fast.
sympify = simplify = Symbol = u = None   # populated by _ensure_sympy()
_UNIT_TABLE = None                       # built lazily (sympy unit objects)


def _ensure_sympy() -> None:
    """Import sympy and build the unit table on first use. Idempotent."""
    global sympify, simplify, Symbol, u, _UNIT_TABLE
    if _UNIT_TABLE is not None:
        return
    from sympy import sympify as _sympify, simplify as _simplify, Symbol as _Symbol
    from sympy.physics import units as _u
    sympify, simplify, Symbol, u = _sympify, _simplify, _Symbol, _u
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
    _ensure_sympy()
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
    _ensure_sympy()
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


def verify_kinematic_motion(spec: Dict[str, Any]) -> VerifierResult:
    """1D constant-acceleration kinematics: d = v0·t + 0.5·a·t².

    Inputs (all SI-consistent; the verifier doesn't enforce unit names):
        v0                   — initial velocity (m/s)
        a                    — acceleration (m/s²)
        t                    — elapsed time (s)
        claimed_displacement — claimed position change (m)
        tolerance_relative   — relative tolerance (default 1e-6)
        tolerance_absolute   — absolute tolerance floor (default 1e-9)
    """
    name = "physics.kinematic_motion"
    v0 = spec.get("v0")
    a = spec.get("a")
    t = spec.get("t")
    claimed = spec.get("claimed_displacement")
    if v0 is None or a is None or t is None or claimed is None:
        return na(name)
    try:
        v0_f, a_f, t_f, c_f = float(v0), float(a), float(t), float(claimed)
    except (TypeError, ValueError):
        return error(name, f"non-numeric input: v0={v0!r}, a={a!r}, t={t!r}, claimed={claimed!r}")
    if t_f < 0:
        return mismatch(name, f"time must be non-negative, got {t_f}")
    actual = v0_f * t_f + 0.5 * a_f * t_f * t_f
    rel_tol = float(spec.get("tolerance_relative", 1e-6))
    abs_tol = float(spec.get("tolerance_absolute", 1e-9))
    diff = abs(actual - c_f)
    if diff <= max(abs_tol, rel_tol * max(abs(actual), abs(c_f))):
        return confirm(name,
                       f"d = v0·t + ½·a·t² = {actual:.6g} (matches claim {c_f:.6g})",
                       {"actual": actual, "claimed": c_f, "diff": diff,
                        "v0": v0_f, "a": a_f, "t": t_f})
    return mismatch(name,
                    f"d = v0·t + ½·a·t² = {actual:.6g}, claimed {c_f:.6g} (diff {diff:.3g})",
                    {"actual": actual, "claimed": c_f, "diff": diff,
                     "v0": v0_f, "a": a_f, "t": t_f})


# Speed of light in vacuum (SI: m/s). Public-domain physical constant.
_SPEED_OF_LIGHT_M_PER_S = 299_792_458.0


def verify_relativistic_speed_limit(spec: Dict[str, Any]) -> VerifierResult:
    """Special relativity: no massive object travels at or above c.

    Inputs:
        speed_m_per_s   — claimed speed (in vacuum-equivalent units, m/s)
        massive         — bool: True for objects with rest mass (default True).
                          Photons/gluons/gravitons (massive=False) travel at c.
    A claim that a massive object reaches v ≥ c is a MISMATCH (the
    Lorentz factor diverges; v = c is not attainable for m > 0).
    """
    name = "physics.relativistic_speed_limit"
    v = spec.get("speed_m_per_s")
    if v is None:
        return na(name)
    try:
        v_f = float(v)
    except (TypeError, ValueError):
        return error(name, f"speed must be numeric, got {v!r}")
    if v_f < 0:
        return error(name, f"speed must be non-negative, got {v_f}")
    massive = spec.get("massive", True)
    c = _SPEED_OF_LIGHT_M_PER_S
    data = {"speed_m_per_s": v_f, "c_m_per_s": c, "fraction_of_c": v_f / c, "massive": bool(massive)}
    if not massive:
        # massless particles travel at exactly c.
        if abs(v_f - c) < 1.0:
            return confirm(name, f"massless particle at v = c (within 1 m/s)", data)
        return mismatch(name,
                        f"massless particle should travel at c = {c:.0f} m/s, claim is {v_f:.0f}",
                        data)
    if v_f >= c:
        return mismatch(name,
                        f"massive object cannot reach v = {v_f:.0f} m/s ≥ c = {c:.0f} m/s; "
                        f"Lorentz factor diverges",
                        data)
    return confirm(name,
                   f"massive object at {v_f:.3g} m/s ({v_f/c:.4%} of c), within relativistic bound",
                   data)


def verify_newtons_second_law(spec: Dict[str, Any]) -> VerifierResult:
    """F = m × a (magnitude check, SI units).

    Closes a gap that dimensional analysis can't catch: if user says
    'F = 100 N when m=2 kg and a=3 m/s²', dimensional check is happy
    (units balance) but the magnitude is wrong by ~17×. This check
    verifies the actual product.
    """
    name = "physics.newtons_second_law"
    m = spec.get("mass_kg")
    a = spec.get("acceleration_m_per_s2")
    F_claimed = spec.get("claimed_force_N")
    if m is None or a is None or F_claimed is None:
        return na(name)
    try:
        mf, af, Ff = float(m), float(a), float(F_claimed)
    except (TypeError, ValueError):
        return error(name, "mass_kg, acceleration_m_per_s2, and claimed_force_N must be numeric")
    actual_F = mf * af
    rel_tol = float(spec.get("rel_tol") or 1e-3)
    abs_tol = float(spec.get("abs_tol") or 1e-6)
    threshold = max(abs_tol, abs(actual_F) * rel_tol)
    diff = abs(actual_F - Ff)
    data = {
        "mass_kg": mf, "acceleration_m_per_s2": af,
        "actual_force_N": actual_F, "claimed_force_N": Ff,
        "diff": diff, "tol_abs": threshold,
        "formula": "F = m × a",
        "source": "Newton's second law (definition of force)",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"{mf} kg × {af} m/s² = {actual_F} N (claim {Ff} within ±{threshold:.3g})",
            data,
        )
    return mismatch(
        name,
        f"{mf} × {af} = {actual_F} N, claimed {Ff} N (diff {diff:.3g})",
        data,
    )


def verify_kinetic_energy_basic(spec: Dict[str, Any]) -> VerifierResult:
    """KE = ½ × m × v²  (magnitude check, SI units).

    Same pattern as F=ma: cover the magnitude version of a basic
    classical-mechanics identity. The `energy` verifier handles a
    similar check; this is here so claims classified as `physics`
    don't fall through.
    """
    name = "physics.kinetic_energy"
    m = spec.get("mass_kg")
    v = spec.get("velocity_m_per_s")
    KE_claimed = spec.get("claimed_kinetic_energy_J")
    if m is None or v is None or KE_claimed is None:
        return na(name)
    try:
        mf, vf, Kf = float(m), float(v), float(KE_claimed)
    except (TypeError, ValueError):
        return error(name, "mass_kg, velocity_m_per_s, claimed_kinetic_energy_J must be numeric")
    actual = 0.5 * mf * vf * vf
    rel_tol = float(spec.get("rel_tol") or 1e-3)
    abs_tol = float(spec.get("abs_tol") or 1e-6)
    threshold = max(abs_tol, abs(actual) * rel_tol)
    diff = abs(actual - Kf)
    data = {
        "mass_kg": mf, "velocity_m_per_s": vf,
        "actual_kinetic_energy_J": actual, "claimed_kinetic_energy_J": Kf,
        "diff": diff, "tol_abs": threshold,
        "formula": "KE = ½ m v²",
        "source": "classical mechanics (definition of kinetic energy)",
    }
    if diff <= threshold:
        return confirm(
            name,
            f"½ × {mf} × {vf}² = {actual} J (claim {Kf} within ±{threshold:.3g})",
            data,
        )
    return mismatch(
        name,
        f"½ × {mf} × {vf}² = {actual} J, claimed {Kf} J (diff {diff:.3g})",
        data,
    )


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

    if all(k in pv for k in ("v0", "a", "t", "claimed_displacement")):
        results.append(verify_kinematic_motion(pv))

    if "speed_m_per_s" in pv:
        results.append(verify_relativistic_speed_limit(pv))

    # Magnitude checks for everyday claims (F=ma, KE=½mv²)
    if all(k in pv for k in ("mass_kg", "acceleration_m_per_s2", "claimed_force_N")):
        results.append(verify_newtons_second_law(pv))
    if all(k in pv for k in ("mass_kg", "velocity_m_per_s", "claimed_kinetic_energy_J")):
        results.append(verify_kinetic_energy_basic(pv))

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
