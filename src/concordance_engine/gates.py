from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from .packet import GateResult, DecisionStatus

def reject(gate: str, *reasons: str, details: Dict[str, Any] | None = None) -> GateResult:
    return GateResult(gate=gate, status="REJECT", reasons=list(reasons), details=details)

def quarantine(gate: str, *reasons: str, details: Dict[str, Any] | None = None) -> GateResult:
    return GateResult(gate=gate, status="QUARANTINE", reasons=list(reasons), details=details)

def ok(gate: str, details: Dict[str, Any] | None = None) -> GateResult:
    return GateResult(gate=gate, status="PASS", reasons=[], details=details)
