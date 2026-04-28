"""Verifier framework — actual computational checks of submitted artifacts.

Domain validators check attestation flags (did the author affirm a constraint).
Verifiers check artifacts (does the math actually balance, does the equation
have the same units on both sides, does the p-value match the data).

Attestation lives on FLOOR. Verification lives on RED. When a packet supplies
artifacts and the verifier can run, a verifier failure is a RED rejection
because the underlying claim is mathematically wrong, not just unaffirmed.

Each verifier returns a VerifierResult:
    status: CONFIRMED | MISMATCH | NOT_APPLICABLE | ERROR
    detail: short human-readable description
    data:   structured payload (e.g. computed coefficients, residuals)

NOT_APPLICABLE means the verifier could not run because the relevant artifact
was absent. ERROR means the artifact was present but malformed. MISMATCH means
the artifact ran and contradicted the author's claim.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Literal, Optional

VerifierStatus = Literal["CONFIRMED", "MISMATCH", "NOT_APPLICABLE", "ERROR"]

@dataclass(frozen=True)
class VerifierResult:
    name: str
    status: VerifierStatus
    detail: str = ""
    data: Optional[Dict[str, Any]] = None

    @property
    def passed(self) -> bool:
        return self.status == "CONFIRMED"

    @property
    def failed(self) -> bool:
        return self.status in ("MISMATCH", "ERROR")

    @property
    def applicable(self) -> bool:
        return self.status != "NOT_APPLICABLE"


def na(name: str, reason: str = "no artifact provided") -> VerifierResult:
    return VerifierResult(name=name, status="NOT_APPLICABLE", detail=reason)


def confirm(name: str, detail: str = "", data: Optional[Dict[str, Any]] = None) -> VerifierResult:
    return VerifierResult(name=name, status="CONFIRMED", detail=detail, data=data)


def mismatch(name: str, detail: str, data: Optional[Dict[str, Any]] = None) -> VerifierResult:
    return VerifierResult(name=name, status="MISMATCH", detail=detail, data=data)


def error(name: str, detail: str, data: Optional[Dict[str, Any]] = None) -> VerifierResult:
    return VerifierResult(name=name, status="ERROR", detail=detail, data=data)
