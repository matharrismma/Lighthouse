"""journal.py — The calibration surface of the coach module.

Stream of consciousness in. Calibration out. **Nothing replaces
what you wrote.**

Per Matt 2026-05-03 (in two pieces):

  *"It's a calibration tool for humans."*

  *"The coach module is a core. We are coaching and programming.
   We take their disorder and make order. We allow them to tap into
   what makes them special. We are the conduit."*

This module is one surface of the coach module's relational plane
(per Coach Fractal OS: Main plane = Coach + Scribe, captures and
suggests; Steward plane is sovereign-gate). The journal is where
the Scribe captures stream-of-consciousness writing and the Coach
reads the categorization back to the user — order from disorder.

The engine is the conduit. It does not generate the user's voice,
does not speak for them, does not produce verdicts on what they
wrote. It reads what's there. It surfaces what shape the writing
carries and where it sits in their own pattern. The user does the
deciding.

What "tap into what makes them special" looks like in code: the
calibration measurements name the user's *recurring* anchors, their
*dominant* action shapes, their *characteristic* tempo. These are
the user's signal — what they uniquely keep returning to. The engine
helps them hear it.

Per the Calibre canon export:

> Time is the witness.
> Drift is inevitable.
> Reset is mercy.
> Constraint reveals alignment.
> Interruption invites return.
> Fruit confirms obedience.

The engine reads each entry and *measures* — like a watch
calibration reports "the second hand is 3 ticks fast," not "this
hour was good or bad." Calibration is descriptive, not prescriptive.
It surfaces:

  * **Drift** — how this entry differs from recent ones (scope
    shifts, anchor changes, action-shape oscillation)
  * **Pattern** — the shape across entries ("4 Open-shape entries
    in 3 weeks, 0 Build-shape" — the engine notes the pattern)
  * **Anchor stability** — which Scripture refs the user returns to
  * **Tempo** — silence between entries is itself observation

Design principles:

  * **Text is sacred.** A journal entry's `text` field is preserved
    verbatim, never summarized, never paraphrased, never compressed.
    Categorization is *additive* metadata.
  * **Categorization is hypothesis.** The engine's reads are stored
    as `detected_*` fields. They name what shape the engine *thinks*
    it heard. The user can override via `user_tags` or `annotations`.
  * **Pre-gate.** Journal entries don't go through the four gates.
    They're the raw material from which packets *may* later be
    extracted. Capture is upstream of decision.
  * **Listens, doesn't speak.** The engine surfaces what it heard +
    what closest precedents look like. It does not produce verdicts,
    answers, or directives on journal text. Per the keeping doctrine
    ("the keeping is the substrate"), the journal is *kept*; what
    happens to it next is the human's call.

Persistence is file-backed: one JSON per entry under `lw/journal/`,
parallel to the audit chain (`lw/ledger/`), the quarantine airlock
(`lw/quarantine/`), and the keeping log (`lw/keeping/`). Override
via the `CONCORDANCE_JOURNAL_DIR` environment variable.

How it integrates with the rest of the engine:
  * **Anchors** detected in the text resolve through the scripture
    verifier — same code path as packet anchors.
  * **Closest precedents** are surfaced via the existing
    `find_closest()` lookup against the audit chain.
  * **Keeping log** records each capture as a `journal_capture`
    observation — the writing event itself becomes part of what
    the keeping kept.
  * **nl_to_packet** templates are tried opportunistically. If the
    text matches a known claim shape (chemistry equation, p-value,
    derivative), that's surfaced — but the journal entry is still
    kept as text. The packet is a hypothesis, not a transformation.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Locations ────────────────────────────────────────────────────────


def _default_journal_dir() -> Path:
    """Repo-root `lw/journal/` by default; overridable via env var."""
    override = os.environ.get("CONCORDANCE_JOURNAL_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "lw" / "journal"


def _new_id() -> str:
    return f"j-{uuid.uuid4().hex[:12]}"


def _now() -> float:
    return time.time()


# ── Categorization (additive metadata, never replacing text) ─────────


# Personal-scale action verbs the engine listens for. Maps to the
# canonical four kernel actions (Reserve / Build / Open / Hold) plus
# Confess / Prune as the engine's confession path.
_ACTION_HINTS: Dict[str, List[str]] = {
    "Reserve":  ["save", "set aside", "hold back", "keep for", "reserve",
                 "firstfruit", "tithe", "store", "put away"],
    "Build":    ["build", "extend", "add to", "grow", "strengthen",
                 "develop", "improve", "expand"],
    "Open":     ["start", "begin", "open", "create", "launch",
                 "introduce", "establish", "found", "plant"],
    "Hold":     ["wait", "hold", "pause", "delay", "not yet",
                 "give it time", "discern"],
    "Prune":    ["stop", "end", "cut", "remove", "let go", "give up",
                 "confess", "repent", "release", "drop"],
}


# Scope hints. These are heuristic — first-person singular pronouns
# suggest personal scope; family/team/community language elevates.
_SCOPE_HINTS: Dict[str, List[str]] = {
    "personal":  [r"\bi\b", r"\bme\b", r"\bmy\b", r"\bmyself\b"],
    "family":    [r"\bmy (wife|husband|spouse|partner|kids?|children|sons?|"
                  r"daughters?|family|home)\b", r"\bour (family|home|kids?|"
                  r"children)\b"],
    "team":      [r"\bmy (team|coworkers?|colleagues?|crew)\b",
                  r"\bour (team|crew|company|business)\b"],
    "community": [r"\bmy (church|community|neighborhood|congregation)\b",
                  r"\bour (church|community|neighborhood)\b"],
    "region":    [r"\b(county|region|state|nation)\b"],
}


# Reference pattern reused from the scripture verifier — book + chapter
# (+ optional verse).
_REF_RE = re.compile(
    r"\b(?:[1-3]\s*)?[A-Z][a-z]{1,3}\.?"        # book (Mt, Mat, Matt, Pr, Prov…)
    r"\s*\d{1,3}"                                # chapter
    r"(?::\d{1,3}(?:-\d{1,3})?)?"                # optional :verse(-end)
)


@dataclass
class Categorization:
    """The engine's read of the entry. All fields are *hypotheses*.

    Empty list / None for any field means "the engine didn't recognize
    a [field] in this text" — not "this entry has none." Absence is
    explicit, never implicit.
    """
    detected_anchors: List[str] = field(default_factory=list)
    detected_action_shapes: List[str] = field(default_factory=list)
    detected_scope: Optional[str] = None
    detected_packet_shape: Optional[str] = None
    detected_packet_confidence: float = 0.0
    closest_precedent_id: Optional[str] = None
    closest_precedent_distance: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Categorization":
        return cls(
            detected_anchors=list(d.get("detected_anchors") or []),
            detected_action_shapes=list(d.get("detected_action_shapes") or []),
            detected_scope=d.get("detected_scope"),
            detected_packet_shape=d.get("detected_packet_shape"),
            detected_packet_confidence=float(d.get("detected_packet_confidence", 0.0)),
            closest_precedent_id=d.get("closest_precedent_id"),
            closest_precedent_distance=d.get("closest_precedent_distance"),
        )


def categorize(text: str) -> Categorization:
    """Listen to the text. Return what the engine recognized.

    Pure function — no side effects, no persistence, no I/O against
    the audit chain. Caller wraps with `capture()` to persist + look
    up precedents.

    Detection passes (each independent, none destructive):
      1. Scripture refs (book + chapter pattern).
      2. Action-shape hints (Reserve / Build / Open / Hold / Prune).
      3. Scope hints (personal / family / team / community / region).
      4. Packet-shape via nl_to_packet templates (if any matches).
    """
    if not text or not text.strip():
        return Categorization()

    # 1. Scripture anchors — surface raw matches; engine doesn't
    # validate them against WEB at this layer (that's a separate
    # walkthrough step the user can opt into).
    raw_refs = _REF_RE.findall(text)
    detected_anchors: List[str] = []
    seen = set()
    for r in raw_refs:
        cleaned = r.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            detected_anchors.append(cleaned)

    # 2. Action shapes
    lower = text.lower()
    detected_action_shapes: List[str] = []
    for shape, hints in _ACTION_HINTS.items():
        if any(h in lower for h in hints):
            detected_action_shapes.append(shape)

    # 3. Scope — pick the most-specific match (region > community >
    # team > family > personal). Keep the broadest visible.
    detected_scope: Optional[str] = None
    for scope, patterns in _SCOPE_HINTS.items():
        if any(re.search(p, lower) for p in patterns):
            detected_scope = scope
            # Don't break — we want the most-specific match, which
            # is the one we hit LAST since dict iteration order is
            # insertion order (personal → region by specificity-going-up).
    # Re-evaluate: we want most specific (highest specificity = region),
    # but the loop above keeps overwriting, so the last hit wins.
    # That gives us the most-specific match because the dict is
    # ordered personal → family → team → community → region.

    # 4. nl_to_packet template attempt — opportunistic. Don't crash
    # if the parser fails for any reason; the journal still captures.
    detected_packet_shape: Optional[str] = None
    detected_packet_confidence: float = 0.0
    try:
        from .nl_to_packet import parse as _nl_parse
        result = _nl_parse(text)
        if result is not None:
            detected_packet_shape = getattr(result, "template", None)
            detected_packet_confidence = float(
                getattr(result, "confidence", 0.0)
            )
    except Exception:
        # Categorization is best-effort. A parser failure should never
        # block the capture.
        pass

    return Categorization(
        detected_anchors=detected_anchors,
        detected_action_shapes=detected_action_shapes,
        detected_scope=detected_scope,
        detected_packet_shape=detected_packet_shape,
        detected_packet_confidence=detected_packet_confidence,
    )


# ── Annotation (later additions to an entry) ─────────────────────────


@dataclass
class Annotation:
    """A note added to an entry after the original capture. The
    original text is never mutated — annotations chain onto it."""
    note: str
    timestamp: float = 0.0
    author: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── JournalEntry ─────────────────────────────────────────────────────


@dataclass
class JournalEntry:
    """One stream-of-consciousness entry. Text is sacred."""
    id: str
    text: str
    written_at: float
    modified_at: float
    user_tags: List[str] = field(default_factory=list)
    annotations: List[Annotation] = field(default_factory=list)
    categorization: Categorization = field(default_factory=Categorization)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "text": self.text,
            "written_at": self.written_at,
            "modified_at": self.modified_at,
            "user_tags": list(self.user_tags),
            "annotations": [a.to_dict() for a in self.annotations],
            "categorization": self.categorization.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "JournalEntry":
        annotations = []
        for a in d.get("annotations", []) or []:
            if isinstance(a, dict):
                annotations.append(Annotation(
                    note=a.get("note", ""),
                    timestamp=float(a.get("timestamp", 0.0)),
                    author=a.get("author", ""),
                ))
        cat_data = d.get("categorization") or {}
        return cls(
            id=d["id"],
            text=d.get("text", ""),
            written_at=float(d.get("written_at", 0.0)),
            modified_at=float(d.get("modified_at", 0.0)),
            user_tags=list(d.get("user_tags", []) or []),
            annotations=annotations,
            categorization=Categorization.from_dict(cat_data),
        )


# ── Store ────────────────────────────────────────────────────────────


class JournalStore:
    """File-backed journal entry store. One JSON per entry."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or _default_journal_dir()

    def _ensure_dir(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir

    def save(self, entry: JournalEntry) -> Path:
        d = self._ensure_dir()
        target = d / f"{entry.id}.json"
        target.write_text(
            json.dumps(entry.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    def load(self, entry_id: str) -> Optional[JournalEntry]:
        f = self.base_dir / f"{entry_id}.json"
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return JournalEntry.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def list_all(
        self,
        *,
        since: Optional[float] = None,
        tag: Optional[str] = None,
    ) -> List[JournalEntry]:
        if not self.base_dir.exists():
            return []
        out: List[JournalEntry] = []
        for f in sorted(self.base_dir.glob("j-*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                entry = JournalEntry.from_dict(data)
            except (OSError, json.JSONDecodeError, KeyError):
                continue
            if since is not None and entry.written_at < since:
                continue
            if tag is not None and tag not in entry.user_tags:
                continue
            out.append(entry)
        # Newest first — most recent writing is most relevant first read.
        out.sort(key=lambda e: e.written_at, reverse=True)
        return out

    def delete(self, entry_id: str) -> bool:
        f = self.base_dir / f"{entry_id}.json"
        if f.exists():
            f.unlink()
            return True
        return False


# ── Capture / annotate / thread ──────────────────────────────────────


def capture(
    text: str,
    *,
    tags: Optional[List[str]] = None,
    store: Optional[JournalStore] = None,
    look_up_precedent: bool = True,
) -> JournalEntry:
    """Capture a stream-of-consciousness entry. Categorization runs
    additively; the original text is preserved.

    Optional precedent lookup against the audit chain — defaults on
    because closest-case overlay is part of the journal's value.

    Persists to the journal store (defaults to `lw/journal/`).
    Emits a keeping-log observation so the writing event itself is
    part of what the keeping kept.
    """
    if not text or not text.strip():
        raise ValueError("cannot capture empty text")

    now = _now()
    entry = JournalEntry(
        id=_new_id(),
        text=text,
        written_at=now,
        modified_at=now,
        user_tags=list(tags or []),
        categorization=categorize(text),
    )

    # Optional closest-precedent lookup. We synthesize a minimal packet
    # from the categorization so `find_closest` can match against the
    # audit chain's scaffold dimensions.
    if look_up_precedent and entry.categorization.detected_packet_shape:
        try:
            from .ledger import find_closest
            stub_packet: Dict[str, Any] = {}
            if entry.categorization.detected_anchors:
                stub_packet["scripture_anchors"] = list(
                    entry.categorization.detected_anchors
                )
            if entry.categorization.detected_packet_shape:
                stub_packet["domain"] = entry.categorization.detected_packet_shape
            if stub_packet:
                cc = find_closest(stub_packet)
                if cc is not None and cc.precedent_id is not None:
                    entry.categorization.closest_precedent_id = cc.precedent_id
                    entry.categorization.closest_precedent_distance = cc.distance
        except Exception:
            # Audit chain access is best-effort. A capture is more
            # important than a precedent lookup.
            pass

    store = store or JournalStore()
    store.save(entry)

    # Notify the keeping that a writing event happened. Soft — best
    # effort; if keeping isn't reachable for any reason, the capture
    # still lands.
    try:
        from .keeping import KeepingLog, KeepingObservation
        log = KeepingLog()
        log.append(KeepingObservation(
            practice="journal_capture",
            started_at=now,
            duration_seconds=0.0,
            kept={
                "entry_id": entry.id,
                "text_length": len(text),
                "detected_anchors": list(entry.categorization.detected_anchors),
                "detected_actions": list(entry.categorization.detected_action_shapes),
                "scope": entry.categorization.detected_scope,
            },
        ))
    except Exception:
        pass

    return entry


def annotate(
    entry_id: str,
    note: str,
    *,
    author: str = "",
    store: Optional[JournalStore] = None,
) -> Optional[JournalEntry]:
    """Add an annotation to an existing entry. The original text and
    original categorization are preserved; the annotation appends to
    the entry's chain. Returns the updated entry, or None if the
    entry isn't found."""
    store = store or JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return None
    if not note or not note.strip():
        raise ValueError("annotation note cannot be empty")
    entry.annotations.append(Annotation(
        note=note,
        timestamp=_now(),
        author=author,
    ))
    entry.modified_at = _now()
    store.save(entry)
    return entry


def thread(
    entry_id: str,
    *,
    store: Optional[JournalStore] = None,
) -> List[JournalEntry]:
    """Find entries that share categorizations with the given entry.

    Two entries are 'in the same thread' if they share at least one
    of: a detected anchor, an action shape, a scope. The returned
    list is newest-first and excludes the source entry.
    """
    store = store or JournalStore()
    source = store.load(entry_id)
    if source is None:
        return []

    src_anchors = set(source.categorization.detected_anchors)
    src_actions = set(source.categorization.detected_action_shapes)
    src_scope = source.categorization.detected_scope

    matches: List[JournalEntry] = []
    for candidate in store.list_all():
        if candidate.id == source.id:
            continue
        cand_anchors = set(candidate.categorization.detected_anchors)
        cand_actions = set(candidate.categorization.detected_action_shapes)
        cand_scope = candidate.categorization.detected_scope

        shared_any = (
            (src_anchors & cand_anchors)
            or (src_actions & cand_actions)
            or (src_scope is not None and src_scope == cand_scope)
        )
        if shared_any:
            matches.append(candidate)

    return matches


# ── Calibration (drift / pattern / anchor / tempo against history) ──


@dataclass
class Calibration:
    """The engine's calibration read for a new entry against history.

    Like a watch's calibration report: descriptive measurement, not
    prescriptive verdict. Each field names a *measurement*; the
    user reads them and decides what (if anything) to do.

    All deltas are computed against the entries returned by
    `store.list_all()` excluding the entry being calibrated.
    """
    # Tempo
    seconds_since_previous: Optional[float] = None  # gap between this and last
    total_entries_to_date: int = 0
    entries_in_last_7_days: int = 0
    entries_in_last_30_days: int = 0

    # Scope drift — does the user's claimed scope differ from the
    # immediately previous entry? Both fields populated only when a
    # scope was detected on both sides.
    previous_scope: Optional[str] = None
    scope_shifted: bool = False

    # Anchor stability — which anchors recur across recent entries.
    # `recurring_anchors` contains anchors that appear in this entry
    # AND in at least one previous entry (a thread of return).
    recurring_anchors: List[str] = field(default_factory=list)
    anchors_first_appearance: List[str] = field(default_factory=list)

    # Action-shape pattern across the last 30 days. Counts the number
    # of recent entries matching each kernel action shape. If this
    # entry's action shape is significantly out of step with the
    # recent distribution, `action_pattern_note` describes it.
    action_shape_counts_30d: Dict[str, int] = field(default_factory=dict)
    action_pattern_note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calibrate(
    entry: JournalEntry,
    *,
    store: Optional[JournalStore] = None,
    now: Optional[float] = None,
) -> Calibration:
    """Calibrate a journal entry against the user's history.

    Pure read. Does not mutate the entry; does not write to disk.
    Caller can persist the calibration report alongside the entry,
    surface it in the CLI, or discard it.

    The semantic guarantee: every field of the returned `Calibration`
    is a *measurement*, not a judgment. The renderer is responsible
    for surfacing it without prescription.
    """
    store = store or JournalStore()
    now_epoch = now if now is not None else _now()

    # Pull all entries; we'll exclude the target entry from history.
    history = [e for e in store.list_all() if e.id != entry.id]

    # ── Tempo
    previous = history[0] if history else None  # newest-first ordering
    seconds_since_previous = (
        entry.written_at - previous.written_at if previous else None
    )

    seven_days_ago = now_epoch - (7 * 86400)
    thirty_days_ago = now_epoch - (30 * 86400)
    entries_in_last_7_days = sum(
        1 for e in history if e.written_at >= seven_days_ago
    )
    entries_in_last_30_days = sum(
        1 for e in history if e.written_at >= thirty_days_ago
    )

    # ── Scope drift
    previous_scope = (
        previous.categorization.detected_scope if previous else None
    )
    scope_shifted = bool(
        entry.categorization.detected_scope
        and previous_scope
        and entry.categorization.detected_scope != previous_scope
    )

    # ── Anchor stability
    historical_anchors: Dict[str, int] = {}
    for e in history:
        for ref in e.categorization.detected_anchors:
            historical_anchors[ref] = historical_anchors.get(ref, 0) + 1
    recurring_anchors: List[str] = []
    anchors_first_appearance: List[str] = []
    for ref in entry.categorization.detected_anchors:
        if historical_anchors.get(ref, 0) > 0:
            recurring_anchors.append(ref)
        else:
            anchors_first_appearance.append(ref)

    # ── Action-shape pattern (30-day window)
    action_counts: Dict[str, int] = {}
    for e in history:
        if e.written_at < thirty_days_ago:
            continue
        for shape in e.categorization.detected_action_shapes:
            action_counts[shape] = action_counts.get(shape, 0) + 1
    # Pattern note: if this entry's action shapes match the dominant
    # 30-day shape, no note. If they diverge, surface the divergence.
    action_pattern_note = ""
    current_shapes = set(entry.categorization.detected_action_shapes)
    if action_counts and current_shapes:
        # The dominant shape across the window.
        dominant_shape = max(action_counts, key=action_counts.get)
        if dominant_shape not in current_shapes:
            action_pattern_note = (
                f"Recent pattern leans {dominant_shape} "
                f"({action_counts[dominant_shape]} entries in last 30 days); "
                f"this entry's shape is {sorted(current_shapes)}."
            )
        elif len(current_shapes) > 1:
            action_pattern_note = (
                f"This entry holds multiple action shapes "
                f"({sorted(current_shapes)}). Recent dominant: "
                f"{dominant_shape}."
            )
    elif current_shapes and not history:
        action_pattern_note = "First entry; no history to calibrate against."

    return Calibration(
        seconds_since_previous=seconds_since_previous,
        total_entries_to_date=len(history) + 1,  # this entry counts
        entries_in_last_7_days=entries_in_last_7_days,
        entries_in_last_30_days=entries_in_last_30_days,
        previous_scope=previous_scope,
        scope_shifted=scope_shifted,
        recurring_anchors=recurring_anchors,
        anchors_first_appearance=anchors_first_appearance,
        action_shape_counts_30d=action_counts,
        action_pattern_note=action_pattern_note,
    )


# ── Render a calibration report (human-readable) ─────────────────────


def render_calibration(entry: JournalEntry, calibration: Calibration) -> str:
    """Render the calibration measurement as a short markdown block.

    Designed to fit at the foot of a capture session — what the
    engine heard, where this sits relative to recent entries.
    Resolutely descriptive: never prescribes.
    """
    lines: List[str] = []
    lines.append("## What the engine kept of your writing")
    lines.append("")

    # What was heard (categorization, not paraphrase)
    cat = entry.categorization
    if cat.detected_anchors:
        lines.append(f"- Anchors heard: {', '.join(f'`{a}`' for a in cat.detected_anchors)}")
    if cat.detected_action_shapes:
        lines.append(f"- Action shape(s): {', '.join(cat.detected_action_shapes)}")
    if cat.detected_scope:
        lines.append(f"- Scope: **{cat.detected_scope}**")
    if cat.detected_packet_shape:
        lines.append(
            f"- Recognized claim shape: `{cat.detected_packet_shape}` "
            f"(confidence {cat.detected_packet_confidence:.2f})"
        )
    if cat.closest_precedent_id:
        lines.append(
            f"- Closest precedent: `{cat.closest_precedent_id}`"
            + (f" (distance {cat.closest_precedent_distance})"
               if cat.closest_precedent_distance is not None else "")
        )
    if not any([cat.detected_anchors, cat.detected_action_shapes,
                cat.detected_scope, cat.detected_packet_shape]):
        lines.append("- _The engine recognized no specific shape in this entry. The text is kept._")

    # Calibration measurements
    lines.append("")
    lines.append("## Calibration")
    lines.append("")
    if calibration.total_entries_to_date == 1:
        lines.append("- This is your first entry. The keeping has begun.")
    else:
        lines.append(
            f"- Entry **#{calibration.total_entries_to_date}**; "
            f"{calibration.entries_in_last_7_days} in the last 7 days, "
            f"{calibration.entries_in_last_30_days} in the last 30."
        )
        if calibration.seconds_since_previous is not None:
            gap = calibration.seconds_since_previous
            if gap < 3600:
                gap_str = f"{gap / 60:.0f} minutes"
            elif gap < 86400:
                gap_str = f"{gap / 3600:.1f} hours"
            else:
                gap_str = f"{gap / 86400:.1f} days"
            lines.append(f"- {gap_str} since your previous entry.")

    if calibration.scope_shifted:
        lines.append(
            f"- Scope shifted: previous entry was at **{calibration.previous_scope}**; "
            f"this one is at **{entry.categorization.detected_scope}**."
        )

    if calibration.recurring_anchors:
        refs = ", ".join(f"`{a}`" for a in calibration.recurring_anchors)
        lines.append(f"- Anchors you've returned to: {refs}.")
    if calibration.anchors_first_appearance:
        refs = ", ".join(f"`{a}`" for a in calibration.anchors_first_appearance)
        lines.append(f"- Anchors first appearing in this entry: {refs}.")

    if calibration.action_pattern_note:
        lines.append(f"- {calibration.action_pattern_note}")

    return "\n".join(lines)


__all__ = [
    "Categorization",
    "Annotation",
    "JournalEntry",
    "JournalStore",
    "Calibration",
    "categorize",
    "calibrate",
    "render_calibration",
    "capture",
    "annotate",
    "thread",
]
