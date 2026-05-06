"""Quantum computing verifier.

Domain: information_theory × physics umbrella (encoding/information + conservation axes).

All checks are closed-form — no quantum simulation required. Proofs about state
normalization, algorithm scaling, period arithmetic, and QKD security thresholds
are deterministic.

Checks performed:
  * qubit_normalization    |α|² + |β|² = 1 for single-qubit states; generalises to
                           n-qubit states via Σ|amplitude_i|² = 1.
  * grover_iterations      Optimal T = floor(π√N / 4). Verifies claimed iteration count.
  * shor_period            a^r ≡ 1 (mod N), r > 0, r is even (necessary for GCD step).
                           Optionally verifies that gcd(a^(r/2)±1, N) yields a non-trivial factor.
  * bb84_security          QBER < threshold (default 11%). Above threshold → channel
                           considered compromised.
  * von_neumann_entropy    S = −Σ λ_i log₂(λ_i) for the eigenvalues of a density
                           matrix ρ. Verifies claimed entropy in bits.
  * quantum_fidelity       F(|ψ⟩,|φ⟩) = |⟨ψ|φ⟩|² for pure states. Verifies claimed
                           fidelity given inner product.

QCOMP_VERIFY packet shape (any subset of fields):
    {
      "amplitudes": [0.6, 0.8],                         # qubit state amplitudes (real or complex)
      "claimed_normalized": true,

      "n_items": 64,                                    # Grover's database size
      "claimed_grover_iterations": 6,

      "shor_a": 2, "shor_N": 15, "shor_r": 4,          # Shor period verification
      "claimed_period_valid": true,

      "qber": 0.09,                                     # BB84 quantum bit error rate (0–1)
      "qber_threshold": 0.11,                           # default 0.11
      "claimed_secure": true,

      "density_eigenvalues": [0.5, 0.5],               # eigenvalues of density matrix
      "claimed_entropy_bits": 1.0,

      "inner_product": 0.707,                           # |⟨ψ|φ⟩|
      "claimed_fidelity": 0.5,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# ── qubit state normalization ────────────────────────────────────────────────

def verify_qubit_normalization(spec: Dict[str, Any]) -> VerifierResult:
    """Σ|amplitude_i|² = 1 (within tolerance)."""
    name = "quantum_computing.qubit_normalization"
    amps = spec.get("amplitudes")
    claimed = spec.get("claimed_normalized")
    if amps is None or claimed is None:
        return na(name)
    try:
        vals = [complex(a) for a in amps]
    except (TypeError, ValueError) as e:
        return error(name, f"amplitudes must be numeric: {e}")
    if not vals:
        return error(name, "amplitudes list is empty")
    norm_sq = sum(abs(a) ** 2 for a in vals)
    tol = float(spec.get("tolerance", 1e-6))
    is_normalized = abs(norm_sq - 1.0) <= tol
    data = {"n_amplitudes": len(vals), "norm_squared": norm_sq,
            "tolerance": tol, "is_normalized": is_normalized}
    if is_normalized == bool(claimed):
        verdict = "normalized" if is_normalized else "not normalized"
        return confirm(name,
                       f"Σ|aᵢ|² = {norm_sq:.8f} → state is {verdict} (matches claim)",
                       data)
    return mismatch(name,
                    f"Σ|aᵢ|² = {norm_sq:.8f} → normalized={is_normalized}, "
                    f"claimed={bool(claimed)}",
                    data)


# ── Grover's algorithm ────────────────────────────────────────────────────────

def verify_grover_iterations(spec: Dict[str, Any]) -> VerifierResult:
    """Optimal iterations T = floor(π√N / 4)."""
    name = "quantum_computing.grover_iterations"
    N = spec.get("n_items")
    claimed = spec.get("claimed_grover_iterations")
    if N is None or claimed is None:
        return na(name)
    try:
        n = int(N)
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, "n_items and claimed_grover_iterations must be integers")
    if n <= 0:
        return error(name, f"n_items must be positive, got {n}")
    optimal = math.floor(math.pi * math.sqrt(n) / 4)
    data = {"n_items": n, "optimal_iterations": optimal,
            "claimed_iterations": c, "formula": "T = floor(π√N/4)"}
    if c == optimal:
        return confirm(name,
                       f"N={n} → T = floor(π×{math.sqrt(n):.4f}/4) = {optimal} (matches claim)",
                       data)
    return mismatch(name,
                    f"N={n} → optimal T={optimal}, claimed {c}",
                    data)


# ── Shor's algorithm period verification ─────────────────────────────────────

def verify_shor_period(spec: Dict[str, Any]) -> VerifierResult:
    """a^r ≡ 1 (mod N), r > 0, r even. Optionally check non-trivial factor."""
    name = "quantum_computing.shor_period"
    a = spec.get("shor_a")
    N = spec.get("shor_N")
    r = spec.get("shor_r")
    claimed = spec.get("claimed_period_valid")
    if a is None or N is None or r is None or claimed is None:
        return na(name)
    try:
        ai, Ni, ri = int(a), int(N), int(r)
    except (TypeError, ValueError):
        return error(name, "shor_a, shor_N, shor_r must be integers")
    if Ni < 2:
        return error(name, f"N must be ≥ 2, got {Ni}")
    if ri <= 0:
        failures = [f"r={ri} must be > 0"]
        data = {"a": ai, "N": Ni, "r": ri, "failures": failures}
        valid = False
    else:
        failures = []
        remainder = pow(ai, ri, Ni)
        if remainder != 1:
            failures.append(f"a^r mod N = {ai}^{ri} mod {Ni} = {remainder} ≠ 1")
        if ri % 2 != 0:
            failures.append(f"r={ri} is odd (Shor's GCD step requires even period)")
        valid = len(failures) == 0
        # Optionally compute factors if r is valid
        factors = {}
        if valid:
            half = ri // 2
            f1 = math.gcd(pow(ai, half, Ni) - 1, Ni)
            f2 = math.gcd(pow(ai, half, Ni) + 1, Ni)
            factors = {"gcd(a^(r/2)-1, N)": f1, "gcd(a^(r/2)+1, N)": f2,
                       "non_trivial": (1 < f1 < Ni) or (1 < f2 < Ni)}
        data = {"a": ai, "N": Ni, "r": ri,
                "a_pow_r_mod_N": pow(ai, ri, Ni) if ri > 0 else None,
                "failures": failures, **factors}
    if valid == bool(claimed):
        msg = f"a={ai}, N={Ni}, r={ri}: period valid" if valid else f"failures: {failures}"
        return confirm(name, f"{msg} (matches claim {claimed})", data)
    return mismatch(name,
                    f"period valid={valid}, claimed={bool(claimed)}; "
                    f"failures: {failures}",
                    data)


# ── BB84 quantum key distribution ────────────────────────────────────────────

def verify_bb84_security(spec: Dict[str, Any]) -> VerifierResult:
    """QBER < threshold (default 11%) → channel considered secure."""
    name = "quantum_computing.bb84_security"
    qber = spec.get("qber")
    claimed = spec.get("claimed_secure")
    if qber is None or claimed is None:
        return na(name)
    try:
        q = float(qber)
        c = bool(claimed)
    except (TypeError, ValueError):
        return error(name, "qber must be numeric")
    if not (0.0 <= q <= 1.0):
        return error(name, f"qber must be in [0, 1], got {q}")
    threshold = float(spec.get("qber_threshold", 0.11))
    is_secure = q < threshold
    data = {"qber": q, "threshold": threshold, "is_secure": is_secure,
            "note": "BB84 security threshold: QBER < 11% (Shor & Preskill 2000)"}
    if is_secure == c:
        status = "secure" if is_secure else "compromised"
        return confirm(name,
                       f"QBER={q:.1%} {'<' if is_secure else '>='} threshold={threshold:.1%} "
                       f"→ {status} (matches claim)",
                       data)
    return mismatch(name,
                    f"QBER={q:.1%}, threshold={threshold:.1%} → secure={is_secure}, "
                    f"claimed={c}",
                    data)


# ── von Neumann entropy ───────────────────────────────────────────────────────

def verify_von_neumann_entropy(spec: Dict[str, Any]) -> VerifierResult:
    """S(ρ) = −Σ λᵢ log₂(λᵢ) in bits."""
    name = "quantum_computing.von_neumann_entropy"
    eigs = spec.get("density_eigenvalues")
    claimed = spec.get("claimed_entropy_bits")
    if eigs is None or claimed is None:
        return na(name)
    try:
        lambdas = [float(e) for e in eigs]
        c = float(claimed)
    except (TypeError, ValueError) as ex:
        return error(name, f"eigenvalues and claimed_entropy_bits must be numeric: {ex}")
    if not lambdas:
        return error(name, "density_eigenvalues list is empty")
    if any(lam < -1e-9 for lam in lambdas):
        return error(name, f"eigenvalues must be non-negative; got {lambdas}")
    total = sum(lambdas)
    if abs(total - 1.0) > 1e-4:
        return error(name, f"eigenvalues must sum to 1, got {total:.6f}")
    entropy = -sum(lam * math.log2(lam) for lam in lambdas if lam > 1e-15)
    tol = float(spec.get("tolerance_bits", 0.005))
    diff = abs(entropy - c)
    data = {"eigenvalues": lambdas, "computed_entropy_bits": entropy,
            "claimed_entropy_bits": c, "diff_bits": diff, "tolerance_bits": tol}
    if diff <= tol:
        return confirm(name,
                       f"S = −Σλlog₂λ = {entropy:.6f} bits (matches claim {c}, diff {diff:.6f})",
                       data)
    return mismatch(name,
                    f"S = {entropy:.6f} bits, claimed {c} (diff {diff:.6f} > tol {tol})",
                    data)


# ── quantum fidelity ──────────────────────────────────────────────────────────

def verify_quantum_fidelity(spec: Dict[str, Any]) -> VerifierResult:
    """F(|ψ⟩,|φ⟩) = |⟨ψ|φ⟩|² for pure states."""
    name = "quantum_computing.quantum_fidelity"
    ip = spec.get("inner_product")
    claimed = spec.get("claimed_fidelity")
    if ip is None or claimed is None:
        return na(name)
    try:
        ip_v = complex(ip)
        c = float(claimed)
    except (TypeError, ValueError) as ex:
        return error(name, f"inner_product and claimed_fidelity must be numeric: {ex}")
    fidelity = abs(ip_v) ** 2
    tol = float(spec.get("tolerance", 1e-4))
    diff = abs(fidelity - c)
    data = {"inner_product": str(ip_v), "computed_fidelity": fidelity,
            "claimed_fidelity": c, "diff": diff}
    if diff <= tol:
        return confirm(name,
                       f"F = |⟨ψ|φ⟩|² = |{ip_v}|² = {fidelity:.6f} (matches claim {c})",
                       data)
    return mismatch(name,
                    f"F = {fidelity:.6f}, claimed {c} (diff {diff:.6f} > tol {tol})",
                    data)


# ── runner ────────────────────────────────────────────────────────────────────

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    qv = packet.get("QCOMP_VERIFY") or {}

    if "amplitudes" in qv and "claimed_normalized" in qv:
        results.append(verify_qubit_normalization(qv))
    if "n_items" in qv and "claimed_grover_iterations" in qv:
        results.append(verify_grover_iterations(qv))
    if all(k in qv for k in ("shor_a", "shor_N", "shor_r", "claimed_period_valid")):
        results.append(verify_shor_period(qv))
    if "qber" in qv and "claimed_secure" in qv:
        results.append(verify_bb84_security(qv))
    if "density_eigenvalues" in qv and "claimed_entropy_bits" in qv:
        results.append(verify_von_neumann_entropy(qv))
    if "inner_product" in qv and "claimed_fidelity" in qv:
        results.append(verify_quantum_fidelity(qv))

    if not results:
        results.append(na("quantum_computing", "no QCOMP_VERIFY artifacts present"))
    return results
