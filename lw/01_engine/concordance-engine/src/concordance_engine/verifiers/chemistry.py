"""
verifiers/chemistry.py — Chemical equation balancing and temperature checks.

Supports nested groups (Cu(OH)2), charges (Fe^2+, MnO4^-, Na+, Cl-),
coefficients, and auto-balancing via null-space solver.
"""
from __future__ import annotations
import re
from collections import defaultdict
from fractions import Fraction
from typing import Dict, List, Optional, Tuple
from .base import VerifierResult


def _parse_formula(formula: str) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    i, n = 0, len(formula)
    while i < n:
        ch = formula[i]
        if ch == "(":
            depth, j = 1, i + 1
            while j < n and depth > 0:
                if formula[j] == "(": depth += 1
                elif formula[j] == ")": depth -= 1
                j += 1
            inner = formula[i + 1:j - 1]
            k = j
            while k < n and formula[k].isdigit(): k += 1
            multiplier = int(formula[j:k]) if j < k else 1
            for el, cnt in _parse_formula(inner).items():
                counts[el] += cnt * multiplier
            i = k
        elif ch.isupper():
            j = i + 1
            while j < n and formula[j].islower(): j += 1
            element = formula[i:j]
            k = j
            while k < n and formula[k].isdigit(): k += 1
            counts[element] += int(formula[j:k]) if j < k else 1
            i = k
        else:
            i += 1
    return dict(counts)


def _parse_charge(token: str) -> Tuple[str, int]:
    token = token.strip()
    if "^" in token:
        idx = token.index("^")
        formula, charge_str = token[:idx], token[idx + 1:]
        if charge_str.endswith("+"):
            mag = charge_str[:-1]
            return formula, int(mag) if mag.isdigit() else 1
        elif charge_str.endswith("-"):
            mag = charge_str[:-1]
            return formula, -(int(mag) if mag.isdigit() else 1)
        return formula, 0
    # Simple trailing sign: Na+, Cl-, H+
    if token.endswith("+") and not token[-2:-1].isdigit():
        return token[:-1], +1
    if token.endswith("-") and not token[-2:-1].isdigit():
        return token[:-1], -1
    return token, 0


def _parse_side(side_str: str) -> List[Tuple[int, Dict[str, int], int]]:
    terms = []
    # Split on ' + ' (space-padded) so that + in charges (Fe^2+, Na+) is not consumed
    for term in re.split(r'\s+\+\s+', side_str.strip()):
        term = term.strip()
        if not term:
            continue
        m = re.match(r"^(\d+)\s+(.+)$", term)
        if m:
            coeff, species = int(m.group(1)), m.group(2).strip()
        else:
            m2 = re.match(r"^(\d+)([A-Z(].+)$", term)
            if m2:
                coeff, species = int(m2.group(1)), m2.group(2).strip()
            else:
                coeff, species = 1, term
        formula, charge = _parse_charge(species)
        terms.append((coeff, _parse_formula(formula), charge))
    return terms


def _side_totals(terms):
    totals: Dict[str, int] = defaultdict(int)
    total_charge = 0
    for coeff, counts, charge in terms:
        for el, cnt in counts.items():
            totals[el] += coeff * cnt
        total_charge += coeff * charge
    return dict(totals), total_charge


def _auto_balance(lhs_terms, rhs_terms):
    try:
        import numpy as np
        from math import gcd
        from functools import reduce
        elements, seen = [], set()
        for _, counts, _ in lhs_terms + rhs_terms:
            for el in counts:
                if el not in seen:
                    elements.append(el); seen.add(el)
        elements.append("__charge__")
        n_terms = len(lhs_terms) + len(rhs_terms)
        M = np.zeros((len(elements), n_terms), dtype=float)
        for j, (_, counts, charge) in enumerate(lhs_terms):
            for i, el in enumerate(elements[:-1]):
                M[i, j] = counts.get(el, 0)
            M[-1, j] = charge
        for j, (_, counts, charge) in enumerate(rhs_terms):
            col = len(lhs_terms) + j
            for i, el in enumerate(elements[:-1]):
                M[i, col] = -counts.get(el, 0)
            M[-1, col] = -charge
        _, s, Vt = np.linalg.svd(M)
        vec = Vt[-1]
        fracs = [Fraction(v).limit_denominator(1000) for v in vec]
        lcm_d = reduce(lambda a, b: a * b // gcd(a, b),
                       [f.denominator for f in fracs if f != 0], 1)
        ints = [int(f * lcm_d) for f in fracs]
        if any(x < 0 for x in ints):
            if sum(1 for x in ints if x < 0) > len(ints) / 2:
                ints = [-x for x in ints]
        g = reduce(gcd, [abs(x) for x in ints if x != 0], 1)
        ints = [x // g for x in ints]
        if any(x <= 0 for x in ints):
            return None
        return ints[:len(lhs_terms)], ints[len(lhs_terms):]
    except Exception:
        return None


def verify_equation(equation_str: str) -> VerifierResult:
    name = "chemistry.equation"
    eq = equation_str.strip()
    for arrow in ("->", "→", "⇌", "<->"):
        if arrow in eq:
            lhs_str, rhs_str = eq.split(arrow, 1)
            lhs_str, rhs_str = lhs_str.strip(), rhs_str.strip()
            break
    else:
        # Try '=' only if not '=' inside species
        if "=" in eq:
            lhs_str, rhs_str = eq.split("=", 1)
            lhs_str, rhs_str = lhs_str.strip(), rhs_str.strip()
        else:
            return VerifierResult(name=name, status="ERROR",
                                  detail=f"No reaction arrow in {equation_str!r}")

    lhs_orig = re.split(r'\s+\+\s+', lhs_str.strip())
    rhs_orig = re.split(r'\s+\+\s+', rhs_str.strip())

    try:
        lhs_terms = _parse_side(lhs_str)
        rhs_terms = _parse_side(rhs_str)
    except Exception as e:
        return VerifierResult(name=name, status="ERROR", detail=f"Parse error: {e}")

    lhs_tot, lhs_charge = _side_totals(lhs_terms)
    rhs_tot, rhs_charge = _side_totals(rhs_terms)

    all_els = sorted(set(lhs_tot) | set(rhs_tot))
    mismatches = []
    for el in all_els:
        l, r = lhs_tot.get(el, 0), rhs_tot.get(el, 0)
        if l != r:
            mismatches.append(f"{el}: LHS={l}, RHS={r}")
    if lhs_charge != rhs_charge:
        mismatches.append(f"charge: LHS={lhs_charge:+d}, RHS={rhs_charge:+d}")

    if not mismatches:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"Balanced: {equation_str}",
                              data={"balanced": True})

    data = {"balanced": False, "mismatches": mismatches}
    balanced = _auto_balance(lhs_terms, rhs_terms)
    if balanced:
        lhs_c, rhs_c = balanced
        balanced_lhs = " + ".join((f"{c} {o}" if c > 1 else o)
                                  for c, o in zip(lhs_c, lhs_orig))
        balanced_rhs = " + ".join((f"{c} {o}" if c > 1 else o)
                                  for c, o in zip(rhs_c, rhs_orig))
        data["balanced_lhs"] = balanced_lhs
        data["balanced_rhs"] = balanced_rhs
        detail = (f"Unbalanced: {', '.join(mismatches)}. "
                  f"Suggested: {balanced_lhs} -> {balanced_rhs}")
    else:
        detail = f"Unbalanced: {', '.join(mismatches)}"

    return VerifierResult(name=name, status="MISMATCH", detail=detail, data=data)


def verify_temperature(temp_K: float) -> VerifierResult:
    name = "chemistry.temperature"
    if float(temp_K) > 0:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"Temperature {temp_K} K is valid.",
                              data={"temperature_K": temp_K})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Temperature {temp_K} K is unphysical (must be > 0 K).",
                          data={"temperature_K": temp_K})


def run(packet: dict) -> list:
    results = []
    verify = packet.get("CHEM_VERIFY") or {}
    setup = packet.get("CHEM_SETUP") or {}
    if "equation" in verify:
        results.append(verify_equation(verify["equation"]))
    temp = verify.get("temperature_K") or setup.get("temperature_K")
    if temp is not None:
        results.append(verify_temperature(float(temp)))
    return results
