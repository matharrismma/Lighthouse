"""Cryptography domain validator (information/encoding grid axis sibling
to genetics + computer_science)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class CryptographyValidator:
    domain = "cryptography"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        cv = packet.get("CRYPTO_VERIFY") or {}

        if not cv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append(
                    "Cryptography packets must include either CRYPTO_VERIFY{} or non-empty claims[]"
                )
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        if "key_bits" in cv:
            try:
                b = int(cv["key_bits"])
                if b <= 0:
                    errors.append(f"key_bits must be positive, got {b}")
            except (TypeError, ValueError):
                errors.append(f"key_bits must be an integer, got {cv['key_bits']!r}")

        for fld in ("claimed_hash_hex", "claimed_hmac_hex"):
            if fld in cv:
                v = cv[fld]
                if not (isinstance(v, str) and all(c in "0123456789abcdefABCDEF" for c in v.replace(" ", ""))):
                    errors.append(f"{fld} must be a hex string, got {v!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        cv = packet.get("CRYPTO_VERIFY") or {}

        if cv:
            verifiable_keys = (
                "claimed_hash_hex", "claimed_hash_strength",
                "claimed_hmac_hex", "claimed_decoded", "claimed_key_strength",
            )
            if not any(k in cv for k in verifiable_keys):
                errors.append("CRYPTO_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Cryptography packets without CRYPTO_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
