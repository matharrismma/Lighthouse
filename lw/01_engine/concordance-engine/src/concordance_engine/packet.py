"""
concordance_engine/packet.py — Core data structures.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GateResult:
    """Outcome of a single gate evaluation."""
    gate: str                               # "RED" | "FLOOR" | "BROTHERS" | "GOD"
    status: str                             # "PASS" | "REJECT" | "QUARANTINE"
    reasons: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Final verdict of the four-gate engine."""
    overall: str                            # "PASS" | "REJECT" | "QUARANTINE"
    gate_results: List[GateResult] = field(default_factory=list)

    def add(self, gr: GateResult) -> None:
        self.gate_results.append(gr)
