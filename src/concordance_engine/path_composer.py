"""Path composer — final assembly layer of the standalone model.

Receives:
  - ClassificationResult (question type, confidence, gate)
  - Gate verdicts (from the existing four-gate engine)
  - RetrievalResult (Scripture anchors)
  - PersonalContext (personal ledger overlay)

Produces a structured path object per the spec §7:
  - question_type, confidence
  - gate_verdicts
  - scripture_anchor (primary + supporting)
  - personal_context
  - path (≤3 sentences)
  - next_step (singular — one thing, not a list)
  - timing (WAIT | HOLD | MOVE | UNCLEAR)

Constraints (per spec §7):
  - `path` is never more than three sentences
  - `next_step` is always singular
  - If any gate halts, path describes the gate failure only
  - Scripture anchor always present — if none found, returns "No anchor found"
  - Model does NOT give answers; it shows where to walk
  - The keeping is the substrate; the path points back to the text
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .classifier import (
    ClassificationResult,
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
    GATE_MAP,
)
from .scripture_retrieval import RetrievalResult, ScripturePassage
from .context_retriever import PersonalContext

# ── Data types ─────────────────────────────────────────────────────────

TIMING_WAIT  = "WAIT"
TIMING_HOLD  = "HOLD"
TIMING_MOVE  = "MOVE"
TIMING_UNCLEAR = "UNCLEAR"


@dataclass
class PathResult:
    """Structured path object returned by the path composer.

    This is what the user (or an agent) receives after all four components
    have run: classifier → Scripture retrieval → personal context →
    gate engine → path composer.
    """
    question_type: str
    confidence: float
    gate_verdicts: dict[str, str]           # {"RED": "PASS", "FLOOR": "PASS", ...}
    scripture_anchor: dict                  # {primary, text, supporting}
    personal_context: dict                  # {relevant_packets, pattern, precedent}
    path: str                               # ≤3 sentences
    next_step: str                          # singular — one thing
    timing: str                             # WAIT | HOLD | MOVE | UNCLEAR
    life_safety: bool = False               # True → "bring a witness now" fast path
    needs_clarification: bool = False       # True → prompt user before proceeding
    clarification_prompt: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "question_type": self.question_type,
            "confidence": round(self.confidence, 4),
            "gate_verdicts": self.gate_verdicts,
            "scripture_anchor": self.scripture_anchor,
            "personal_context": self.personal_context,
            "path": self.path,
            "next_step": self.next_step,
            "timing": self.timing,
            "life_safety": self.life_safety,
            "needs_clarification": self.needs_clarification,
            "clarification_prompt": self.clarification_prompt,
        }


# ── Gate verdict parsing ───────────────────────────────────────────────

def _gate_status(verdicts: dict[str, str], gate: str) -> str:
    """Return the status string for a gate, defaulting to UNKNOWN."""
    return verdicts.get(gate, "UNKNOWN")


def _any_gate_blocked(verdicts: dict[str, str]) -> tuple[bool, str, str]:
    """Return (blocked, gate_name, status) for the first blocked gate."""
    for gate in ("RED", "FLOOR", "BROTHERS", "GOD"):
        status = verdicts.get(gate, "PASS")
        if status not in ("PASS", "OK", "ok", "pass", ""):
            return True, gate, status
    return False, "", ""


# ── Path templates per type ────────────────────────────────────────────
# These are the composition templates — not answers, but path structures.
# Each entry is (path_template, next_step_template, timing).
# Templates use {anchor_ref} and {context_note} as interpolation slots.

_GATE_FAILURE_TEMPLATES: dict[str, tuple[str, str]] = {
    "RED": (
        "The RED gate is holding. The claim as submitted does not hold against "
        "external authority. Before the path can be traced, what failed must be named.",
        "Name what failed at the RED gate.",
    ),
    "FLOOR": (
        "The FLOOR gate is holding. There is a minimum being violated or unmet. "
        "The path cannot proceed until the floor beneath it is established.",
        "Establish what the floor requires.",
    ),
    "BROTHERS": (
        "The gate is holding at BROTHERS. The decision or situation requires witness. "
        "The path does not open until the right person has seen this.",
        "Name the witness.",
    ),
    "GOD": (
        "The GOD gate is holding. The timing is not yet clear. "
        "Everything below it holds. The next movement is to wait with open hands.",
        "Wait. Watch the signal you were given.",
    ),
}

_PATH_TEMPLATES: dict[str, tuple[str, str, str]] = {
    WISDOM: (
        "The question is one of understanding, not yet decision. "
        "The floor holds beneath it. "
        "{anchor_ref} is the starting place — read it slowly, not for information but for orientation.",
        "Read {anchor_ref} once today.",
        TIMING_UNCLEAR,
    ),
    DOCTRINE: (
        "The question is about what is true. "
        "The anchor is {anchor_ref}. "
        "What the text says is the ceiling; what any tradition says is subordinate to it.",
        "Read {anchor_ref} and let the text speak before consulting commentary.",
        TIMING_MOVE,
    ),
    DECISION: (
        "The decision is real and the floor holds beneath it. "
        "What is missing is witness — the BROTHERS gate requires another person to see this "
        "before it moves to timing. "
        "{context_note}",
        "Name the witness who should see this before you act.",
        TIMING_WAIT,
    ),
    RELATIONAL: (
        "The situation requires a witness who knows the parties. "
        "The path through Matthew 18 is not optional — it is the structure. "
        "{anchor_ref} names the order: go to them first, alone.",
        "Go to the person directly. Alone. First.",
        TIMING_MOVE,
    ),
    RESOURCE: (
        "The floor must hold before any resource decision is made. "
        "{anchor_ref} is the test: is the minimum being honored? "
        "After the floor holds, the allocation question opens.",
        "Check whether the floor is holding before allocating.",
        TIMING_UNCLEAR,
    ),
    TIMING: (
        "The question is timing, not direction. "
        "The direction is already held. "
        "{anchor_ref} is the anchor — there is a time for this, and it will arrive.",
        "Wait with open hands. Watch for the signal.",
        TIMING_WAIT,
    ),
    FORMATION: (
        "The question is about who you are becoming. "
        "Formation is not a single decision — it is a cycle of confession, renewal, and practice. "
        "{anchor_ref} names the mechanism: transformation happens by the renewing of the mind.",
        "Name the specific pattern. Write it. Then bring it to {anchor_ref}.",
        TIMING_UNCLEAR,
    ),
    CRISIS: (
        "The gate holds at FLOOR. "
        "The minimum is: you are not alone in this, and the Lord is near the brokenhearted. "
        "{anchor_ref} is where you stand right now.",
        "Read {anchor_ref} once. Then bring a human witness.",
        TIMING_WAIT,
    ),
    HISTORICAL: (
        "The question is about what happened and what it means. "
        "The attestation gate holds: the record is what it is. "
        "{anchor_ref} frames why the historical account exists: these things were written for our instruction.",
        "Read the account in the text before drawing conclusions from it.",
        TIMING_MOVE,
    ),
}


# ── Context note builder ───────────────────────────────────────────────

def _build_context_note(ctx: PersonalContext, question_type: str) -> str:
    """Build the personal context insertion for the path template."""
    if not ctx.has_history:
        return ""
    if ctx.pattern:
        return ctx.pattern
    if ctx.relevant_count == 2:
        return "This theme has appeared before. The pattern is beginning to form."
    return ""


# ── Life-safety path ───────────────────────────────────────────────────

_LIFE_SAFETY_PATH = PathResult(
    question_type=CRISIS,
    confidence=1.0,
    gate_verdicts={"RED": "PASS", "FLOOR": "HOLD", "BROTHERS": "REQUIRED", "GOD": "HOLD"},
    scripture_anchor={"primary": "Psalms 34:18", "text": "", "supporting": []},
    personal_context={"relevant_packets": 0, "pattern": None, "precedent": None},
    path=(
        "This is a life-safety situation. "
        "The only output is: bring a human witness now. "
        "Do not wait."
    ),
    next_step="Bring a human witness now.",
    timing=TIMING_WAIT,
    life_safety=True,
)


# ── Public API ─────────────────────────────────────────────────────────

def compose(
    classification: ClassificationResult,
    retrieval: RetrievalResult,
    context: PersonalContext,
    gate_verdicts: Optional[dict[str, str]] = None,
) -> PathResult:
    """Compose the final path object from all four components.

    Args:
        classification: Output of classify().
        retrieval:      Output of retrieve().
        context:        Output of retrieve_context().
        gate_verdicts:  Gate results from the existing engine. If None,
                        all gates are assumed to pass (for Phase 1 RAG mode
                        where the gate engine hasn't yet run on this submission).

    Returns:
        PathResult per spec §7.
    """
    # Life-safety fast path.
    if classification.life_safety:
        return _LIFE_SAFETY_PATH

    # Clarification required.
    if classification.needs_clarification:
        return PathResult(
            question_type=classification.primary_type,
            confidence=classification.confidence,
            gate_verdicts={},
            scripture_anchor=_no_anchor(),
            personal_context=context.to_dict(),
            path="The submission could not be classified with enough confidence to proceed.",
            next_step=_clarification_prompt(classification),
            timing=TIMING_UNCLEAR,
            needs_clarification=True,
            clarification_prompt=_clarification_prompt(classification),
        )

    # Normalize gate verdicts.
    if gate_verdicts is None:
        gate_verdicts = {"RED": "PASS", "FLOOR": "PASS", "BROTHERS": "PASS", "GOD": "PASS"}

    # Check for gate failures.
    blocked, blocked_gate, blocked_status = _any_gate_blocked(gate_verdicts)
    if blocked:
        path_text, next_step = _gate_failure_templates_for(blocked_gate, blocked_status)
        return PathResult(
            question_type=classification.primary_type,
            confidence=classification.confidence,
            gate_verdicts=gate_verdicts,
            scripture_anchor=_anchor_dict(retrieval),
            personal_context=context.to_dict(),
            path=path_text,
            next_step=next_step,
            timing=_timing_from_gate(blocked_gate),
        )

    # All gates clear — compose the type-specific path.
    qtype = classification.primary_type
    template = _PATH_TEMPLATES.get(qtype, _PATH_TEMPLATES[WISDOM])
    path_template, next_step_template, timing = template

    # Resolve interpolation slots.
    anchor_ref = retrieval.primary.ref if retrieval.primary else "Proverbs 2:6"
    context_note = _build_context_note(context, qtype)

    path_text = path_template.format(
        anchor_ref=anchor_ref,
        context_note=context_note or "Bring this before a witness before moving forward.",
    )
    next_step = next_step_template.format(anchor_ref=anchor_ref)

    return PathResult(
        question_type=qtype,
        confidence=classification.confidence,
        gate_verdicts=gate_verdicts,
        scripture_anchor=_anchor_dict(retrieval),
        personal_context=context.to_dict(),
        path=path_text.strip(),
        next_step=next_step.strip(),
        timing=timing,
    )


# ── Helpers ────────────────────────────────────────────────────────────

def _anchor_dict(retrieval: RetrievalResult) -> dict:
    """Build the scripture_anchor sub-object."""
    if not retrieval.primary:
        return {"primary": "No anchor found", "text": "", "supporting": []}
    return {
        "primary": retrieval.primary.ref,
        "text": retrieval.primary.text,
        "supporting": [p.ref for p in retrieval.supporting],
    }


def _no_anchor() -> dict:
    return {"primary": "No anchor found", "text": "", "supporting": []}


def _gate_failure_templates_for(gate: str, status: str) -> tuple[str, str]:
    """Return (path_text, next_step) for a gate failure."""
    template = _GATE_FAILURE_TEMPLATES.get(gate, _GATE_FAILURE_TEMPLATES["RED"])
    # Append the specific status if it carries diagnostic information.
    path_text = template[0]
    if status and status.upper() not in ("QUARANTINE", "REJECT", "HOLD", "WAIT"):
        path_text = path_text.rstrip(".") + f". Gate status: {status}."
    return path_text, template[1]


def _timing_from_gate(gate: str) -> str:
    return {
        "RED": TIMING_UNCLEAR,
        "FLOOR": TIMING_WAIT,
        "BROTHERS": TIMING_WAIT,
        "GOD": TIMING_HOLD,
    }.get(gate, TIMING_UNCLEAR)


def _clarification_prompt(classification: ClassificationResult) -> str:
    """Generate a clarification prompt when confidence is below threshold."""
    s = classification.secondary_type
    p = classification.primary_type
    if s:
        return (
            f"The submission could be a {p.title()} question or a {s.title()} question. "
            f"Which is closer to what you are carrying right now?"
        )
    return (
        f"The submission was classified as a {p.title()} question with low confidence. "
        f"Can you say more about what you are actually asking?"
    )
