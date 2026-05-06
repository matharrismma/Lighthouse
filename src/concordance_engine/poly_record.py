"""PolymathicRecord — the hive's collective output.

A single WitnessRecord seals one domain claim. A PolymathicRecord is
what the hive returns: all applicable domains fired simultaneously,
their results collected, the axis overlaps surfaced.

The intelligence emerges from the connections between workers, not
from any single worker. Domains that share a dimensional axis are
structurally linked — the overlap IS the signal.

Schema version tracked separately from WitnessRecord (1.x) so
they can evolve independently.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Tuple


POLYMATHIC_SCHEMA_VERSION = "1.0"

# Composite verdict vocabulary
CONCORDANT    = "CONCORDANT"     # all fired domains confirmed
DISCORDANT    = "DISCORDANT"     # at least one mismatch
MIXED         = "MIXED"          # some confirmed, some not-applicable
QUARANTINE    = "QUARANTINE"     # airlocked — claims stripped but unverifiable
OUT_OF_SCOPE  = "OUT_OF_SCOPE"   # no domain matched
ERROR         = "ERROR"          # system failure


@dataclass(frozen=True)
class DomainResult:
    """One worker's report.

    `source_claim` is the atomic claim (from the strip phase) that
    spawned this domain dispatch — the provenance link in the
    strip → send → wrap chain.
    """
    domain: str
    spec: Dict[str, Any]
    result: Dict[str, Any]       # raw verifier output
    verdict: str                 # CONFIRMED | MISMATCH | NOT_APPLICABLE | ERROR
    detail: str = ""
    axis_dims: FrozenSet[str] = field(default_factory=frozenset)
    source_claim: Optional[str] = None   # the atomic claim that spawned this

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "domain": self.domain,
            "spec": self.spec,
            "verdict": self.verdict,
            "detail": self.detail,
            "axis_dims": sorted(self.axis_dims),
            "result": self.result,
        }
        if self.source_claim is not None:
            out["source_claim"] = self.source_claim
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DomainResult":
        return cls(
            domain=d["domain"],
            spec=d.get("spec", {}),
            result=d.get("result", {}),
            verdict=d.get("verdict", "UNKNOWN"),
            detail=d.get("detail", ""),
            axis_dims=frozenset(d.get("axis_dims", [])),
            source_claim=d.get("source_claim"),
        )


@dataclass(frozen=True)
class AxisOverlap:
    """A shared scaffold dimension claimed by two or more domains.

    When biology + labor + governance all sit on `authority_trust`,
    that shared axis is a structural signal — the situation spans
    those domains along a common load-bearing dimension.
    """
    dimension: str
    domains: Tuple[str, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {"dimension": self.dimension, "domains": list(self.domains)}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AxisOverlap":
        return cls(dimension=d["dimension"], domains=tuple(d.get("domains", [])))


@dataclass(frozen=True)
class PolymathicRecord:
    """The hive's collective output.

    `situation`      — the original natural-language input
    `atomic_claims`       — stripped intermediate (decompose/strip phase)
    `quarantined_claims`  — claims that were stripped but couldn't be
                            classified to any domain. Airlocked: not
                            dispatched, not discarded. Held pending more
                            information or manual triage.
    `domain_results`      — every worker's report (send phase)
    `axis_overlaps`       — dimensions shared by ≥2 domains
    `composite_verdict`   — CONCORDANT | DISCORDANT | MIXED |
                            QUARANTINE | OUT_OF_SCOPE | ERROR
    `subject_pubkey`      — soulbound (set at seal time)
    `permanent_ref`       — CAS content hash (wrap phase complete)
    """
    situation: str
    domain_results: Tuple[DomainResult, ...]
    axis_overlaps: Tuple[AxisOverlap, ...]
    composite_verdict: str
    atomic_claims: Tuple[str, ...] = ()
    quarantined_claims: Tuple[str, ...] = ()   # airlocked
    keeper_manifest: Optional[Dict[str, Any]] = None  # keeper's triage output
    closest_precedent: Optional[Dict[str, Any]] = None  # axis-index match
    subject_pubkey: Optional[str] = None
    permanent_ref: Optional[str] = None
    schema_version: str = POLYMATHIC_SCHEMA_VERSION

    # ── Derived views ──────────────────────────────────────────────────

    @property
    def confirmed_domains(self) -> Tuple[DomainResult, ...]:
        return tuple(d for d in self.domain_results if d.verdict == "CONFIRMED")

    @property
    def discordant_domains(self) -> Tuple[DomainResult, ...]:
        return tuple(d for d in self.domain_results if d.verdict == "MISMATCH")

    @property
    def domain_count(self) -> int:
        return len(self.domain_results)

    # ── Serialization ──────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "situation": self.situation,
            "composite_verdict": self.composite_verdict,
            "domain_results": [dr.to_dict() for dr in self.domain_results],
            "axis_overlaps": [ao.to_dict() for ao in self.axis_overlaps],
        }
        if self.atomic_claims:
            out["atomic_claims"] = list(self.atomic_claims)
        if self.quarantined_claims:
            out["quarantined_claims"] = list(self.quarantined_claims)
        if self.keeper_manifest is not None:
            out["keeper_manifest"] = self.keeper_manifest
        if self.closest_precedent is not None:
            out["closest_precedent"] = self.closest_precedent
        if self.subject_pubkey is not None:
            out["subject_pubkey"] = self.subject_pubkey
        # content_hash: SHA-256 of canonical JSON excluding itself + permanent_ref
        canonical = json.dumps(out, sort_keys=True, separators=(",", ":")).encode("utf-8")
        out["content_hash"] = hashlib.sha256(canonical).hexdigest()
        if self.permanent_ref is not None:
            out["permanent_ref"] = self.permanent_ref
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PolymathicRecord":
        return cls(
            situation=d["situation"],
            domain_results=tuple(DomainResult.from_dict(r) for r in d.get("domain_results", [])),
            axis_overlaps=tuple(AxisOverlap.from_dict(a) for a in d.get("axis_overlaps", [])),
            composite_verdict=d.get("composite_verdict", "UNKNOWN"),
            atomic_claims=tuple(d.get("atomic_claims", [])),
            quarantined_claims=tuple(d.get("quarantined_claims", [])),
            keeper_manifest=d.get("keeper_manifest"),
            closest_precedent=d.get("closest_precedent"),
            subject_pubkey=d.get("subject_pubkey"),
            permanent_ref=d.get("permanent_ref"),
            schema_version=d.get("schema_version", POLYMATHIC_SCHEMA_VERSION),
        )


# ── Verdict computation ─────────────────────────────────────────────────

def compute_composite_verdict(
    domain_results: List[DomainResult],
    quarantined_claims: Optional[List[str]] = None,
) -> str:
    has_quarantined = bool(quarantined_claims)

    if not domain_results and not has_quarantined:
        return OUT_OF_SCOPE
    if not domain_results and has_quarantined:
        return QUARANTINE

    verdicts = {dr.verdict for dr in domain_results}
    if "ERROR" in verdicts:
        return ERROR

    meaningful = {v for v in verdicts if v != "NOT_APPLICABLE"}

    if "MISMATCH" in meaningful:
        return DISCORDANT          # discordant beats quarantine
    if not meaningful and has_quarantined:
        return QUARANTINE
    if not meaningful:
        return OUT_OF_SCOPE
    if meaningful == {"CONFIRMED"} and has_quarantined:
        return QUARANTINE          # confirmed domains + airlocked claims → QUARANTINE
    if meaningful == {"CONFIRMED"}:
        return CONCORDANT
    if has_quarantined:
        return QUARANTINE
    return MIXED


# ── Axis-overlap computation ────────────────────────────────────────────

def compute_axis_overlaps(domain_results: List[DomainResult]) -> List[AxisOverlap]:
    dim_to_domains: Dict[str, List[str]] = {}
    for dr in domain_results:
        for dim in dr.axis_dims:
            dim_to_domains.setdefault(dim, []).append(dr.domain)
    return [
        AxisOverlap(dimension=dim, domains=tuple(sorted(set(domains))))
        for dim, domains in sorted(dim_to_domains.items())
        if len(set(domains)) >= 2
    ]


__all__ = [
    "DomainResult",
    "AxisOverlap",
    "PolymathicRecord",
    "compute_composite_verdict",
    "compute_axis_overlaps",
    "CONCORDANT", "DISCORDANT", "MIXED", "OUT_OF_SCOPE", "ERROR",
]
