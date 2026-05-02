"""Networking domain validator (encoding-grid axis sibling)."""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


class NetworkingValidator:
    domain = "networking"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        nv = packet.get("NET_VERIFY") or {}

        if not nv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Networking packets must include either NET_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        if "subnet_prefix" in nv:
            try:
                n = int(nv["subnet_prefix"])
                if not (0 <= n <= 128):
                    errors.append(f"subnet_prefix must be 0-128 (IPv4: 0-32, IPv6: 0-128), got {n}")
            except (TypeError, ValueError):
                errors.append(f"subnet_prefix must be an integer, got {nv['subnet_prefix']!r}")

        if "claimed_usable_hosts" in nv:
            try:
                c = int(nv["claimed_usable_hosts"])
                if c < 0:
                    errors.append(f"claimed_usable_hosts cannot be negative, got {c}")
            except (TypeError, ValueError):
                errors.append(f"claimed_usable_hosts must be an integer")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        nv = packet.get("NET_VERIFY") or {}

        if nv:
            verifiable_keys = (
                "claimed_format_valid", "claimed_in_subnet",
                "claimed_usable_hosts", "claimed_mac_valid",
            )
            if not any(k in nv for k in verifiable_keys):
                errors.append("NET_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys))
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Networking packets without NET_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
