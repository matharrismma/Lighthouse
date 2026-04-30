"""
verifiers/physics.py — Dimensional consistency and conservation arithmetic.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
from .base import VerifierResult


# SI unit expressions: name → pint-compatible string (we use sympy.physics.units instead)
_UNIT_ALIASES = {
    "newton": "kilogram * meter / second**2",
    "joule": "kilogram * meter**2 / second**2",
    "watt": "kilogram * meter**2 / second**3",
    "pascal": "kilogram / (meter * second**2)",
    "hertz": "1 / second",
    "coulomb": "ampere * second",
    "volt": "kilogram * meter**2 / (ampere * second**3)",
    "tesla": "kilogram / (ampere * second**2)",
    "weber": "kilogram * meter**2 / (ampere * second**2)",
    "henry": "kilogram * meter**2 / (ampere**2 * second**2)",
    "farad": "ampere**2 * second**4 / (kilogram * meter**2)",
    "ohm": "kilogram * meter**2 / (ampere**2 * second**3)",
    "siemens": "ampere**2 * second**3 / (kilogram * meter**2)",
    "lux": "candela / meter**2",
    "lumen": "candela",
    "becquerel": "1 / second",
    "gray": "meter**2 / second**2",
    "sievert": "meter**2 / second**2",
    "katal": "mol / second",
    # convenience
    "meter": "meter",
    "kilogram": "kilogram",
    "second": "second",
    "ampere": "ampere",
    "kelvin": "kelvin",
    "mol": "mol",
    "candela": "candela",
    "gram": "kilogram / 1000",   # not clean, skip for dim analysis
}

# Base SI dimensions (symbolic)
_BASE = ["kilogram", "meter", "second", "ampere", "kelvin", "mol", "candela"]


def _unit_to_dims(unit_expr: str) -> Optional[Dict[str, int]]:
    """
    Convert a unit expression string to a dimensional exponent dict.
    e.g. "kilogram * meter / second**2" → {kg:1, m:1, s:-2}
    Returns None on failure.
    """
    try:
        import sympy as sp
        # Expand aliases
        expr = unit_expr.strip()
        for alias, expansion in _UNIT_ALIASES.items():
            # whole-word replacement
            import re
            expr = re.sub(r"\b" + alias + r"\b", f"({expansion})", expr)

        # Build symbol map for base units
        syms = {b: sp.Symbol(b) for b in _BASE}
        # Add "1" for dimensionless
        syms["1"] = sp.Integer(1)

        result = sp.sympify(expr, locals=syms)
        result = sp.expand(sp.powsimp(result, force=True))

        dims = {}
        # Extract exponents for each base symbol
        for base, sym in syms.items():
            if base == "1":
                continue
            exp = result.as_powers_dict().get(sym, 0)
            if exp != 0:
                dims[base] = int(exp)
        return dims
    except Exception:
        return None


def verify_dimensional_consistency(equation: str, symbols: Dict[str, str]) -> VerifierResult:
    """
    Check that both sides of a physics equation have the same SI dimensions.
    """
    name = "physics.dimensional_consistency"
    try:
        import sympy as sp

        # Split on '='
        if "=" not in equation:
            return VerifierResult(name=name, status="ERROR",
                                  detail=f"No '=' in equation: {equation!r}")

        lhs_str, rhs_str = equation.split("=", 1)
        lhs_str = lhs_str.strip()
        rhs_str = rhs_str.strip()

        # Map each symbol to its dimensional representation
        sym_map = {}
        for sym_name, unit_str in symbols.items():
            # Expand the unit_str into a sympy expression of base dims
            dims = _unit_to_dims(unit_str)
            if dims is None:
                return VerifierResult(name=name, status="ERROR",
                                      detail=f"Cannot parse unit for '{sym_name}': {unit_str!r}")
            # Build sympy expression for this symbol's dimensions
            base_syms = {b: sp.Symbol(b) for b in _BASE}
            dim_expr = sp.Integer(1)
            for base, exp in dims.items():
                dim_expr *= base_syms[base] ** exp
            sym_map[sym_name] = dim_expr

        # Evaluate both sides dimensionally
        lhs_expr = sp.sympify(lhs_str, locals=sym_map)
        rhs_expr = sp.sympify(rhs_str, locals=sym_map)

        lhs_dims = sp.expand(sp.powsimp(lhs_expr, force=True))
        rhs_dims = sp.expand(sp.powsimp(rhs_expr, force=True))

        diff = sp.simplify(lhs_dims - rhs_dims)

        # Also accept if lhs/rhs differs only by a numeric constant (e.g. KE = m*v^2/2)
        if diff == 0:
            is_consistent = True
        else:
            try:
                ratio = sp.simplify(lhs_dims / rhs_dims)
                is_consistent = ratio.is_number
            except Exception:
                is_consistent = False

        if is_consistent:
            return VerifierResult(
                name=name, status="CONFIRMED",
                detail=f"Dimensionally consistent. LHS: {lhs_dims}, RHS: {rhs_dims}",
                data={"lhs_units": str(lhs_dims), "rhs_units": str(rhs_dims)}
            )
        else:
            return VerifierResult(
                name=name, status="MISMATCH",
                detail=f"Dimensional mismatch. LHS={lhs_dims}, RHS={rhs_dims}",
                data={"lhs_units": str(lhs_dims), "rhs_units": str(rhs_dims)}
            )
    except Exception as e:
        return VerifierResult(name=name, status="ERROR",
                              detail=f"Dimensional check failed: {e}")


def verify_conservation(before: Dict[str, float], after: Dict[str, float],
                        tolerance_relative: float = 1e-6) -> VerifierResult:
    """
    Check that all quantities in 'before' are conserved to within tolerance in 'after'.
    """
    name = "physics.conservation"
    failures = []
    for qty, val_before in before.items():
        val_after = after.get(qty, 0.0)
        if abs(val_before) > 0:
            rel_diff = abs(val_after - val_before) / abs(val_before)
        else:
            rel_diff = abs(val_after - val_before)
        if rel_diff > tolerance_relative:
            failures.append(f"{qty}: before={val_before}, after={val_after}, "
                            f"rel_diff={rel_diff:.3e} > tol={tolerance_relative:.3e}")

    if not failures:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="All conservation laws satisfied within tolerance.",
                              data={"before": before, "after": after})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Conservation violated: {'; '.join(failures)}",
                          data={"before": before, "after": after, "failures": failures})


def run(packet: dict) -> list:
    results = []
    verify = packet.get("PHYS_VERIFY") or {}
    if "equation" in verify and "symbols" in verify:
        results.append(verify_dimensional_consistency(verify["equation"], verify["symbols"]))
    if "before" in verify and "after" in verify:
        results.append(verify_conservation(verify["before"], verify["after"]))
    return results
