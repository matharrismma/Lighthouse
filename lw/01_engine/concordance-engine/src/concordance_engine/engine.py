"""
concordance_engine/engine.py — Four-gate validation engine.

Usage:
    from concordance_engine.engine import EngineConfig, validate_packet
    config = EngineConfig()
    result = validate_packet(packet_dict, now_epoch=int(time.time()), config=config)
    print(result.overall)  # "PASS" | "REJECT" | "QUARANTINE"
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .packet import GateResult, ValidationResult
from .gates import gate_red, gate_floor, gate_brothers, gate_god


@dataclass
class EngineConfig:
    """Configuration for the four-gate engine."""
    schema_path: str = ""                   # optional JSON schema for packet validation
    default_scope: str = "adapter"          # default scope if not specified
    run_verifiers: bool = True              # run computational verifiers
    wait_window_seconds: int = 3600         # minimum seconds from created_epoch


def validate_packet(
    packet: Dict[str, Any],
    now_epoch: Optional[int] = None,
    config: Optional[EngineConfig] = None,
) -> ValidationResult:
    """
    Run the four-gate validation pipeline on a packet.

    Gates: RED → FLOOR → BROTHERS → GOD
    First gate to fail determines the overall verdict:
        RED/FLOOR fail  → REJECT
        BROTHERS fail   → QUARANTINE
        All pass        → PASS
    """
    if config is None:
        config = EngineConfig()
    if now_epoch is None:
        now_epoch = int(time.time())

    domain = str(packet.get("domain", "governance")).lower()
    result = ValidationResult(overall="PASS")

    # ── Gate 1: RED ─────────────────────────────────────────────────────────
    red = gate_red(packet, domain, run_verifiers=config.run_verifiers)
    result.add(red)
    if red.status == "REJECT":
        result.overall = "REJECT"
        return result

    # ── Gate 2: FLOOR ───────────────────────────────────────────────────────
    floor = gate_floor(packet, domain)
    result.add(floor)
    if floor.status == "REJECT":
        result.overall = "REJECT"
        return result

    # ── Gate 3: BROTHERS ────────────────────────────────────────────────────
    brothers = gate_brothers(packet, now_epoch,
                             wait_window_seconds=config.wait_window_seconds)
    result.add(brothers)
    if brothers.status == "QUARANTINE":
        result.overall = "QUARANTINE"
        return result

    # ── Gate 4: GOD ─────────────────────────────────────────────────────────
    god = gate_god(packet)
    result.add(god)
    result.overall = "PASS"
    return result
