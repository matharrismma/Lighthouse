"""Sports analytics domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class SportsAnalyticsValidator:
    domain = "sports_analytics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        sv = packet.get("SPORT_VERIFY") or {}
        if not sv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Sports analytics packets must include either SPORT_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("runs_scored", "runs_allowed", "pythag_exponent",
                    "elo_a", "elo_b", "elo_a_pre", "elo_b_pre",
                    "actual_score_a", "elo_K",
                    "leader_wins", "leader_losses", "team_wins", "team_losses"):
            if fld in sv:
                try:
                    float(sv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        if "actual_score_a" in sv:
            try:
                s = float(sv["actual_score_a"])
                if not (0.0 <= s <= 1.0):
                    errors.append(f"actual_score_a must be in [0, 1], got {s}")
            except (TypeError, ValueError):
                pass
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        sv = packet.get("SPORT_VERIFY") or {}
        if sv:
            verifiable = ("claimed_winning_pct", "claimed_expected_score_a",
                          "claimed_elo_a_post", "claimed_games_behind")
            if not any(k in sv for k in verifiable):
                return [reject("FLOOR", "SPORT_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Sports-analytics packets without SPORT_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
