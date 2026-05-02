"""verifiers/base.py — VerifierResult shared by all computational verifiers."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class VerifierResult:
    """
    Result of a single computational verification step.
    status: CONFIRMED | MISMATCH | ERROR | SKIPPED
    """
    name: str
    status: str
    detail: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
