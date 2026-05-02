"""Information theory verifier (information/encoding grid axis — quartet
with genetics, cryptography, computer_science).

Shannon entropy, binary channel capacity, Hamming distance.
Public-domain: Shannon's foundational papers, generic IT textbooks.

Checks:
  * info_theory.shannon_entropy   — H(X) = -Σ p·log₂(p)
  * info_theory.bsc_capacity      — C = 1 - H₂(p) for a Binary Symmetric Channel
  * info_theory.hamming_distance  — count of differing positions in two equal-length strings

INFO_VERIFY shape (any subset):
    {
      "probabilities": [0.5, 0.5],
      "claimed_entropy_bits": 1.0,

      "bsc_error_rate": 0.1,
      "claimed_capacity_bits": 0.531,

      "string_a": "10101010",
      "string_b": "10100100",
      "claimed_hamming": 2,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _h2(p: float) -> float:
    """Binary entropy function H₂(p) in bits. H₂(0) = H₂(1) = 0."""
    if p in (0, 1):
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


def verify_shannon_entropy(spec: Dict[str, Any]) -> VerifierResult:
    name = "info_theory.shannon_entropy"
    probs = spec.get("probabilities")
    claimed = spec.get("claimed_entropy_bits")
    if probs is None or claimed is None:
        return na(name)
    if not isinstance(probs, (list, tuple)) or not probs:
        return error(name, "probabilities must be a non-empty list")
    try:
        ps = [float(p) for p in probs]
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "probabilities and claimed_entropy_bits must be numeric")
    if any(p < 0 for p in ps):
        return error(name, "probabilities cannot be negative")
    s = sum(ps)
    if abs(s - 1.0) > 1e-6:
        return error(name, f"probabilities must sum to 1, got {s}")
    actual = -sum(p * math.log2(p) for p in ps if p > 0)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-6))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual))
    data = {"probabilities": ps, "actual_entropy_bits": actual,
            "claimed_entropy_bits": c, "diff": diff,
            "formula": "H(X) = −Σ p·log₂(p)"}
    if diff <= threshold:
        return confirm(name,
                       f"H = {actual:.6f} bits (matches claim {c})",
                       data)
    return mismatch(name,
                    f"H = {actual:.6f} bits, claimed {c} (diff {diff:.6f})",
                    data)


def verify_bsc_capacity(spec: Dict[str, Any]) -> VerifierResult:
    """Binary Symmetric Channel: C = 1 − H₂(p) where p is the bit-flip rate."""
    name = "info_theory.bsc_capacity"
    p = spec.get("bsc_error_rate")
    claimed = spec.get("claimed_capacity_bits")
    if p is None or claimed is None:
        return na(name)
    try:
        pf = float(p)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "bsc_error_rate and claimed_capacity_bits must be numeric")
    if not (0 <= pf <= 1):
        return error(name, f"bit-flip rate must be in [0, 1], got {pf}")
    actual = 1.0 - _h2(pf)
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    abs_tol = float(spec.get("tolerance_absolute", 1e-3))
    diff = abs(actual - c)
    threshold = max(abs_tol, rel_tol * abs(actual))
    data = {"bsc_error_rate": pf, "actual_capacity_bits": actual,
            "claimed_capacity_bits": c, "diff": diff,
            "formula": "C = 1 − H₂(p)"}
    if diff <= threshold:
        return confirm(name,
                       f"C = 1 − H₂({pf}) = {actual:.4f} bits/use (matches claim {c})",
                       data)
    return mismatch(name,
                    f"C = {actual:.4f} bits/use, claimed {c} (diff {diff:.4f})",
                    data)


def verify_hamming_distance(spec: Dict[str, Any]) -> VerifierResult:
    """Hamming distance: count of positions at which two equal-length strings differ."""
    name = "info_theory.hamming_distance"
    a = spec.get("string_a")
    b = spec.get("string_b")
    claimed = spec.get("claimed_hamming")
    if a is None or b is None or claimed is None:
        return na(name)
    try:
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_hamming must be an integer, got {claimed!r}")
    if not isinstance(a, str) or not isinstance(b, str):
        return error(name, "string_a and string_b must be strings")
    if len(a) != len(b):
        return error(name, f"string lengths differ: {len(a)} vs {len(b)}")
    actual = sum(1 for xa, xb in zip(a, b) if xa != xb)
    data = {"string_a": a, "string_b": b, "length": len(a),
            "actual_hamming": actual, "claimed_hamming": c,
            "rule": "count of differing positions"}
    if actual == c:
        return confirm(name,
                       f"Hamming({a!r}, {b!r}) = {actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"Hamming({a!r}, {b!r}) = {actual}, claimed {c}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    iv = packet.get("INFO_VERIFY") or {}
    if "probabilities" in iv and "claimed_entropy_bits" in iv:
        results.append(verify_shannon_entropy(iv))
    if "bsc_error_rate" in iv and "claimed_capacity_bits" in iv:
        results.append(verify_bsc_capacity(iv))
    if all(k in iv for k in ("string_a", "string_b", "claimed_hamming")):
        results.append(verify_hamming_distance(iv))
    if not results:
        results.append(na("information_theory", "no INFO_VERIFY artifacts present"))
    return results
