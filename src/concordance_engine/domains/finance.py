"""Finance domain validator (economic governance umbrella sibling)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class FinanceValidator:
    domain = "finance"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        fv = packet.get("FIN_VERIFY") or {}

        if not fv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append(
                    "Finance packets must include either FIN_VERIFY{} or non-empty claims[]"
                )
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        for fld in ("assets", "liabilities", "equity",
                    "principal", "compounding_per_year", "years",
                    "discount_rate", "future_value", "pv_periods"):
            if fld in fv:
                try:
                    float(fv[fld])
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric, got {fv[fld]!r}")

        if "cashflows" in fv:
            cfs = fv["cashflows"]
            if not isinstance(cfs, (list, tuple)) or not cfs:
                errors.append("cashflows must be a non-empty list")

        if "rate" in fv:
            try:
                r = float(fv["rate"])
                if r < -1.0:
                    errors.append(f"interest rate must be >= -1, got {r}")
            except (TypeError, ValueError):
                errors.append(f"rate must be numeric, got {fv['rate']!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        fv = packet.get("FIN_VERIFY") or {}

        if fv:
            verifiable_keys = (
                "assets",  # accounting identity
                "claimed_future_value",
                "claimed_npv",
                "claimed_present_value",
            )
            if not any(k in fv for k in verifiable_keys):
                errors.append("FIN_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Finance packets without FIN_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
