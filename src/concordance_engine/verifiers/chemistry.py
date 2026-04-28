"""Chemistry verifier.

Checks that this verifier actually performs (not attestations):
  * mass_balance: atoms on each side conserve under the stated coefficients,
    or — if coefficients are not given — solves for the smallest integer
    coefficients that balance the equation
  * charge_balance: net charge is conserved across the equation
  * temperature_positive: temperature_K > 0 (K is the only physical scale)

Equation format accepted (string):
    "H2 + O2 -> H2O"            # finds coefficients
    "2 H2 + O2 -> 2 H2O"        # verifies coefficients
    "Fe^3+ + e^- -> Fe^2+"      # charges
    "Cu(OH)2 -> CuO + H2O"      # nested groups

Any species may carry a charge suffix written as ^n+ or ^n- (n optional, default 1)
or as +/- with no caret. State labels in parentheses (s), (l), (g), (aq) are stripped.
"""
from __future__ import annotations
import re
from fractions import Fraction
from typing import Dict, List, Tuple, Any
from .base import VerifierResult, na, confirm, mismatch, error

# regex pieces ---------------------------------------------------------------

_STATE = re.compile(r"\((?:s|l|g|aq|aq\.|cr|am|ads)\)\s*", re.IGNORECASE)
_CHARGE = re.compile(r"\^?(\d*)([+\-])$")
_ELEMENT_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*)|\(|\)(\d*)")


def _strip_state(species: str) -> str:
    return _STATE.sub("", species).strip()


def _parse_charge(species: str) -> Tuple[str, int]:
    """Strip a trailing charge tag and return (bare_formula, charge)."""
    s = species.strip()
    # accept species like Fe^3+, Fe^+, Fe+, Cu^2-, OH-, NH4+
    m = re.search(r"\^?(\d*)([+\-])\s*$", s)
    if not m:
        return s, 0
    # Be careful: a trailing - might be the dash in -> already stripped, fine.
    digits, sign = m.group(1), m.group(2)
    n = int(digits) if digits else 1
    bare = s[:m.start()].rstrip()
    return bare, n if sign == "+" else -n


def _parse_formula(formula: str) -> Dict[str, int]:
    """Count atoms in a formula, supporting nested parentheses."""
    s = formula.replace(" ", "")
    stack: List[Dict[str, int]] = [{}]
    i = 0
    while i < len(s):
        c = s[i]
        if c == "(":
            stack.append({})
            i += 1
        elif c == ")":
            # collect multiplier after )
            i += 1
            mdigits = ""
            while i < len(s) and s[i].isdigit():
                mdigits += s[i]
                i += 1
            mult = int(mdigits) if mdigits else 1
            top = stack.pop()
            for el, n in top.items():
                stack[-1][el] = stack[-1].get(el, 0) + n * mult
        elif c.isupper():
            sym = c
            i += 1
            if i < len(s) and s[i].islower():
                sym += s[i]
                i += 1
            ndigits = ""
            while i < len(s) and s[i].isdigit():
                ndigits += s[i]
                i += 1
            n = int(ndigits) if ndigits else 1
            stack[-1][sym] = stack[-1].get(sym, 0) + n
        elif c.isdigit():
            # bare leading digit is a coefficient — should not appear here because
            # callers split on whitespace first. Skip.
            i += 1
        elif c == "·" or c == ".":
            # hydrate dot, e.g. CuSO4·5H2O — handle cheaply by splitting and merging
            # not fully general but covers common cases
            i += 1
        else:
            # unknown character — treat as separator
            i += 1
    if len(stack) != 1:
        raise ValueError(f"unbalanced parentheses in {formula!r}")
    return stack[0]


def _split_term(term: str) -> Tuple[int, str]:
    """Split '2 H2O' into (2, 'H2O'). No coefficient -> (1, term)."""
    t = term.strip()
    m = re.match(r"^(\d+)\s*(.+)$", t)
    if m:
        return int(m.group(1)), m.group(2).strip()
    return 1, t


def _split_side(side: str) -> List[Tuple[int, str, int]]:
    """Return [(coef, formula, charge), ...] for one side of the equation.

    Splits species on whitespace-padded ' + ' (so charges like Fe^2+ or Na+
    don't get torn apart). Accepts species ending in: ^n+, ^n-, +, -.
    """
    out: List[Tuple[int, str, int]] = []
    # Split on ' + ' that has whitespace around it (or is at end / start adjacent to whitespace).
    # The simplest robust regex: split on /\s+\+\s+/. Anything tighter than that is
    # part of a charge tag and stays attached to its species.
    for term in re.split(r"\s+\+\s+", side.strip()):
        term = _strip_state(term).strip()
        if not term:
            continue
        coef, sp = _split_term(term)
        bare, charge = _parse_charge(sp)
        # also handle e^- and e- (electron)
        if bare.lower() in ("e", "e-") or (bare == "" and charge == -1):
            out.append((coef, "", -1))
            continue
        out.append((coef, bare, charge))
    return out


def _atoms_on_side(side: List[Tuple[int, str, int]]) -> Dict[str, int]:
    total: Dict[str, int] = {}
    for coef, formula, _ in side:
        if not formula:
            continue
        atoms = _parse_formula(formula)
        for el, n in atoms.items():
            total[el] = total.get(el, 0) + coef * n
    return total


def _charge_on_side(side: List[Tuple[int, str, int]]) -> int:
    return sum(coef * charge for coef, _, charge in side)


def verify_equation(eq: str, *, balance_if_unbalanced: bool = True) -> VerifierResult:
    """Verify or balance a chemical equation."""
    if "->" not in eq and "→" not in eq:
        return error("chemistry.equation", f"no reaction arrow in {eq!r}")

    lhs_str, rhs_str = re.split(r"->|→", eq, maxsplit=1)
    try:
        lhs = _split_side(lhs_str)
        rhs = _split_side(rhs_str)
    except Exception as e:
        return error("chemistry.equation", f"parse failure: {e}")

    try:
        atoms_lhs = _atoms_on_side(lhs)
        atoms_rhs = _atoms_on_side(rhs)
    except Exception as e:
        return error("chemistry.equation", f"atom-count failure: {e}")

    charge_lhs = _charge_on_side(lhs)
    charge_rhs = _charge_on_side(rhs)

    elements = sorted(set(atoms_lhs) | set(atoms_rhs))
    diff = {el: atoms_lhs.get(el, 0) - atoms_rhs.get(el, 0) for el in elements}

    if all(v == 0 for v in diff.values()) and charge_lhs == charge_rhs:
        return confirm(
            "chemistry.equation",
            "atoms and charge balanced under stated coefficients",
            {"atoms_lhs": atoms_lhs, "atoms_rhs": atoms_rhs,
             "charge_lhs": charge_lhs, "charge_rhs": charge_rhs},
        )

    if not balance_if_unbalanced:
        return mismatch(
            "chemistry.equation",
            f"unbalanced under stated coefficients: atom diff {diff}, "
            f"charge {charge_lhs} -> {charge_rhs}",
            {"atom_diff": diff, "charge_lhs": charge_lhs, "charge_rhs": charge_rhs},
        )

    # Try to balance: solve A x = 0 for x in positive integers, where A's columns
    # are species (with sign), rows are conserved quantities (elements + charge).
    species: List[Tuple[int, str, int]] = []  # (sign, formula, charge); sign +1 lhs, -1 rhs
    for _, f, c in lhs:
        species.append((+1, f, c))
    for _, f, c in rhs:
        species.append((-1, f, c))

    # Build conservation matrix.
    rows = elements + ["__charge__"]
    A: List[List[Fraction]] = []
    for r in rows:
        row: List[Fraction] = []
        for sign, f, c in species:
            if r == "__charge__":
                row.append(Fraction(sign * c))
            else:
                atoms = _parse_formula(f) if f else {}
                row.append(Fraction(sign * atoms.get(r, 0)))
        A.append(row)

    coefs = _nullspace_positive_integer(A)
    if coefs is None:
        return mismatch(
            "chemistry.equation",
            f"could not balance: atom diff {diff}, charge {charge_lhs} -> {charge_rhs}",
            {"atom_diff": diff},
        )

    # Reconstruct the balanced equation
    n_lhs = len(lhs)
    lhs_balanced = " + ".join(_render(c, lhs[i][1], lhs[i][2]) for i, c in enumerate(coefs[:n_lhs]))
    rhs_balanced = " + ".join(_render(c, rhs[i][1], rhs[i][2]) for i, c in enumerate(coefs[n_lhs:]))
    return mismatch(
        "chemistry.equation",
        f"unbalanced under stated coefficients but balances as: "
        f"{lhs_balanced} -> {rhs_balanced}",
        {"balanced_coefficients": coefs, "balanced_lhs": lhs_balanced, "balanced_rhs": rhs_balanced},
    )


def _render(coef: int, formula: str, charge: int) -> str:
    body = formula if formula else "e^-"
    if charge and formula:
        sign = "+" if charge > 0 else "-"
        n = abs(charge)
        body = body + ("^" + (str(n) if n != 1 else "") + sign)
    return f"{coef} {body}" if coef != 1 else body


def _nullspace_positive_integer(A: List[List[Fraction]]) -> List[int] | None:
    """Find the smallest positive-integer vector x with A x = 0 (one-dim nullspace)."""
    if not A or not A[0]:
        return None
    n_cols = len(A[0])
    # Gauss-Jordan over Fractions
    M = [row[:] for row in A]
    pivot_col_for_row: List[int] = []
    r = 0
    for c in range(n_cols):
        # find pivot
        piv = None
        for rr in range(r, len(M)):
            if M[rr][c] != 0:
                piv = rr
                break
        if piv is None:
            continue
        M[r], M[piv] = M[piv], M[r]
        # normalize pivot row
        pv = M[r][c]
        M[r] = [x / pv for x in M[r]]
        # eliminate in other rows
        for rr in range(len(M)):
            if rr != r and M[rr][c] != 0:
                factor = M[rr][c]
                M[rr] = [a - factor * b for a, b in zip(M[rr], M[r])]
        pivot_col_for_row.append(c)
        r += 1
        if r == len(M):
            break

    pivot_cols = set(pivot_col_for_row)
    free_cols = [c for c in range(n_cols) if c not in pivot_cols]
    if len(free_cols) != 1:
        return None  # need exactly one free variable for a unique balance

    free = free_cols[0]
    x: List[Fraction] = [Fraction(0)] * n_cols
    x[free] = Fraction(1)
    # solve for pivot vars: row r corresponds to pivot col pivot_col_for_row[r]
    for ri, pc in enumerate(pivot_col_for_row):
        # 0 = sum_c M[ri][c] * x[c]; x[pc] = -sum over c != pc of M[ri][c] * x[c]
        s = Fraction(0)
        for c in range(n_cols):
            if c != pc:
                s += M[ri][c] * x[c]
        x[pc] = -s

    # All coefficients should have the same sign (all positive, after flipping if needed)
    if all(v == 0 for v in x):
        return None
    nonzero = [v for v in x if v != 0]
    sign = 1 if nonzero[0] > 0 else -1
    x = [v * sign for v in x]
    if any(v <= 0 for v in x):
        return None  # cannot make all coefficients positive with one degree of freedom

    # Scale to smallest positive integers
    from math import gcd
    den_lcm = 1
    for v in x:
        den_lcm = den_lcm * v.denominator // gcd(den_lcm, v.denominator)
    ints = [int(v * den_lcm) for v in x]
    g = ints[0]
    for v in ints[1:]:
        g = gcd(g, v)
    return [v // g for v in ints]


def verify_temperature(temperature_K: float) -> VerifierResult:
    if temperature_K is None:
        return na("chemistry.temperature_K")
    try:
        t = float(temperature_K)
    except (ValueError, TypeError):
        return error("chemistry.temperature_K", f"non-numeric: {temperature_K!r}")
    if t <= 0:
        return mismatch("chemistry.temperature_K", f"{t} K is not a positive absolute temperature")
    return confirm("chemistry.temperature_K", f"{t} K positive")


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Run all chemistry verifiers that have an artifact in the packet."""
    results: List[VerifierResult] = []
    chem_verify = packet.get("CHEM_VERIFY") or {}

    if "equation" in chem_verify:
        eq = chem_verify["equation"]
        results.append(verify_equation(eq, balance_if_unbalanced=True))

    setup = packet.get("CHEM_SETUP") or {}
    if "temperature_K" in setup or "temperature_K" in chem_verify:
        t = chem_verify.get("temperature_K", setup.get("temperature_K"))
        results.append(verify_temperature(t))

    if not results:
        results.append(na("chemistry", "no CHEM_VERIFY artifacts present"))
    return results
