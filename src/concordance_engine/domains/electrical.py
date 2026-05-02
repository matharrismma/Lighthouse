"""Electrical engineering domain validator (engineering umbrella)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class ElectricalValidator:
    domain = "electrical"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ev = packet.get("ELEC_VERIFY") or {}

        if not ev:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Electrical packets must include either ELEC_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("resistance_ohm", "resistance_ohm_rc", "capacitance_F"):
            if fld in ev:
                try:
                    v = float(ev[fld])
                    if v < 0:
                        errors.append(f"{fld} must be non-negative, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {ev[fld]!r}")

        if "voltages_in_loop" in ev and not isinstance(ev["voltages_in_loop"], (list, tuple)):
            errors.append("voltages_in_loop must be a list")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        ev = packet.get("ELEC_VERIFY") or {}

        if ev:
            verifiable_keys = (
                "voltage_V", "power_W_claim", "claimed_loop_sum_V",
                "claimed_capacitor_voltage_V",
            )
            if not any(k in ev for k in verifiable_keys):
                errors.append("ELEC_VERIFY block must contain at least one verifiable claim")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Electrical packets without ELEC_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
