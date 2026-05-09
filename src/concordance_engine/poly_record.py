"""PolymathicRecord — the polymathic coordinator's collective output.

A single WitnessRecord seals one domain claim. A PolymathicRecord is
what the polymathic coordinator returns: all applicable domains fired
simultaneously, their results collected, the axis overlaps surfaced.

The intelligence emerges from the connections between verifiers, not
from any single verifier. Domains that share a dimensional axis are
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
QUARANTINE    = "QUARANTINE"     # claims decomposed cleanly but unverifiable
OUT_OF_SCOPE  = "OUT_OF_SCOPE"   # no domain matched
ERROR         = "ERROR"          # system failure


@dataclass(frozen=True)
class DomainResult:
    """One worker's report.

    `source_claim` is the atomic claim (from the decompose phase) that
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
    """The polymathic coordinator's collective output.

    `situation`           — the original natural-language input
    `atomic_claims`       — claims after the decompose phase
    `quarantined_claims`  — claims that decomposed cleanly but couldn't be
                            classified to any domain. Held pending more
                            information or manual triage; not discarded.
    `domain_results`      — every verifier's report (verify phase)
    `axis_overlaps`       — dimensions shared by ≥2 domains
    `composite_verdict`   — CONCORDANT | DISCORDANT | MIXED |
                            QUARANTINE | OUT_OF_SCOPE | ERROR
    `subject_pubkey`      — soulbound (set at seal time)
    `permanent_ref`       — CAS content hash (collect phase complete)
    """
    situation: str
    domain_results: Tuple[DomainResult, ...]
    axis_overlaps: Tuple[AxisOverlap, ...]
    composite_verdict: str
    atomic_claims: Tuple[str, ...] = ()
    quarantined_claims: Tuple[str, ...] = ()   # quarantined
    keeper_manifest: Optional[Dict[str, Any]] = None   # keeper's triage output
    closest_precedent: Optional[Dict[str, Any]] = None  # axis-index match
    axis_weights: Optional[Dict[str, float]] = None     # per-domain structural weight
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
        if self.axis_weights:
            out["axis_weights"] = self.axis_weights
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
            axis_weights=d.get("axis_weights"),
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
        return QUARANTINE          # confirmed domains + quarantined claims → QUARANTINE
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


# ── Axis-weight computation ─────────────────────────────────────────────

def compute_axis_weights(domain_results: List[DomainResult]) -> Dict[str, float]:
    """Structural weight for each domain relative to the full situation.

    Weight = |domain.axis_dims ∩ situation_dims| / |situation_dims|

    where situation_dims = union of all domains' axis_dims.

    A domain that covers 4 of the 5 situation axes gets weight 0.8;
    one that covers only 1 axis gets 0.2.  Domains with no overlap at all
    get 0.0 — they fired but aren't structurally central.

    If situation_dims is empty (no axes known), all domains get 1.0 so
    the weighted verdict degrades gracefully to the unweighted logic.

    Returns a dict keyed by domain name.  Values sum to ≤ len(results)
    (not normalised to 1 — each domain's weight is independent).
    """
    situation_dims: FrozenSet[str] = frozenset().union(
        *(dr.axis_dims for dr in domain_results)
    )
    if not situation_dims:
        return {dr.domain: 1.0 for dr in domain_results}

    return {
        dr.domain: round(len(dr.axis_dims & situation_dims) / len(situation_dims), 3)
        for dr in domain_results
    }


# Fraction of weighted mismatch above which the verdict becomes DISCORDANT.
# Below this floor, peripheral mismatches (low-weight domains) yield MIXED.
MISMATCH_FLOOR = 0.25


def compute_weighted_composite_verdict(
    domain_results: List[DomainResult],
    weights: Optional[Dict[str, float]] = None,
    quarantined_claims: Optional[List[str]] = None,
    mismatch_floor: float = MISMATCH_FLOOR,
) -> str:
    """Axis-weight-aware composite verdict.

    A MISMATCH from a peripheral domain (low structural weight) only
    triggers DISCORDANT if it carries enough combined weight. Light
    peripheral mismatches produce MIXED so the synthesis isn't vetoed by
    a domain that barely touches the situation's core axes.

    Weighting logic
    ───────────────
    mismatch_frac = Σ weight(mismatched domains) / Σ weight(all meaningful domains)

    If mismatch_frac >= mismatch_floor (default 0.25) → DISCORDANT
    If 0 < mismatch_frac < mismatch_floor → MIXED
    If mismatch_frac == 0 and confirmations exist → CONCORDANT

    Falls back to the unweighted `compute_composite_verdict` when weights
    is None (e.g. the record was built before this feature existed).

    Backward compatibility
    ──────────────────────
    Single-domain packets produce one result with weight 1.0, so the
    weighted and unweighted paths always agree.  The benchmark is safe.
    """
    has_quarantined = bool(quarantined_claims)

    if not domain_results and not has_quarantined:
        return OUT_OF_SCOPE
    if not domain_results and has_quarantined:
        return QUARANTINE

    verdicts = {dr.verdict for dr in domain_results}
    if "ERROR" in verdicts:
        return ERROR

    meaningful = [dr for dr in domain_results if dr.verdict != "NOT_APPLICABLE"]
    if not meaningful:
        return QUARANTINE if has_quarantined else OUT_OF_SCOPE

    if weights is None:
        return compute_composite_verdict(domain_results, quarantined_claims)

    w_total     = sum(weights.get(dr.domain, 1.0) for dr in meaningful)
    w_mismatch  = sum(weights.get(dr.domain, 1.0) for dr in meaningful if dr.verdict == "MISMATCH")
    w_confirmed = sum(weights.get(dr.domain, 1.0) for dr in meaningful if dr.verdict == "CONFIRMED")

    mismatch_frac = (w_mismatch / w_total) if w_total > 0 else 0.0

    if mismatch_frac >= mismatch_floor:
        return DISCORDANT
    if w_mismatch > 0:
        # Peripheral dissent — structurally below the veto threshold
        return QUARANTINE if has_quarantined else MIXED
    if w_confirmed > 0 and has_quarantined:
        return QUARANTINE
    if w_confirmed > 0:
        return CONCORDANT
    return QUARANTINE if has_quarantined else OUT_OF_SCOPE


__all__ = [
    "DomainResult",
    "AxisOverlap",
    "PolymathicRecord",
    "compute_composite_verdict",
    "compute_weighted_composite_verdict",
    "compute_axis_weights",
    "compute_axis_overlaps",
    "MISMATCH_FLOOR",
    "CONCORDANT", "DISCORDANT", "MIXED", "OUT_OF_SCOPE", "ERROR",
]
