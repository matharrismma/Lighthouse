"""
verifiers/governance.py — Decision packet structural completeness.
"""
from __future__ import annotations
from typing import Any, Dict
from .base import VerifierResult

VALID_SCOPES = {"adapter", "canon", "mesh", "kernel", "local"}
REQUIRED_FIELDS = ["title", "scope", "red_items", "floor_items",
                   "way_path", "execution_steps", "witnesses"]


def verify_decision_packet_shape(dp: Dict[str, Any]) -> VerifierResult:
    name = "governance.decision_packet_shape"
    issues = []

    for field in REQUIRED_FIELDS:
        val = dp.get(field)
        if val is None:
            issues.append(f"Missing required field: '{field}'")
        elif isinstance(val, str) and not val.strip():
            issues.append(f"Field '{field}' is empty")
        elif isinstance(val, list) and len(val) == 0:
            issues.append(f"Field '{field}' is an empty list")

    scope = dp.get("scope", "")
    if scope and scope not in VALID_SCOPES:
        issues.append(f"Invalid scope '{scope}'; must be one of {sorted(VALID_SCOPES)}")

    if not issues:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail="Decision packet is structurally complete.",
                              data={"scope": scope,
                                    "witness_count": len(dp.get("witnesses", []))})
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Incomplete decision packet: {'; '.join(issues)}",
                          data={"issues": issues})


def verify_witness_count_consistency(dp: Dict[str, Any], packet: Dict[str, Any]) -> VerifierResult:
    name = "governance.witness_count_consistency"
    named = len(dp.get("witnesses", []))
    claimed = int(packet.get("witness_count", 0))
    if named == claimed:
        return VerifierResult(name=name, status="CONFIRMED",
                              detail=f"Witness count consistent: {named} named, {claimed} claimed.")
    return VerifierResult(name=name, status="MISMATCH",
                          detail=f"Witness mismatch: {named} named in DECISION_PACKET, "
                                 f"but packet claims {claimed}.",
                          data={"named": named, "claimed": claimed})


def run(packet: dict) -> list:
    results = []
    dp = packet.get("DECISION_PACKET")
    if dp is None:
        return results
    results.append(verify_decision_packet_shape(dp))
    results.append(verify_witness_count_consistency(dp, packet))
    return results
