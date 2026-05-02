"""Number theory verifier (formal-reasoning grid axis sibling to math + logic).

Primality, GCD, factorial, and modular inverse. All deterministic via
stdlib math; no external dependency.

Checks:
  * number_theory.primality       — claimed prime/composite matches
  * number_theory.gcd             — Euclid's algorithm
  * number_theory.factorial       — n! exact
  * number_theory.modular_inverse — a · inv ≡ 1 mod m

NUM_VERIFY shape (any subset):
    {
      "n_prime": 17, "claimed_prime": true,
      "gcd_a": 12, "gcd_b": 18, "claimed_gcd": 6,
      "factorial_n": 5, "claimed_factorial": 120,
      "mod_a": 3, "mod_m": 11, "claimed_inverse": 4,   # 3·4 = 12 ≡ 1 mod 11
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    r = int(math.isqrt(n))
    for i in range(3, r + 1, 2):
        if n % i == 0:
            return False
    return True


def verify_primality(spec: Dict[str, Any]) -> VerifierResult:
    name = "number_theory.primality"
    n = spec.get("n_prime")
    claimed = spec.get("claimed_prime")
    if n is None or claimed is None:
        return na(name)
    try:
        nf = int(n)
    except (TypeError, ValueError):
        return error(name, f"n_prime must be an integer, got {n!r}")
    if nf < 0:
        return error(name, "primality is defined for non-negative integers")
    actual = _is_prime(nf)
    data = {"n": nf, "actual_prime": actual, "claimed_prime": bool(claimed),
            "rule": "primality via trial division up to √n"}
    if actual == bool(claimed):
        return confirm(name, f"{nf} is{' ' if actual else ' NOT '}prime (matches claim)", data)
    return mismatch(name, f"{nf} is{' ' if actual else ' NOT '}prime, claimed {bool(claimed)}", data)


def verify_gcd(spec: Dict[str, Any]) -> VerifierResult:
    name = "number_theory.gcd"
    a = spec.get("gcd_a")
    b = spec.get("gcd_b")
    claimed = spec.get("claimed_gcd")
    if a is None or b is None or claimed is None:
        return na(name)
    try:
        af, bf, c = int(a), int(b), int(claimed)
    except (TypeError, ValueError):
        return error(name, "gcd inputs must be integers")
    actual = math.gcd(af, bf)
    data = {"a": af, "b": bf, "actual_gcd": actual, "claimed_gcd": c,
            "rule": "Euclidean algorithm (math.gcd)"}
    if actual == c:
        return confirm(name, f"gcd({af}, {bf}) = {actual} (matches claim)", data)
    return mismatch(name, f"gcd({af}, {bf}) = {actual}, claimed {c}", data)


def verify_factorial(spec: Dict[str, Any]) -> VerifierResult:
    name = "number_theory.factorial"
    n = spec.get("factorial_n")
    claimed = spec.get("claimed_factorial")
    if n is None or claimed is None:
        return na(name)
    try:
        nf = int(n)
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "factorial inputs must be integers")
    if nf < 0:
        return error(name, f"factorial undefined for negative n, got {nf}")
    if nf > 1000:
        return error(name, f"factorial input {nf} too large for this verifier")
    actual = math.factorial(nf)
    data = {"n": nf, "actual_factorial": actual, "claimed_factorial": c}
    if actual == c:
        return confirm(name, f"{nf}! = {actual} (matches claim)", data)
    return mismatch(name, f"{nf}! = {actual}, claimed {c}", data)


def verify_modular_inverse(spec: Dict[str, Any]) -> VerifierResult:
    """Verify a · claimed ≡ 1 (mod m). Inverse exists iff gcd(a, m) = 1."""
    name = "number_theory.modular_inverse"
    a = spec.get("mod_a")
    m = spec.get("mod_m")
    claimed = spec.get("claimed_inverse")
    if a is None or m is None or claimed is None:
        return na(name)
    try:
        af, mf, c = int(a), int(m), int(claimed)
    except (TypeError, ValueError):
        return error(name, "modular inverse inputs must be integers")
    if mf <= 1:
        return error(name, f"modulus must be >= 2, got {mf}")
    if math.gcd(af, mf) != 1:
        return mismatch(name,
                        f"gcd({af}, {mf}) = {math.gcd(af, mf)} ≠ 1; modular inverse does not exist",
                        {"a": af, "m": mf, "gcd": math.gcd(af, mf)})
    product_mod = (af * c) % mf
    actual_inverse = pow(af, -1, mf)
    data = {"a": af, "m": mf, "claimed_inverse": c,
            "actual_inverse": actual_inverse,
            "a_times_claimed_mod_m": product_mod,
            "rule": "a · inv ≡ 1 (mod m)"}
    if product_mod == 1:
        return confirm(name,
                       f"{af}·{c} mod {mf} = 1; {c} is the modular inverse",
                       data)
    return mismatch(name,
                    f"{af}·{c} mod {mf} = {product_mod} ≠ 1; correct inverse is {actual_inverse}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    nv = packet.get("NUM_VERIFY") or {}
    if "n_prime" in nv and "claimed_prime" in nv:
        results.append(verify_primality(nv))
    if all(k in nv for k in ("gcd_a", "gcd_b", "claimed_gcd")):
        results.append(verify_gcd(nv))
    if "factorial_n" in nv and "claimed_factorial" in nv:
        results.append(verify_factorial(nv))
    if all(k in nv for k in ("mod_a", "mod_m", "claimed_inverse")):
        results.append(verify_modular_inverse(nv))
    if not results:
        results.append(na("number_theory", "no NUM_VERIFY artifacts present"))
    return results
