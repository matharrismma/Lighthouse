"""Canonical result schema — the WitnessRecord.

The single source of truth that both audiences render from. Agents
serialize it to JSON and parse it; humans see it unfolded as a
Socratic walkthrough. Same object, two surfaces.

Nothing in this module *executes* verification. The engine produces a
WitnessRecord; the witness verifier (verifiers/witness.py) checks one;
the future agent endpoint and human UI render one. This module only
defines the shape and the builder.

Design constraints (load-bearing):
  * Frozen dataclasses everywhere — a sealed record is immutable.
  * Every field is JSON-round-trippable via to_dict / from_dict.
  * No `final_answer` / `answer` field anywhere. The doctrine is
    expressed in the *absence* of such a field, and the witness
    verifier enforces it at validation time.
  * Anchors carry their `layer` from the source hierarchy, so
    provenance is on every cited rule, not bolted on.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, FrozenSet, List, Literal, Optional, Tuple

from .packet import GateResult, EngineResult, DecisionStatus
from .verifiers.base import VerifierResult, VerifierStatus


# Source-hierarchy layers (Matt's doctrinal commitment, made type-safe).
SourceLayer = Literal[
    "jesus_words",
    "bible",
    "apostles",
    "recognized_elders",
]
SOURCE_LAYERS: Tuple[str, ...] = (
    "jesus_words", "bible", "apostles", "recognized_elders",
)


@dataclass(frozen=True)
class Anchor:
    """A citation with its layer in the source hierarchy.

    `ref` is the citation string ("Mat 5:37", "Augustine, City of God 19.13").
    `layer` is the doctrinal weight tier; the witness verifier rejects
    any layer outside the source hierarchy.
    `text` is optional — present for human display, absent for agents
    that would resolve the ref themselves.
    """
    ref: str
    layer: SourceLayer
    text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Anchor":
        return cls(ref=d["ref"], layer=d["layer"], text=d.get("text"))


@dataclass(frozen=True)
class AxisCoordinates:
    """The packet's position in the multi-dimensional scaffold.

    The scaffold has seven members (see concordance_engine.grid); each
    axis lives at a position in that 7D space. AxisCoordinates records
    which members this packet's axis sits on — its scaffold address.

    `axis`       — the verifier domain (e.g. "chemistry", "witness")
    `dimensions` — frozenset of scaffold-member names the axis sits on
    `umbrella`   — parent axis if this is a subsystem (genetics → biology)
    """
    axis: str
    dimensions: FrozenSet[str]
    umbrella: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "axis": self.axis,
            "dimensions": sorted(self.dimensions),
        }
        if self.umbrella is not None:
            out["umbrella"] = self.umbrella
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AxisCoordinates":
        return cls(
            axis=d["axis"],
            dimensions=frozenset(d.get("dimensions", [])),
            umbrella=d.get("umbrella"),
        )


@dataclass(frozen=True)
class ClosestCase:
    """The closest already-solved precedent the engine matched on.

    `precedent_id` is a stable identifier into the Evidence Ledger.
    `shared_dimensions` is the scaffold-member overlap with the current
    packet — the structural axes along which the precedent and the
    situation are aligned.
    `shared_anchors` is the set of citation refs (e.g. "Mt 18:15-17")
    that both the packet and the precedent invoke. When the packet
    cites scripture, anchor overlap is a strong second-order signal
    beyond raw scaffold dimensions.
    `distance` is a scalar summary (lower = closer); concrete metric is
    deliberately not pinned here so future implementations can choose.
    `reasoning_overlay` is the precedent's verifier trace, ready to
    overlay onto the current situation in the human UI.

    A WitnessRecord may legitimately have no closest case — for novel
    or out-of-distribution claims. In that case `precedent_id` is None
    and the field is explicitly absent rather than fabricated.
    """
    precedent_id: Optional[str]
    shared_dimensions: FrozenSet[str] = field(default_factory=frozenset)
    shared_anchors: Tuple[str, ...] = ()
    distance: Optional[float] = None
    reasoning_overlay: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"precedent_id": self.precedent_id}
        if self.shared_dimensions:
            out["shared_dimensions"] = sorted(self.shared_dimensions)
        if self.shared_anchors:
            out["shared_anchors"] = list(self.shared_anchors)
        if self.distance is not None:
            out["distance"] = self.distance
        if self.reasoning_overlay is not None:
            out["reasoning_overlay"] = self.reasoning_overlay
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ClosestCase":
        return cls(
            precedent_id=d.get("precedent_id"),
            shared_dimensions=frozenset(d.get("shared_dimensions", [])),
            shared_anchors=tuple(d.get("shared_anchors", [])),
            distance=d.get("distance"),
            reasoning_overlay=d.get("reasoning_overlay"),
        )


@dataclass(frozen=True)
class WitnessRecord:
    """The canonical sealed record. One object, two surfaces.

    `overall`     — engine verdict (PASS/REJECT/QUARANTINE)
    `gate_results`— the four gates' verdicts, in firing order
    `verifier_results` — every verifier result, including NA
    `anchors`     — citations with layer provenance
    `axis_coords` — where this packet sits on the grid
    `closest_case`— the precedent overlay, or None if novel
    `packet_id`   — stable ID for the input packet (for the ledger)
    `schema_version` — bumped when the shape changes; agents check it

    There is deliberately no `final_answer` field. The engine
    categorizes; it does not answer.
    """
    overall: DecisionStatus
    gate_results: Tuple[GateResult, ...]
    verifier_results: Tuple[VerifierResult, ...]
    anchors: Tuple[Anchor, ...] = ()
    axis_coords: Optional[AxisCoordinates] = None
    closest_case: Optional[ClosestCase] = None
    packet_id: Optional[str] = None
    schema_version: str = "1.0"

    # ── derived views ─────────────────────────────────────────────────

    @property
    def passed(self) -> bool:
        return self.overall == "PASS"

    @property
    def hard_gate_failures(self) -> Tuple[GateResult, ...]:
        return tuple(
            gr for gr in self.gate_results
            if gr.gate in ("RED", "FLOOR") and gr.status == "REJECT"
        )

    def confirmed_verifiers(self) -> Tuple[VerifierResult, ...]:
        return tuple(v for v in self.verifier_results if v.status == "CONFIRMED")

    def failed_verifiers(self) -> Tuple[VerifierResult, ...]:
        return tuple(v for v in self.verifier_results if v.status in ("MISMATCH", "ERROR"))

    # ── serialization ─────────────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        """JSON-shaped dict, suitable for the agent surface."""
        out: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "overall": self.overall,
            "gate_results": [
                {
                    "gate": gr.gate,
                    "status": gr.status,
                    "reasons": list(gr.reasons),
                    "details": gr.details,
                }
                for gr in self.gate_results
            ],
            "verifier_results": [
                {
                    "name": v.name,
                    "status": v.status,
                    "detail": v.detail,
                    "data": v.data,
                }
                for v in self.verifier_results
            ],
            "anchors": [a.to_dict() for a in self.anchors],
        }
        if self.axis_coords is not None:
            out["axis_coords"] = self.axis_coords.to_dict()
        if self.closest_case is not None:
            out["closest_case"] = self.closest_case.to_dict()
        if self.packet_id is not None:
            out["packet_id"] = self.packet_id
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WitnessRecord":
        gates = tuple(
            GateResult(
                gate=g["gate"],
                status=g["status"],
                reasons=list(g.get("reasons", [])),
                details=g.get("details"),
            )
            for g in d.get("gate_results", [])
        )
        verifiers = tuple(
            VerifierResult(
                name=v["name"],
                status=v["status"],
                detail=v.get("detail", ""),
                data=v.get("data"),
            )
            for v in d.get("verifier_results", [])
        )
        anchors = tuple(Anchor.from_dict(a) for a in d.get("anchors", []))
        axis_coords = (
            AxisCoordinates.from_dict(d["axis_coords"])
            if "axis_coords" in d else None
        )
        closest_case = (
            ClosestCase.from_dict(d["closest_case"])
            if "closest_case" in d else None
        )
        return cls(
            overall=d["overall"],
            gate_results=gates,
            verifier_results=verifiers,
            anchors=anchors,
            axis_coords=axis_coords,
            closest_case=closest_case,
            packet_id=d.get("packet_id"),
            schema_version=d.get("schema_version", "1.0"),
        )

    # ── witness-verifier handoff ──────────────────────────────────────

    def to_wit_verify_block(self) -> Dict[str, Any]:
        """Build the WIT_VERIFY block this record would be checked
        against. Used by the witness verifier and by integration tests
        that round-trip a record through validation.
        """
        return {
            "claimed_gate_verdicts": [
                {"gate": gr.gate, "status": gr.status}
                for gr in self.gate_results
            ],
            "claimed_verifier_results": [
                {
                    "name": v.name,
                    "status": v.status,
                    "data": v.data,
                    "message": v.detail,
                }
                for v in self.verifier_results
            ],
            "claimed_anchors": [a.to_dict() for a in self.anchors],
            "declared_no_answer": True,
        }


# ── Builder ────────────────────────────────────────────────────────────

def build_record(
    *,
    engine_result: EngineResult,
    verifier_results: Tuple[VerifierResult, ...] = (),
    anchors: Tuple[Anchor, ...] = (),
    axis_coords: Optional[AxisCoordinates] = None,
    closest_case: Optional[ClosestCase] = None,
    packet_id: Optional[str] = None,
) -> WitnessRecord:
    """Assemble a WitnessRecord from engine output.

    The engine runs gates and dispatches verifiers; this function packs
    those plus the rendering-layer concerns (anchors, axis_coords,
    closest_case) into one sealed record. Future engine integration
    will call this from validate_packet; for now it's invoked by tests
    and downstream surfaces directly.
    """
    return WitnessRecord(
        overall=engine_result.overall,
        gate_results=tuple(engine_result.gate_results),
        verifier_results=tuple(verifier_results),
        anchors=tuple(anchors),
        axis_coords=axis_coords,
        closest_case=closest_case,
        packet_id=packet_id,
    )


def axis_coords_for(domain: str) -> Optional[AxisCoordinates]:
    """Look up grid coordinates for a domain, with umbrella detection.
    Returns None for domains not registered in the grid."""
    # Imported here to avoid a circular import at module load.
    from . import grid

    if domain not in grid.AXIS_DIMENSIONS:
        return None
    umbrella: Optional[str] = None
    for parent, children in grid.UMBRELLAS.items():
        if domain in children:
            umbrella = parent
            break
    return AxisCoordinates(
        axis=domain,
        dimensions=grid.AXIS_DIMENSIONS[domain],
        umbrella=umbrella,
    )
