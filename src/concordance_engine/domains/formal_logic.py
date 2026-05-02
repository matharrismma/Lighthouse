"""Formal Logic domain validator — RED/FLOOR for the LOGIC_VERIFY block."""
from __future__ import annotations
import re
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


_VAR_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*$")


class FormalLogicValidator:
    domain = "formal_logic"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        lv = packet.get("LOGIC_VERIFY") or {}

        if not lv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append(
                    "Formal-logic packets must include either LOGIC_VERIFY{} or non-empty claims[]"
                )
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        # Variables, when supplied, must be valid Python identifiers (so SymPy
        # can use them as symbols).
        variables = lv.get("variables")
        if variables is not None:
            if not isinstance(variables, (list, tuple)):
                errors.append(f"variables must be a list, got {type(variables).__name__}")
            else:
                for v in variables:
                    if not (isinstance(v, str) and _VAR_PATTERN.match(v)):
                        errors.append(
                            f"variable {v!r} is not a valid identifier (letters, digits, underscore; "
                            f"must start with a letter or underscore)"
                        )

        if "premises" in lv and not isinstance(lv["premises"], (list, tuple)):
            errors.append(f"premises must be a list, got {type(lv['premises']).__name__}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        lv = packet.get("LOGIC_VERIFY") or {}

        if lv:
            verifiable_pairs = (
                ("formula", "claimed_satisfiable"),
                ("formula", "claimed_tautology"),
                ("formula", "claimed_contradiction"),
                ("premises", "claimed_entailment"),
                ("formula_a", "claimed_equivalent"),
            )
            has_any_pair = any(all(k in lv for k in pair) for pair in verifiable_pairs)
            if not has_any_pair:
                errors.append(
                    "LOGIC_VERIFY block must contain at least one verifiable claim: "
                    "(formula + claimed_satisfiable/tautology/contradiction), "
                    "or (premises + conclusion + claimed_entailment), "
                    "or (formula_a + formula_b + claimed_equivalent)"
                )
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Formal-logic packets without LOGIC_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
