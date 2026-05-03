"""Phase verifier — Setup → Positioning → Conversion (canonical).

Per 00_CANON/PHASES_SETUP_POSITIONING_CONVERSION.md, every decision
or execution sits in one of three canonical phases:

  * **Setup** — Secure base. Define arena. Develop capacity. Avoid
    early loss. Packets in Setup are typically reversible, low-stakes,
    capacity-building.

  * **Positioning** — Build dominant positions. Apply the longest
    levers. Reduce complexity. Funnel opponents into asymmetry. Win
    position before outcome.

  * **Conversion** — Lock in gains. Remove counterplay. Simplify when
    ahead. Make results irreversible.

This verifier runs cross-cuttingly (like scripture). When a packet
declares `phase`, it classifies the packet and emits a CONFIRMED
result with the canonical guidance for that phase. Without `phase`,
the verifier emits NOT_APPLICABLE — phase metadata is optional in V1.

Future iterations can add phase-aware enforcement: e.g. Conversion-
phase packets requiring stronger witness counts, longer wait windows,
or explicit scripture anchors. For now, the verifier surfaces phase
as a structured classification so humans and agents can reason about
where in the decision lifecycle a packet sits.

Anchored in canonical phase language; no specific scripture ref
because the phase doctrine is general wisdom expressed across many
passages (Prov 24:27 "prepare your work outside" for setup, 1 Cor
9:24-26 for positioning, Phil 3:14 "press on" for conversion).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_PHASES = ("setup", "positioning", "conversion")

_PHASE_GUIDANCE = {
    "setup": (
        "Secure base. Define arena. Develop capacity. Avoid early "
        "loss. Decisions in Setup should be reversible, low-stakes, "
        "and oriented toward building capacity rather than committing "
        "to outcomes."
    ),
    "positioning": (
        "Build dominant positions. Apply the longest levers. Reduce "
        "complexity. Win position before outcome. Decisions in "
        "Positioning should reduce future complexity, not increase it."
    ),
    "conversion": (
        "Lock in gains. Remove counterplay. Simplify when ahead. Make "
        "results irreversible. Decisions in Conversion are the binding "
        "kind — Conversion is where the wait window matters most and "
        "the witness count should be highest."
    ),
}

_PHASE_ANCHOR = {
    "ref": "Prov 24:27",
    "layer": "bible",
    "derivation": (
        "Phase order: 'Prepare your work outside; get everything ready "
        "for yourself in the field, and after that build your house.' "
        "Setup precedes Positioning precedes Conversion. Order matters: "
        "skipping phases (or executing out of order) is the haste "
        "Prov 19:2 warns against."
    ),
}


def verify_phase(packet: Dict[str, Any]) -> VerifierResult:
    """Classify the packet by declared phase. Informational in V1."""
    name = "phase.classification"
    phase = packet.get("phase")
    if phase is None:
        return na(name, "no phase declared (optional metadata)")
    if not isinstance(phase, str):
        return error(
            name,
            f"phase must be a string, got {type(phase).__name__}",
            {"anchor": _PHASE_ANCHOR},
        )
    phase_normalized = phase.lower().strip()
    if phase_normalized not in _PHASES:
        return mismatch(
            name,
            f"phase {phase!r} is not one of {_PHASES}",
            {
                "anchor": _PHASE_ANCHOR,
                "rule": (
                    "phase must be one of the canonical three: "
                    "setup, positioning, conversion (Prov 24:27 — "
                    "phase order matters)"
                ),
                "given_phase": phase,
                "valid_phases": list(_PHASES),
            },
        )
    return confirm(
        name,
        f"phase classified as '{phase_normalized}'",
        {
            "anchor": _PHASE_ANCHOR,
            "rule": (
                "phase metadata classifies where in the decision "
                "lifecycle this packet sits (Setup → Positioning → "
                "Conversion). Future iterations may apply phase-aware "
                "verifier behavior; V1 is informational."
            ),
            "phase": phase_normalized,
            "guidance": _PHASE_GUIDANCE[phase_normalized],
        },
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Cross-cutting: runs on every packet, NA if no phase declared."""
    return [verify_phase(packet)]
