"""Sports analytics verifier (statistics-application axis).

Pythagorean expectation (Bill James), Elo expected-score and rating
update, games-behind. Public-domain sabermetrics + chess-rating math.

Checks:
  * sports_analytics.pythagorean_expectation — W% = RS^k / (RS^k + RA^k)
  * sports_analytics.elo_expected_score      — E_a = 1 / (1 + 10^((R_b - R_a)/400))
  * sports_analytics.elo_rating_update       — R'_a = R_a + K·(S_a - E_a)
  * sports_analytics.games_behind            — GB = ((W_l - W_t) + (L_t - L_l))/2

SPORT_VERIFY shape (any subset):
    {
      "runs_scored": 750, "runs_allowed": 600,
      "pythag_exponent": 2.0,
      "claimed_winning_pct": 0.610,

      "elo_a": 1600, "elo_b": 1500,
      "claimed_expected_score_a": 0.640,

      "elo_a_pre": 1600, "elo_b_pre": 1500,
      "actual_score_a": 1.0, "elo_K": 32,
      "claimed_elo_a_post": 1611.51,

      "leader_wins": 50, "leader_losses": 30,
      "team_wins": 45, "team_losses": 35,
      "claimed_games_behind": 5.0,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def verify_pythagorean_expectation(spec: Dict[str, Any]) -> VerifierResult:
    name = "sports_analytics.pythagorean_expectation"
    rs = spec.get("runs_scored")
    ra = spec.get("runs_allowed")
    k = spec.get("pythag_exponent", 2.0)
    claimed = spec.get("claimed_winning_pct")
    if rs is None or ra is None or claimed is None:
        return na(name)
    try:
        rsf, raf, kf, c = float(rs), float(ra), float(k), float(claimed)
    except (TypeError, ValueError):
        return error(name, "inputs must be numeric")
    if rsf < 0 or raf < 0:
        return error(name, "runs scored/allowed must be non-negative")
    if rsf == 0 and raf == 0:
        return error(name, "cannot compute when both RS and RA are zero")
    if kf <= 0:
        return error(name, "exponent must be positive")
    actual = (rsf ** kf) / ((rsf ** kf) + (raf ** kf))
    tol = float(spec.get("tolerance_pct", 0.005))
    diff = abs(actual - c)
    data = {"runs_scored": rsf, "runs_allowed": raf, "exponent": kf,
            "actual_winning_pct": actual, "claimed_winning_pct": c,
            "diff": diff, "tolerance_pct": tol,
            "formula": "W% = RS^k / (RS^k + RA^k)  (Bill James)"}
    if diff <= tol:
        return confirm(name, f"W% = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"W% = {actual:.4f}, claimed {c} (diff {diff:.4f})", data)


def verify_elo_expected_score(spec: Dict[str, Any]) -> VerifierResult:
    name = "sports_analytics.elo_expected_score"
    Ra = spec.get("elo_a")
    Rb = spec.get("elo_b")
    claimed = spec.get("claimed_expected_score_a")
    if Ra is None or Rb is None or claimed is None:
        return na(name)
    try:
        Raf, Rbf, c = float(Ra), float(Rb), float(claimed)
    except (TypeError, ValueError):
        return error(name, "ratings and claim must be numeric")
    actual = 1.0 / (1.0 + 10 ** ((Rbf - Raf) / 400.0))
    tol = float(spec.get("tolerance", 0.005))
    diff = abs(actual - c)
    data = {"elo_a": Raf, "elo_b": Rbf,
            "actual_expected": actual, "claimed_expected": c, "diff": diff,
            "tolerance": tol,
            "formula": "E_a = 1 / (1 + 10^((R_b − R_a)/400))"}
    if diff <= tol:
        return confirm(name, f"E_a = {actual:.4f} (matches claim)", data)
    return mismatch(name, f"E_a = {actual:.4f}, claimed {c} (diff {diff:.4f})", data)


def verify_elo_rating_update(spec: Dict[str, Any]) -> VerifierResult:
    """R'_a = R_a + K·(S_a − E_a) where E_a is from the current ratings."""
    name = "sports_analytics.elo_rating_update"
    Ra = spec.get("elo_a_pre")
    Rb = spec.get("elo_b_pre")
    Sa = spec.get("actual_score_a")
    K = spec.get("elo_K")
    claimed = spec.get("claimed_elo_a_post")
    if any(v is None for v in (Ra, Rb, Sa, K, claimed)):
        return na(name)
    try:
        Raf, Rbf, Saf, Kf, c = float(Ra), float(Rb), float(Sa), float(K), float(claimed)
    except (TypeError, ValueError):
        return error(name, "all inputs must be numeric")
    if not (0.0 <= Saf <= 1.0):
        return error(name, f"actual_score_a must be in [0, 1] (0 loss, 0.5 draw, 1 win), got {Saf}")
    if Kf <= 0:
        return error(name, "K must be positive")
    Ea = 1.0 / (1.0 + 10 ** ((Rbf - Raf) / 400.0))
    actual = Raf + Kf * (Saf - Ea)
    tol = float(spec.get("tolerance_rating", 0.5))
    diff = abs(actual - c)
    data = {"elo_a_pre": Raf, "elo_b_pre": Rbf, "actual_score_a": Saf,
            "K": Kf, "expected_score_a": Ea,
            "actual_post": actual, "claimed_post": c, "diff": diff,
            "tolerance_rating": tol,
            "formula": "R'_a = R_a + K·(S_a − E_a)"}
    if diff <= tol:
        return confirm(name, f"R'_a = {actual:.3f} (matches claim)", data)
    return mismatch(name, f"R'_a = {actual:.3f}, claimed {c} (diff {diff:.3f})", data)


def verify_games_behind(spec: Dict[str, Any]) -> VerifierResult:
    """GB = ((W_l − W_t) + (L_t − L_l)) / 2"""
    name = "sports_analytics.games_behind"
    Wl = spec.get("leader_wins")
    Ll = spec.get("leader_losses")
    Wt = spec.get("team_wins")
    Lt = spec.get("team_losses")
    claimed = spec.get("claimed_games_behind")
    if any(v is None for v in (Wl, Ll, Wt, Lt, claimed)):
        return na(name)
    try:
        Wlf, Llf, Wtf, Ltf, c = float(Wl), float(Ll), float(Wt), float(Lt), float(claimed)
    except (TypeError, ValueError):
        return error(name, "win/loss counts and claim must be numeric")
    for v, n in ((Wlf, "leader_wins"), (Llf, "leader_losses"),
                 (Wtf, "team_wins"), (Ltf, "team_losses")):
        if v < 0:
            return error(name, f"{n} must be non-negative")
    actual = ((Wlf - Wtf) + (Ltf - Llf)) / 2.0
    tol = float(spec.get("tolerance_games", 0.0))
    diff = abs(actual - c)
    data = {"leader_record": [Wlf, Llf], "team_record": [Wtf, Ltf],
            "actual_games_behind": actual, "claimed_games_behind": c,
            "diff": diff, "tolerance_games": tol,
            "formula": "GB = ((W_leader − W_team) + (L_team − L_leader)) / 2"}
    if diff <= tol:
        return confirm(name, f"GB = {actual} (matches claim)", data)
    return mismatch(name, f"GB = {actual}, claimed {c} (diff {diff})", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    sv = packet.get("SPORT_VERIFY") or {}
    if all(k in sv for k in ("runs_scored", "runs_allowed", "claimed_winning_pct")):
        results.append(verify_pythagorean_expectation(sv))
    if all(k in sv for k in ("elo_a", "elo_b", "claimed_expected_score_a")):
        results.append(verify_elo_expected_score(sv))
    if all(k in sv for k in ("elo_a_pre", "elo_b_pre", "actual_score_a", "elo_K", "claimed_elo_a_post")):
        results.append(verify_elo_rating_update(sv))
    if all(k in sv for k in ("leader_wins", "leader_losses", "team_wins",
                              "team_losses", "claimed_games_behind")):
        results.append(verify_games_behind(sv))
    if not results:
        results.append(na("sports_analytics", "no SPORT_VERIFY artifacts present"))
    return results
