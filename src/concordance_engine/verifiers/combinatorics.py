"""Combinatorics verifier (formal-reasoning grid axis sibling to math, logic, number_theory).

Counting structures: permutations, combinations, derangements, multinomial.
Pure stdlib (math.factorial / math.perm / math.comb).

Checks:
  * combinatorics.permutations  — P(n,k) = n!/(n-k)!
  * combinatorics.combinations  — C(n,k) = n!/(k!(n-k)!)
  * combinatorics.derangements  — !n = n! · Σ_{i=0..n} (-1)^i / i!
  * combinatorics.multinomial   — n! / (n1! · n2! · ... · nk!), Σnᵢ = n

COMB_VERIFY shape (any subset):
    {
      "perm_n": 5, "perm_k": 2, "claimed_permutations": 20,
      "comb_n": 5, "comb_k": 2, "claimed_combinations": 10,
      "derangement_n": 4, "claimed_derangements": 9,
      "multinomial_groups": [2, 2, 1], "claimed_multinomial": 30,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _derangements(n: int) -> int:
    """!n via recurrence: !0=1, !1=0, !n = (n-1)·(!(n-1) + !(n-2))."""
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 1
    if n == 1:
        return 0
    a, b = 1, 0
    for k in range(2, n + 1):
        a, b = b, (k - 1) * (a + b)
    return b


def verify_permutations(spec: Dict[str, Any]) -> VerifierResult:
    name = "combinatorics.permutations"
    n = spec.get("perm_n")
    k = spec.get("perm_k")
    claimed = spec.get("claimed_permutations")
    if n is None or k is None or claimed is None:
        return na(name)
    try:
        nf, kf, c = int(n), int(k), int(claimed)
    except (TypeError, ValueError):
        return error(name, "permutation inputs must be integers")
    if nf < 0 or kf < 0:
        return error(name, "n and k must be non-negative")
    if kf > nf:
        return error(name, f"k ({kf}) cannot exceed n ({nf})")
    actual = math.perm(nf, kf)
    data = {"n": nf, "k": kf, "actual": actual, "claimed": c,
            "rule": "P(n,k) = n!/(n-k)!"}
    if actual == c:
        return confirm(name, f"P({nf},{kf}) = {actual} (matches claim)", data)
    return mismatch(name, f"P({nf},{kf}) = {actual}, claimed {c}", data)


def verify_combinations(spec: Dict[str, Any]) -> VerifierResult:
    name = "combinatorics.combinations"
    n = spec.get("comb_n")
    k = spec.get("comb_k")
    claimed = spec.get("claimed_combinations")
    if n is None or k is None or claimed is None:
        return na(name)
    try:
        nf, kf, c = int(n), int(k), int(claimed)
    except (TypeError, ValueError):
        return error(name, "combination inputs must be integers")
    if nf < 0 or kf < 0:
        return error(name, "n and k must be non-negative")
    if kf > nf:
        return error(name, f"k ({kf}) cannot exceed n ({nf})")
    actual = math.comb(nf, kf)
    data = {"n": nf, "k": kf, "actual": actual, "claimed": c,
            "rule": "C(n,k) = n!/(k!(n-k)!)"}
    if actual == c:
        return confirm(name, f"C({nf},{kf}) = {actual} (matches claim)", data)
    return mismatch(name, f"C({nf},{kf}) = {actual}, claimed {c}", data)


def verify_derangements(spec: Dict[str, Any]) -> VerifierResult:
    name = "combinatorics.derangements"
    n = spec.get("derangement_n")
    claimed = spec.get("claimed_derangements")
    if n is None or claimed is None:
        return na(name)
    try:
        nf, c = int(n), int(claimed)
    except (TypeError, ValueError):
        return error(name, "derangement inputs must be integers")
    if nf < 0:
        return error(name, f"n must be non-negative, got {nf}")
    if nf > 1000:
        return error(name, f"n ({nf}) too large for this verifier")
    actual = _derangements(nf)
    data = {"n": nf, "actual": actual, "claimed": c,
            "rule": "!n = (n-1)(!(n-1) + !(n-2)); !0=1, !1=0"}
    if actual == c:
        return confirm(name, f"!{nf} = {actual} (matches claim)", data)
    return mismatch(name, f"!{nf} = {actual}, claimed {c}", data)


def verify_multinomial(spec: Dict[str, Any]) -> VerifierResult:
    """n! / (n1! · n2! · ... · nk!) where Σnᵢ = n."""
    name = "combinatorics.multinomial"
    groups = spec.get("multinomial_groups")
    claimed = spec.get("claimed_multinomial")
    if groups is None or claimed is None:
        return na(name)
    if not isinstance(groups, list) or len(groups) == 0:
        return error(name, "multinomial_groups must be a non-empty list")
    try:
        gs = [int(g) for g in groups]
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "all group sizes and claimed value must be integers")
    if any(g < 0 for g in gs):
        return error(name, "group sizes must be non-negative")
    n = sum(gs)
    if n > 1000:
        return error(name, f"total n ({n}) too large for this verifier")
    denom = 1
    for g in gs:
        denom *= math.factorial(g)
    actual = math.factorial(n) // denom
    data = {"groups": gs, "n": n, "actual": actual, "claimed": c,
            "rule": "n! / (n1! · n2! · ... · nk!), Σnᵢ = n"}
    if actual == c:
        return confirm(name, f"multinomial({gs}) = {actual} (matches claim)", data)
    return mismatch(name, f"multinomial({gs}) = {actual}, claimed {c}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("COMB_VERIFY") or {}
    if all(k in cv for k in ("perm_n", "perm_k", "claimed_permutations")):
        results.append(verify_permutations(cv))
    if all(k in cv for k in ("comb_n", "comb_k", "claimed_combinations")):
        results.append(verify_combinations(cv))
    if "derangement_n" in cv and "claimed_derangements" in cv:
        results.append(verify_derangements(cv))
    if "multinomial_groups" in cv and "claimed_multinomial" in cv:
        results.append(verify_multinomial(cv))
    if not results:
        results.append(na("combinatorics", "no COMB_VERIFY artifacts present"))
    return results
