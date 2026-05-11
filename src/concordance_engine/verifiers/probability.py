"""Probability verifier.

Common probability and distribution claims, all computed
deterministically. The engine doesn't take anyone's word on what a
probability "should" be — it runs the math.

Checks:
  * probability.expected_value         — E[X] = Σ pᵢ xᵢ  (discrete)
  * probability.variance               — Var(X) = E[X²] - (E[X])²
  * probability.binomial               — P(X=k) for X ~ Binom(n,p)
  * probability.binomial_mean          — E[Binom(n,p)] = n p
  * probability.normal_cdf             — P(X ≤ x) for X ~ N(μ,σ)
  * probability.normal_within_std      — P(|X-μ| ≤ k σ) ≈ {68.27, 95.45, 99.73}%
  * probability.poisson                — P(X=k) for X ~ Poisson(λ)
  * probability.bayes                  — P(A|B) = P(B|A) P(A) / P(B)
  * probability.conditional            — P(A|B) = P(A∩B) / P(B)
  * probability.independence           — verify independence: P(A∩B) = P(A) P(B)

PROB_VERIFY shape (each check fires when its keys are present):

    # Discrete distributions
    {"outcomes": [1,2,3,4,5,6],
     "probabilities": [1/6]*6,
     "claimed_expected_value": 3.5}

    {"outcomes": [1,2,3,4,5,6],
     "probabilities": [1/6]*6,
     "claimed_variance": 2.91666667}

    # Binomial
    {"binomial_n": 10, "binomial_p": 0.5, "binomial_k": 5,
     "claimed_binomial_probability": 0.24609375}
    {"binomial_n": 100, "binomial_p": 0.3, "claimed_binomial_mean": 30}

    # Normal
    {"normal_mu": 0, "normal_sigma": 1, "normal_x": 1.96,
     "claimed_normal_cdf": 0.975}
    {"k_std": 1, "claimed_normal_within_std": 0.6827}

    # Poisson
    {"poisson_lambda": 3, "poisson_k": 2,
     "claimed_poisson_probability": 0.224}

    # Bayes
    {"p_a": 0.01, "p_b_given_a": 0.99, "p_b_given_not_a": 0.05,
     "claimed_p_a_given_b": 0.167}

    # Conditional probability
    {"p_a_and_b": 0.2, "p_b": 0.5,
     "claimed_p_a_given_b": 0.4}

    # Independence check
    {"p_a": 0.3, "p_b": 0.4, "p_a_and_b": 0.12,
     "claimed_independent": true}
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


def _close(a: float, b: float, rel: float = 1e-4, abs_: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_, rel * max(abs(a), abs(b)))


# ── Discrete distribution checks ────────────────────────────────────────

def _validate_discrete(outcomes: Any, probs: Any) -> Optional[str]:
    """Return None if the (outcomes, probabilities) pair is valid,
    else a human-readable error."""
    if not isinstance(outcomes, list) or not isinstance(probs, list):
        return "outcomes and probabilities must be lists"
    if len(outcomes) != len(probs):
        return f"outcomes and probabilities must have same length ({len(outcomes)} vs {len(probs)})"
    try:
        p = [float(x) for x in probs]
        _ = [float(x) for x in outcomes]
    except (TypeError, ValueError):
        return "outcomes and probabilities must be numeric"
    if any(pi < 0 for pi in p):
        return "negative probability"
    total = sum(p)
    if not _close(total, 1.0, rel=1e-3, abs_=1e-6):
        return f"probabilities sum to {total}, not 1"
    return None


def verify_expected_value(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.expected_value"
    outcomes = spec.get("outcomes")
    probs = spec.get("probabilities")
    claimed = spec.get("claimed_expected_value")
    if outcomes is None or probs is None or claimed is None:
        return na(name)
    err = _validate_discrete(outcomes, probs)
    if err:
        return error(name, err)
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_expected_value must be numeric")
    actual = sum(float(x) * float(p) for x, p in zip(outcomes, probs))
    data = {"outcomes": outcomes, "probabilities": probs,
            "actual_expected_value": actual, "claimed_expected_value": cl,
            "formula": "E[X] = Σ pᵢ xᵢ"}
    if _close(actual, cl):
        return confirm(name, f"E[X] = {actual:.6g}", data)
    return mismatch(name, f"E[X] = {actual:.6g}, claimed {cl}", data)


def verify_variance(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.variance"
    outcomes = spec.get("outcomes")
    probs = spec.get("probabilities")
    claimed = spec.get("claimed_variance")
    if outcomes is None or probs is None or claimed is None:
        return na(name)
    err = _validate_discrete(outcomes, probs)
    if err:
        return error(name, err)
    try:
        cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "claimed_variance must be numeric")
    mean = sum(float(x) * float(p) for x, p in zip(outcomes, probs))
    actual = sum(float(p) * (float(x) - mean) ** 2 for x, p in zip(outcomes, probs))
    data = {"outcomes": outcomes, "probabilities": probs,
            "mean": mean,
            "actual_variance": actual, "claimed_variance": cl,
            "formula": "Var(X) = Σ pᵢ (xᵢ - μ)²"}
    if _close(actual, cl):
        return confirm(name, f"Var(X) = {actual:.6g}", data)
    return mismatch(name, f"Var(X) = {actual:.6g}, claimed {cl}", data)


# ── Binomial ────────────────────────────────────────────────────────────

def verify_binomial_probability(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.binomial"
    n = spec.get("binomial_n")
    p = spec.get("binomial_p")
    k = spec.get("binomial_k")
    claimed = spec.get("claimed_binomial_probability")
    if n is None or p is None or k is None or claimed is None:
        return na(name)
    try:
        nf, kf = int(n), int(k)
        pf, cl = float(p), float(claimed)
    except (TypeError, ValueError):
        return error(name, "binomial inputs must be numeric (n,k int; p,claimed float)")
    if not (0 <= pf <= 1):
        return error(name, f"p must be in [0,1], got {pf}")
    if not (0 <= kf <= nf):
        return error(name, f"k={kf} must be in [0, n={nf}]")
    actual = math.comb(nf, kf) * (pf ** kf) * ((1 - pf) ** (nf - kf))
    data = {"n": nf, "p": pf, "k": kf,
            "actual_probability": actual, "claimed_probability": cl,
            "formula": "P(X=k) = C(n,k) pᵏ (1-p)ⁿ⁻ᵏ"}
    if _close(actual, cl, rel=1e-3, abs_=1e-6):
        return confirm(name, f"P(X={kf} | n={nf}, p={pf}) = {actual:.6g}", data)
    return mismatch(name, f"actual {actual:.6g}, claimed {cl}", data)


def verify_binomial_mean(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.binomial_mean"
    n = spec.get("binomial_n")
    p = spec.get("binomial_p")
    claimed = spec.get("claimed_binomial_mean")
    if n is None or p is None or claimed is None:
        return na(name)
    try:
        nf = int(n); pf = float(p); cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "n, p, claimed_binomial_mean must be numeric")
    actual = nf * pf
    data = {"n": nf, "p": pf,
            "actual_mean": actual, "claimed_mean": cl,
            "formula": "E[Binom(n,p)] = n p"}
    if _close(actual, cl):
        return confirm(name, f"E[Binom({nf},{pf})] = {actual}", data)
    return mismatch(name, f"actual {actual}, claimed {cl}", data)


# ── Normal distribution ────────────────────────────────────────────────

def _normal_cdf(x: float, mu: float = 0.0, sigma: float = 1.0) -> float:
    """Φ via the error function (stdlib)."""
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    z = (x - mu) / sigma
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def verify_normal_cdf(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.normal_cdf"
    mu = spec.get("normal_mu")
    sigma = spec.get("normal_sigma")
    x = spec.get("normal_x")
    claimed = spec.get("claimed_normal_cdf")
    if mu is None or sigma is None or x is None or claimed is None:
        return na(name)
    try:
        muf, sf, xf, cl = float(mu), float(sigma), float(x), float(claimed)
    except (TypeError, ValueError):
        return error(name, "mu, sigma, x, claimed_normal_cdf must be numeric")
    if sf <= 0:
        return error(name, f"sigma must be positive, got {sf}")
    actual = _normal_cdf(xf, muf, sf)
    data = {"mu": muf, "sigma": sf, "x": xf,
            "actual_cdf": actual, "claimed_cdf": cl,
            "formula": "Φ((x-μ)/σ) — standard normal CDF via erf"}
    if _close(actual, cl, rel=1e-3, abs_=1e-4):
        return confirm(name, f"P(X≤{xf} | N({muf},{sf})) = {actual:.6f}", data)
    return mismatch(name, f"actual {actual:.6f}, claimed {cl}", data)


def verify_normal_within_std(spec: Dict[str, Any]) -> VerifierResult:
    """68-95-99.7 rule: fraction of normal distribution within k σ of mean."""
    name = "probability.normal_within_std"
    k = spec.get("k_std")
    claimed = spec.get("claimed_normal_within_std")
    if k is None or claimed is None:
        return na(name)
    try:
        kf = float(k); cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "k_std and claimed_normal_within_std must be numeric")
    if kf <= 0:
        return error(name, f"k_std must be positive, got {kf}")
    actual = _normal_cdf(kf) - _normal_cdf(-kf)
    data = {"k_std": kf,
            "actual_fraction": actual, "claimed_fraction": cl,
            "formula": "P(|Z| ≤ k) = Φ(k) - Φ(-k)"}
    # Allow looser tolerance because users often quote "68%" / "95%" / "99.7%" rounded
    if _close(actual, cl, rel=5e-3, abs_=5e-3):
        return confirm(name, f"P(|X-μ| ≤ {kf}σ) = {actual:.4f}", data)
    return mismatch(name, f"actual {actual:.4f}, claimed {cl}", data)


# ── Poisson ─────────────────────────────────────────────────────────────

def verify_poisson_probability(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.poisson"
    lam = spec.get("poisson_lambda")
    k = spec.get("poisson_k")
    claimed = spec.get("claimed_poisson_probability")
    if lam is None or k is None or claimed is None:
        return na(name)
    try:
        lf = float(lam); kf = int(k); cl = float(claimed)
    except (TypeError, ValueError):
        return error(name, "lambda, k, claimed_poisson_probability must be numeric")
    if lf < 0:
        return error(name, f"lambda must be non-negative, got {lf}")
    if kf < 0:
        return error(name, f"k must be non-negative, got {kf}")
    actual = math.exp(-lf) * (lf ** kf) / math.factorial(kf)
    data = {"lambda": lf, "k": kf,
            "actual_probability": actual, "claimed_probability": cl,
            "formula": "P(X=k) = e^(-λ) λᵏ / k!"}
    if _close(actual, cl, rel=1e-3, abs_=1e-5):
        return confirm(name, f"P(X={kf} | λ={lf}) = {actual:.6g}", data)
    return mismatch(name, f"actual {actual:.6g}, claimed {cl}", data)


# ── Bayes ───────────────────────────────────────────────────────────────

def verify_bayes(spec: Dict[str, Any]) -> VerifierResult:
    """P(A|B) = P(B|A) P(A) / P(B), where P(B) = P(B|A) P(A) + P(B|¬A) P(¬A)."""
    name = "probability.bayes"
    pa = spec.get("p_a")
    pba = spec.get("p_b_given_a")
    pbna = spec.get("p_b_given_not_a")
    claimed = spec.get("claimed_p_a_given_b")
    if pa is None or pba is None or pbna is None or claimed is None:
        return na(name)
    try:
        pa_, pba_, pbna_, cl = float(pa), float(pba), float(pbna), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all Bayes inputs must be numeric")
    if not (0 <= pa_ <= 1 and 0 <= pba_ <= 1 and 0 <= pbna_ <= 1):
        return error(name, "all probabilities must be in [0,1]")
    p_b = pba_ * pa_ + pbna_ * (1 - pa_)
    if p_b == 0:
        return error(name, "P(B) = 0, conditional undefined")
    actual = pba_ * pa_ / p_b
    data = {"p_a": pa_, "p_b_given_a": pba_, "p_b_given_not_a": pbna_,
            "p_b": p_b,
            "actual_p_a_given_b": actual, "claimed_p_a_given_b": cl,
            "formula": "P(A|B) = P(B|A) P(A) / (P(B|A) P(A) + P(B|¬A) P(¬A))"}
    if _close(actual, cl, rel=1e-3, abs_=1e-4):
        return confirm(name, f"P(A|B) = {actual:.6f}", data)
    return mismatch(name, f"actual {actual:.6f}, claimed {cl}", data)


def verify_conditional_probability(spec: Dict[str, Any]) -> VerifierResult:
    name = "probability.conditional"
    p_ab = spec.get("p_a_and_b")
    p_b = spec.get("p_b")
    claimed = spec.get("claimed_p_a_given_b")
    if p_ab is None or p_b is None or claimed is None:
        return na(name)
    try:
        pab, pb, cl = float(p_ab), float(p_b), float(claimed)
    except (TypeError, ValueError):
        return error(name, "p_a_and_b, p_b, claimed_p_a_given_b must be numeric")
    if pb == 0:
        return error(name, "P(B) = 0, conditional undefined")
    if not (0 <= pab <= 1 and 0 <= pb <= 1):
        return error(name, "probabilities must be in [0,1]")
    if pab > pb + 1e-9:
        return error(name, f"P(A∩B) cannot exceed P(B); got {pab} > {pb}")
    actual = pab / pb
    data = {"p_a_and_b": pab, "p_b": pb,
            "actual_p_a_given_b": actual, "claimed_p_a_given_b": cl,
            "formula": "P(A|B) = P(A∩B) / P(B)"}
    if _close(actual, cl, rel=1e-3, abs_=1e-4):
        return confirm(name, f"P(A|B) = {actual:.6f}", data)
    return mismatch(name, f"actual {actual:.6f}, claimed {cl}", data)


def verify_independence(spec: Dict[str, Any]) -> VerifierResult:
    """A and B are independent iff P(A∩B) = P(A) P(B)."""
    name = "probability.independence"
    pa = spec.get("p_a")
    pb = spec.get("p_b")
    pab = spec.get("p_a_and_b")
    claimed = spec.get("claimed_independent")
    if pa is None or pb is None or pab is None or claimed is None:
        return na(name)
    try:
        pa_, pb_, pab_ = float(pa), float(pb), float(pab)
    except (TypeError, ValueError):
        return error(name, "p_a, p_b, p_a_and_b must be numeric")
    cl = bool(claimed)
    product = pa_ * pb_
    is_indep = _close(pab_, product, rel=1e-3, abs_=1e-4)
    data = {"p_a": pa_, "p_b": pb_, "p_a_and_b": pab_,
            "p_a_times_p_b": product,
            "actual_independent": is_indep, "claimed_independent": cl,
            "formula": "A ⊥ B ⟺ P(A∩B) = P(A) P(B)"}
    if is_indep == cl:
        return confirm(name, f"independence={is_indep} (matches claim)", data)
    return mismatch(name, f"actual independence={is_indep}, claimed {cl}", data)


# ── Dispatcher ─────────────────────────────────────────────────────────

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    pv = packet.get("PROB_VERIFY") or {}
    # Discrete
    if pv.get("outcomes") is not None and pv.get("probabilities") is not None:
        if pv.get("claimed_expected_value") is not None:
            results.append(verify_expected_value(pv))
        if pv.get("claimed_variance") is not None:
            results.append(verify_variance(pv))
    # Binomial
    if pv.get("binomial_n") is not None and pv.get("binomial_p") is not None:
        if pv.get("binomial_k") is not None and pv.get("claimed_binomial_probability") is not None:
            results.append(verify_binomial_probability(pv))
        if pv.get("claimed_binomial_mean") is not None:
            results.append(verify_binomial_mean(pv))
    # Normal
    if all(pv.get(k) is not None for k in ("normal_mu", "normal_sigma", "normal_x", "claimed_normal_cdf")):
        results.append(verify_normal_cdf(pv))
    if pv.get("k_std") is not None and pv.get("claimed_normal_within_std") is not None:
        results.append(verify_normal_within_std(pv))
    # Poisson
    if all(pv.get(k) is not None for k in ("poisson_lambda", "poisson_k", "claimed_poisson_probability")):
        results.append(verify_poisson_probability(pv))
    # Bayes
    if all(pv.get(k) is not None for k in ("p_a", "p_b_given_a", "p_b_given_not_a", "claimed_p_a_given_b")):
        results.append(verify_bayes(pv))
    # Conditional
    if pv.get("p_a_and_b") is not None and pv.get("p_b") is not None and pv.get("claimed_p_a_given_b") is not None and pv.get("p_b_given_a") is None:
        # Only fire if Bayes path isn't fired (would have p_b_given_a)
        results.append(verify_conditional_probability(pv))
    # Independence
    if all(pv.get(k) is not None for k in ("p_a", "p_b", "p_a_and_b", "claimed_independent")):
        results.append(verify_independence(pv))
    if not results:
        results.append(na("probability", "no PROB_VERIFY artifacts present"))
    return results
