"""Document validation domain validator."""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class DocumentValidationValidator:
    domain = "document_validation"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        dv = packet.get("DOC_VERIFY") or {}
        if not dv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Document-validation packets must include either DOC_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        # Inputs must be strings (or coercible).
        for fld in ("isbn10", "isbn13", "luhn_number", "ean_or_upc"):
            if fld in dv and not isinstance(dv[fld], (str, int)):
                errors.append(f"{fld} must be a string or integer")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        dv = packet.get("DOC_VERIFY") or {}
        if dv:
            keys = ("claimed_isbn10_valid", "claimed_isbn13_valid",
                    "claimed_luhn_valid", "claimed_ean_valid")
            if not any(k in dv for k in keys):
                return [reject("FLOOR", "DOC_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Document-validation packets without DOC_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
