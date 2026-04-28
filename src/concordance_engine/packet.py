from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Literal

DecisionStatus = Literal["REJECT", "QUARANTINE", "PASS"]

@dataclass(frozen=True)
class GateResult:
    gate: str
    status: DecisionStatus
    reasons: List[str]
    details: Dict[str, Any] | None = None

@dataclass(frozen=True)
class EngineResult:
    overall: DecisionStatus
    gate_results: List[GateResult]

    @property
    def rejected(self) -> bool:
        return self.overall == "REJECT"

    @property
    def quarantined(self) -> bool:
        return self.overall == "QUARANTINE"

    @property
    def passed_hard_gates(self) -> bool:
        return all(gr.status != "REJECT" for gr in self.gate_results if gr.gate in ("RED","FLOOR"))
