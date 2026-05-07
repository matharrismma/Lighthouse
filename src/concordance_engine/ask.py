"""ask.py — search-the-bank-or-create-a-new-seed.

Per Matt 2026-05-03 (in three pieces):

  *"We can also have an ask feature. It will search our seeds. It
   will create a seed if necessary. seed=packet."*

  *"We focus on what is not the answer. By elimination we illuminate
   the narrow path."*

  *"Good fruit is the measure. We focus on locating the good fruit
   and creating a clear path."*

`/ask` does NOT generate an answer. It walks the seed bank (audit
chain precedents + journal library + shelf) and returns what
survives elimination, ranked by fruit. The elimination trail itself
is the reasoning — surface what was *not* the answer, and what
survives is the narrow path.

If nothing survives elimination, the question itself becomes a new
seed (captured to the journal). The absence of a match is itself
information the engine keeps.

## Fruit scoring (positive doctrine, cataphatic)

A precedent's fruit is computed from observable signals:

  * **Survival without amendment.** If a sealed precedent has been
    cited / referenced as `prior_id` by an `amend_precedent` call,
    it has been refined — its raw form lost some fruit. Unamended
    precedents score higher.
  * **Recurring anchors.** If the precedent's anchors appear in
    multiple subsequent journal entries, it's a recurring touch
    point — fruit lives in the recurrence.
  * **Threading.** If the precedent's axis or dimensions appear in
    later journal entries (the user keeps coming back), the seed
    has spread.

Ranking is by `fruit_score` (higher = more fruit = clearer path).

## Elimination passes (negative doctrine, apophatic)

Each candidate from the seed bank goes through eliminations:

  1. **Axis mismatch.** Question's detected packet shape doesn't
     match candidate's axis.
  2. **Scope mismatch.** Question's scope and candidate's scope
     are mutually exclusive (e.g., `personal` vs `region`).
  3. **No anchor overlap.** When the question carries scripture
     anchors but the candidate carries none in common.

What survives all passes is the narrow path. The eliminated
candidates are returned alongside, with their rejection reasons,
so the reader can see the trail.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from . import journal as _journal
from . import ledger as _ledger


# ── Result types ────────────────────────────────────────────────────


@dataclass
class EliminatedCandidate:
    """A seed bank candidate that did NOT survive elimination,
    along with the reason it was eliminated."""
    source: str  # "audit_chain" or "journal"
    candidate_id: str
    reason: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SurvivingMatch:
    """A seed bank entry that survived elimination, with its fruit
    score and the signals that contributed to that score."""
    source: str  # "audit_chain" or "journal"
    candidate_id: str
    summary: str
    shared_signal: List[str]  # what made this a match (anchors, axis, scope)
    fruit_score: float
    fruit_signals: Dict[str, Any]  # raw signals contributing to score

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AskResult:
    """The engine's response to /ask. Apophatic + cataphatic together.

    `survivors` is the ranked path (most-fruitful first); `eliminated`
    is the trail of what was NOT the answer. If `survivors` is empty,
    `new_seed_id` will be set — the question itself was captured as
    a fresh seed in the user's library.
    """
    question: str
    survivors: List[SurvivingMatch] = field(default_factory=list)
    eliminated: List[EliminatedCandidate] = field(default_factory=list)
    new_seed_id: Optional[str] = None
    categorization: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "survivors": [s.to_dict() for s in self.survivors],
            "eliminated": [e.to_dict() for e in self.eliminated],
            "new_seed_id": self.new_seed_id,
            "categorization": self.categorization,
        }


# ── Fruit scoring ───────────────────────────────────────────────────


def _score_precedent_fruit(
    precedent: Dict[str, Any],
    *,
    all_precedents: List[Dict[str, Any]],
    all_entries: List[_journal.JournalEntry],
) -> tuple[float, Dict[str, Any]]:
    """Compute a fruit score for a sealed precedent.

    Components (each capped to keep total bounded):
      * +1.0 base for being sealed (it survived all four gates once)
      * +0.5 if unamended (no later precedent has `amends == this.id`)
      * +0.2 per other precedent citing this as `prior_id` (capped at +1.0)
      * +0.1 per journal entry whose anchors overlap with this
        precedent's anchors (capped at +1.0)
      * +0.05 per journal entry whose axis matches (capped at +0.5)
    """
    pid = precedent.get("precedent_id") or ""
    base_score = 1.0
    signals: Dict[str, Any] = {"sealed": True, "base": 1.0}

    # Unamended bonus
    amended = any(
        (other.get("amends") == pid) for other in all_precedents
    )
    if not amended:
        base_score += 0.5
        signals["unamended"] = True
    else:
        signals["unamended"] = False
        signals["amended_by_count"] = sum(
            1 for o in all_precedents if o.get("amends") == pid
        )

    # Citation count (other precedents amending toward this — refined-from)
    refined_from_count = sum(
        1 for o in all_precedents if o.get("amends") == pid
    )
    citation_bonus = min(refined_from_count * 0.2, 1.0)
    base_score += citation_bonus
    signals["citation_count"] = refined_from_count

    # Anchor overlap with journal entries (recurring-anchor signal)
    p_anchors = set()
    for a in precedent.get("anchors") or []:
        if isinstance(a, str):
            p_anchors.add(a)
        elif isinstance(a, dict) and a.get("ref"):
            p_anchors.add(a["ref"])

    anchor_overlap_count = 0
    if p_anchors:
        for entry in all_entries:
            entry_anchors = set(entry.categorization.detected_anchors or [])
            if entry_anchors & p_anchors:
                anchor_overlap_count += 1
    anchor_bonus = min(anchor_overlap_count * 0.1, 1.0)
    base_score += anchor_bonus
    signals["anchor_overlap_count"] = anchor_overlap_count

    # Axis match with journal entries
    axis = precedent.get("axis")
    axis_match_count = 0
    if axis:
        for entry in all_entries:
            if entry.categorization.detected_packet_shape == axis:
                axis_match_count += 1
    axis_bonus = min(axis_match_count * 0.05, 0.5)
    base_score += axis_bonus
    signals["axis_match_count"] = axis_match_count

    return base_score, signals


def _score_journal_fruit(
    entry: _journal.JournalEntry,
    *,
    all_entries: List[_journal.JournalEntry],
) -> tuple[float, Dict[str, Any]]:
    """Compute a fruit score for a journal seed.

    Lower-base than precedents (they haven't survived the gates yet),
    but threading and shelf publication elevate.

    Thread count is computed from the already-loaded ``all_entries``
    list (O(n) per entry, O(n²) total) rather than calling
    ``_journal.thread()`` which would do a full disk scan per entry.
    """
    base_score = 0.3  # journal entries start lower than sealed precedents
    signals: Dict[str, Any] = {"sealed": False, "base": 0.3}

    # Shelf bonus — community visibility means this seed has been
    # offered for others to reach for.
    if "shelf" in (entry.user_tags or []):
        base_score += 0.3
        signals["on_shelf"] = True

    # Threading bonus: how many other entries share signal with this one.
    # Computed in-memory from the pre-loaded all_entries to avoid O(n²)
    # disk I/O (formerly called _journal.thread(entry.id) per entry).
    src_anchors = set(entry.categorization.detected_anchors or [])
    src_actions = set(entry.categorization.detected_action_shapes or [])
    src_scope = entry.categorization.detected_scope
    thread_count = 0
    for other in all_entries:
        if other.id == entry.id:
            continue
        other_anchors = set(other.categorization.detected_anchors or [])
        other_actions = set(other.categorization.detected_action_shapes or [])
        if (
            (src_anchors and other_anchors and src_anchors & other_anchors)
            or (src_actions and other_actions and src_actions & other_actions)
            or (src_scope is not None
                and src_scope == other.categorization.detected_scope)
        ):
            thread_count += 1
    thread_bonus = min(thread_count * 0.1, 0.5)
    base_score += thread_bonus
    signals["thread_count"] = thread_count

    # Annotation bonus: an entry that's been returned to (annotated
    # later) has more fruit than one written once and forgotten.
    annotation_count = len(entry.annotations or [])
    base_score += min(annotation_count * 0.1, 0.3)
    signals["annotation_count"] = annotation_count

    return base_score, signals


# ── Elimination passes ──────────────────────────────────────────────


def _eliminate_precedent(
    precedent: Dict[str, Any],
    cat: _journal.Categorization,
) -> Optional[EliminatedCandidate]:
    """Return an EliminatedCandidate if this precedent fails any
    elimination pass; else None (the precedent survives)."""
    pid = precedent.get("precedent_id", "?")

    # Axis mismatch
    if cat.detected_packet_shape:
        axis = precedent.get("axis")
        if axis and axis != cat.detected_packet_shape:
            return EliminatedCandidate(
                source="audit_chain",
                candidate_id=pid,
                reason="axis_mismatch",
                detail=f"question shape={cat.detected_packet_shape}, "
                       f"precedent axis={axis}",
            )

    # Anchor passing: only require overlap when BOTH sides carry anchors.
    if cat.detected_anchors:
        p_anchors = set()
        for a in precedent.get("anchors") or []:
            if isinstance(a, str):
                p_anchors.add(a)
            elif isinstance(a, dict) and a.get("ref"):
                p_anchors.add(a["ref"])
        if p_anchors and not (set(cat.detected_anchors) & p_anchors):
            return EliminatedCandidate(
                source="audit_chain",
                candidate_id=pid,
                reason="no_anchor_overlap",
                detail=f"question anchors {sorted(cat.detected_anchors)} "
                       f"do not overlap precedent anchors {sorted(p_anchors)}",
            )

    return None


def _eliminate_journal_entry(
    entry: _journal.JournalEntry,
    cat: _journal.Categorization,
) -> Optional[EliminatedCandidate]:
    """Return an EliminatedCandidate if this journal entry fails any
    elimination pass; else None (it survives)."""
    eid = entry.id

    # Anchor passing: only when the question has anchors.
    if cat.detected_anchors:
        e_anchors = set(entry.categorization.detected_anchors or [])
        if e_anchors and not (set(cat.detected_anchors) & e_anchors):
            return EliminatedCandidate(
                source="journal",
                candidate_id=eid,
                reason="no_anchor_overlap",
                detail=f"question anchors {sorted(cat.detected_anchors)} "
                       f"do not overlap entry anchors {sorted(e_anchors)}",
            )

    # Scope mismatch — only eliminate when scopes are mutually
    # exclusive (e.g., region vs personal). Same scope or one-side-
    # absent is not elimination.
    if cat.detected_scope and entry.categorization.detected_scope:
        scopes_incompatible = (
            cat.detected_scope != entry.categorization.detected_scope
        )
        if scopes_incompatible:
            return EliminatedCandidate(
                source="journal",
                candidate_id=eid,
                reason="scope_mismatch",
                detail=f"question scope={cat.detected_scope}, "
                       f"entry scope={entry.categorization.detected_scope}",
            )

    return None


def _shared_signal(
    cat: _journal.Categorization,
    other_anchors: List[str],
    other_axis: Optional[str] = None,
    other_scope: Optional[str] = None,
    other_actions: Optional[List[str]] = None,
) -> List[str]:
    """List the signals that connect the question to a survivor."""
    shared: List[str] = []
    if cat.detected_anchors and other_anchors:
        common = set(cat.detected_anchors) & set(other_anchors)
        if common:
            shared.append("anchors:" + ",".join(sorted(common)))
    if (cat.detected_packet_shape and other_axis
            and cat.detected_packet_shape == other_axis):
        shared.append(f"axis:{other_axis}")
    if (cat.detected_scope and other_scope
            and cat.detected_scope == other_scope):
        shared.append(f"scope:{other_scope}")
    if cat.detected_action_shapes and other_actions:
        common_actions = set(cat.detected_action_shapes) & set(other_actions)
        if common_actions:
            shared.append("actions:" + ",".join(sorted(common_actions)))
    return shared


# ── Public API ──────────────────────────────────────────────────────


def ask(
    question: str,
    *,
    capture_if_no_survivors: bool = True,
    max_survivors: int = 5,
    max_eliminated: int = 10,
    max_journal_entries: int = 500,
    journal_store: Optional[_journal.JournalStore] = None,
    ledger_dir: Optional[Any] = None,
) -> AskResult:
    """Search the seed bank with elimination + fruit ranking.

    Returns an `AskResult` carrying the survivors (ranked by fruit),
    the elimination trail (what was NOT the answer, with reasons),
    and `new_seed_id` if the question itself was captured because
    nothing survived.

    ``max_journal_entries`` caps how many journal entries are scanned
    (most recent first). Default 500 keeps response times under 2s
    even on large corpora while covering all recently seeded domains.
    Set to 0 to disable the cap and scan everything.
    """
    if not question or not question.strip():
        raise ValueError("question cannot be empty")

    cat = _journal.categorize(question)
    journal_store = journal_store or _journal.JournalStore()

    all_precedents = _ledger.list_precedents(ledger_dir)
    limit = max_journal_entries if max_journal_entries > 0 else None
    all_entries = journal_store.list_all(limit=limit)

    eliminated: List[EliminatedCandidate] = []
    surviving: List[SurvivingMatch] = []

    # ── Pass 1: eliminate audit-chain precedents that don't fit
    surviving_precedents: List[Dict[str, Any]] = []
    for p in all_precedents:
        e = _eliminate_precedent(p, cat)
        if e is not None:
            eliminated.append(e)
        else:
            surviving_precedents.append(p)

    # ── Pass 2: eliminate journal entries that don't fit
    surviving_entries: List[_journal.JournalEntry] = []
    for entry in all_entries:
        e = _eliminate_journal_entry(entry, cat)
        if e is not None:
            eliminated.append(e)
        else:
            surviving_entries.append(entry)

    # ── Score survivors by fruit and assemble the path
    for p in surviving_precedents:
        score, signals = _score_precedent_fruit(
            p, all_precedents=all_precedents, all_entries=all_entries,
        )
        p_anchors = []
        for a in p.get("anchors") or []:
            if isinstance(a, str):
                p_anchors.append(a)
            elif isinstance(a, dict) and a.get("ref"):
                p_anchors.append(a["ref"])
        surviving.append(SurvivingMatch(
            source="audit_chain",
            candidate_id=p.get("precedent_id", "?"),
            summary=p.get("summary", "(no summary)"),
            shared_signal=_shared_signal(
                cat,
                other_anchors=p_anchors,
                other_axis=p.get("axis"),
            ),
            fruit_score=score,
            fruit_signals=signals,
        ))

    for entry in surviving_entries:
        score, signals = _score_journal_fruit(
            entry, all_entries=all_entries,
        )
        # Skip self-matches (if the question was previously captured
        # verbatim, the engine shouldn't surface that to itself).
        if entry.text.strip() == question.strip():
            continue
        surviving.append(SurvivingMatch(
            source="journal",
            candidate_id=entry.id,
            summary=entry.text[:80] + ("..." if len(entry.text) > 80 else ""),
            shared_signal=_shared_signal(
                cat,
                other_anchors=entry.categorization.detected_anchors or [],
                other_axis=entry.categorization.detected_packet_shape,
                other_scope=entry.categorization.detected_scope,
                other_actions=entry.categorization.detected_action_shapes or [],
            ),
            fruit_score=score,
            fruit_signals=signals,
        ))

    # Sort survivors: most fruit first.
    surviving.sort(key=lambda s: s.fruit_score, reverse=True)
    survivors_capped = surviving[:max_survivors]

    # ── If nothing survived, capture the question as a new seed.
    new_seed_id: Optional[str] = None
    if not surviving and capture_if_no_survivors:
        try:
            new_entry = _journal.capture(question, tags=["from_ask"])
            new_seed_id = new_entry.id
        except ValueError:
            pass

    return AskResult(
        question=question,
        survivors=survivors_capped,
        eliminated=eliminated[:max_eliminated],
        new_seed_id=new_seed_id,
        categorization=cat.to_dict() if cat else None,
    )


def render_ask(result: AskResult) -> str:
    """Render an AskResult as human-readable markdown.

    Honors the doctrinal commitments:
      * Surface what was eliminated AND why (apophatic)
      * Rank survivors by fruit (cataphatic)
      * Never produce an answer; always end on the user's move
    """
    lines: List[str] = []
    lines.append("## Question")
    lines.append("")
    lines.append(f"> {result.question}")
    lines.append("")

    if result.survivors:
        lines.append("## What survived elimination (ranked by fruit)")
        lines.append("")
        for i, s in enumerate(result.survivors, 1):
            lines.append(
                f"### {i}. `{s.candidate_id}` ({s.source})"
            )
            lines.append(f"_{s.summary}_")
            lines.append("")
            lines.append(f"- fruit score: **{s.fruit_score:.2f}**")
            if s.shared_signal:
                lines.append(f"- shared signal: {', '.join(f'`{x}`' for x in s.shared_signal)}")
            if s.fruit_signals:
                signals_str = ", ".join(
                    f"{k}={v}" for k, v in s.fruit_signals.items()
                )
                lines.append(f"- signals: {signals_str}")
            lines.append("")
    elif result.new_seed_id:
        lines.append("## Nothing in the bank matched this shape")
        lines.append("")
        lines.append(
            f"The question itself was kept as a new seed: "
            f"`{result.new_seed_id}`. The absence of a match is itself "
            f"information; the engine keeps the question for future "
            f"elimination passes."
        )
        lines.append("")
    else:
        lines.append("## Nothing in the bank matched this shape")
        lines.append("")

    if result.eliminated:
        lines.append("## What was eliminated (and why)")
        lines.append("")
        for e in result.eliminated:
            lines.append(
                f"- `{e.candidate_id}` ({e.source}) — "
                f"**{e.reason}** — {e.detail}"
            )
        lines.append("")

    lines.append("## The next move is yours")
    lines.append("")
    if result.survivors:
        lines.append(
            "The path above survived elimination and ranks by fruit. "
            "The engine does not declare it the answer — it is what is "
            "left when what is not the answer has been removed."
        )
    elif result.new_seed_id:
        lines.append(
            "The seed bank has not seen this shape before. The question "
            "is now in your library; you can publish it to the shelf, "
            "annotate it as you learn, or ask again later when more "
            "seeds have been planted."
        )
    else:
        lines.append("Nothing emerged. Try a clearer shape or anchor.")
    lines.append("")

    return "\n".join(lines)


__all__ = [
    "ask",
    "render_ask",
    "AskResult",
    "SurvivingMatch",
    "EliminatedCandidate",
]
