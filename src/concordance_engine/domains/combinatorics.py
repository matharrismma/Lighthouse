"""Combinatorics domain validator."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class CombinatoricsValidator:
    domain = "combinatorics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        cv = packet.get("COMB_VERIFY") or {}
        if not cv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Combinatorics packets must include either COMB_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("perm_n", "perm_k", "comb_n", "comb_k", "derangement_n",
                    "claimed_permutations", "claimed_combinations",
                    "claimed_derangements", "claimed_multinomial"):
            if fld in cv:
                try:
                    int(cv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be an integer")
        if "multinomial_groups" in cv:
            g = cv["multinomial_groups"]
            if not isinstance(g, list) or len(g) == 0:
                errors.append("multinomial_groups must be a non-empty list of ints")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        cv = packet.get("COMB_VERIFY") or {}
        if cv:
            verifiable = ("claimed_permutations", "claimed_combinations",
                          "claimed_derangements", "claimed_multinomial")
            if not any(k in cv for k in verifiable):
                return [reject("FLOOR", "COMB_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Combinatorics packets without COMB_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
