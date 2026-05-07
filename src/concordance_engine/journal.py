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

# Task-shape phrases — first-person and imperative cues that suggest a
# to-do item buried in the stream of consciousness.
_TASK_PATTERNS = [
    re.compile(r"\b(?:i\s+(?:need|have|want|got)\s+to|i\s+should|i'?ll\s+(?:need\s+to|have\s+to))\s+([^.!?\n]{2,80})", re.IGNORECASE),
    re.compile(r"\b(?:don't\s+forget\s+to|remember\s+to|make\s+sure\s+to|gotta)\s+([^.!?\n]{2,80})", re.IGNORECASE),
    re.compile(r"\b(?:todo|to-do|to\s+do)\s*[:\-]\s*([^.!?\n]{2,80})", re.IGNORECASE),
    re.compile(r"^\s*[\-\*•]\s+([^.!?\n]{2,80})", re.MULTILINE),  # bulleted lines
]

# Date / calendar shapes — explicit dates, day names, relative references.
_DATE_PATTERNS = [
    # Full dates: 2026-05-03, 5/3/26, May 3, May 3rd, 3 May
    re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b"),
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?\b", re.IGNORECASE),
    re.compile(r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\b", re.IGNORECASE),
    # Day names
    re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:Mon|Tue|Tues|Wed|Thu|Thur|Thurs|Fri|Sat|Sun)\b", re.IGNORECASE),
    # Relative-time markers that anchor planning
    re.compile(r"\b(?:today|tomorrow|tonight|yesterday)\b", re.IGNORECASE),
    re.compile(r"\b(?:next|this|last)\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday|morning|evening)\b", re.IGNORECASE),
    re.compile(r"\bin\s+\d+\s+(?:days?|weeks?|months?|years?)\b", re.IGNORECASE),
]

# Person mentions — capitalized first names following relational
# verbs / prepositions ("met with Sarah", "Sarah's birthday", "from
# Bob"). Heuristic; not a real NER pass. The engine never claims this
# is exhaustive.
# Inline (?i:...) flag groups make the prefix case-insensitive while
# the captured NAME group remains required-capitalized — distinguishing
# proper names from common nouns.
_PERSON_RELATIONAL = re.compile(
    r"\b(?i:with|from|to|for|by|met|saw|called|texted|emailed|asked|told|"
    r"thanked|owe|love)\s+([A-Z][a-z]{1,15})(?:'s|\b)",
)
_PERSON_BIRTHDAY = re.compile(
    r"\b([A-Z][a-z]{1,15})(?:'s|s')\s+(?i:birthday|anniversary|wedding|funeral)",
)
_PERSON_WHOLE = re.compile(
    r"\b(?i:my|her|his)\s+(?i:wife|husband|spouse|partner|son|daughter|"
    r"brother|sister|mom|mother|dad|father|cousin|friend)\s+([A-Z][a-z]{1,15})",
)

# Feeling vocabulary — minimal seed list; the engine treats matches as
# hypotheses. NOT a clinical assessment.
_FEELING_WORDS = [
    "happy", "joyful", "grateful", "thankful", "content", "peaceful",
    "calm", "relaxed", "excited", "hopeful", "loved", "blessed",
    "tired", "exhausted", "drained", "weary", "fatigued",
    "anxious", "worried", "nervous", "stressed", "overwhelmed",
    "afraid", "scared", "fearful", "uncertain", "confused", "lost",
    "sad", "down", "blue", "discouraged", "hopeless", "lonely",
    "angry", "frustrated", "annoyed", "irritated", "resentful",
    "ashamed", "guilty", "embarrassed", "regretful",
    "convicted", "humbled", "broken", "contrite",
]
_FEELING_RES = [
    re.compile(rf"\b(?:i\s+(?:am|feel|felt|am\s+feeling))\s+(?:so\s+|really\s+|very\s+|kinda\s+|a\s+bit\s+|a\s+little\s+)?({w})\b", re.IGNORECASE)
    for w in _FEELING_WORDS
] + [
    re.compile(rf"\b(?:feeling|feel|felt)\s+({w})\b", re.IGNORECASE)
    for w in _FEELING_WORDS
]

# Coordinated-continuation pattern — captures feeling words after "and",
# "but", "or", commas. "I am tired and stressed" should catch both.
_FEELING_CONTINUATION = re.compile(
    rf"(?:\band\b|\bbut\b|\bor\b|,)\s+(?:so\s+|really\s+|very\s+|kinda\s+|a\s+bit\s+|a\s+little\s+|mostly\s+)?({'|'.join(_FEELING_WORDS)})\b",
    re.IGNORECASE,
)


@dataclass
class Categorization:
    """The engine's read of the entry. All fields are *hypotheses*.

    Empty list / None for any field means "the engine didn't recognize
    a [field] in this text" — not "this entry has none." Absence is
    explicit, never implicit.

    Per Matt 2026-05-03: *"It's all important. It may just be
    important to you, but it was important enough to input."* The
    engine doesn't filter for "depth" — even casual notes (tasks,
    dates, names, feelings) are surfaced as real signal.
    """
    # Doctrinal / structural
    detected_anchors: List[str] = field(default_factory=list)
    detected_action_shapes: List[str] = field(default_factory=list)
    detected_scope: Optional[str] = None
    detected_packet_shape: Optional[str] = None
    detected_packet_confidence: float = 0.0
    closest_precedent_id: Optional[str] = None
    closest_precedent_distance: Optional[int] = None

    # Daily-life signals (per the broader stream-of-consciousness
    # framing — tasks, dates, names, feelings)
    detected_tasks: List[str] = field(default_factory=list)
    detected_dates: List[str] = field(default_factory=list)
    detected_people: List[str] = field(default_factory=list)
    detected_feelings: List[str] = field(default_factory=list)

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
            detected_tasks=list(d.get("detected_tasks") or []),
            detected_dates=list(d.get("detected_dates") or []),
            detected_people=list(d.get("detected_people") or []),
            detected_feelings=list(d.get("detected_feelings") or []),
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

    # 5. Tasks — first-person and imperative cues
    detected_tasks: List[str] = []
    seen_tasks = set()
    for pat in _TASK_PATTERNS:
        for m in pat.finditer(text):
            task = (m.group(1) if m.groups() else m.group(0)).strip().rstrip(",.;: ")
            if task and task.lower() not in seen_tasks and len(task) >= 3:
                seen_tasks.add(task.lower())
                detected_tasks.append(task)

    # 6. Dates / calendar markers
    detected_dates: List[str] = []
    seen_dates = set()
    for pat in _DATE_PATTERNS:
        for m in pat.finditer(text):
            d = m.group(0).strip()
            d_norm = d.lower()
            if d and d_norm not in seen_dates:
                seen_dates.add(d_norm)
                detected_dates.append(d)

    # 7. People — heuristic-only; never a real NER pass
    detected_people: List[str] = []
    seen_people = set()
    for pat in (_PERSON_RELATIONAL, _PERSON_BIRTHDAY, _PERSON_WHOLE):
        for m in pat.finditer(text):
            name = m.group(1).strip()
            if name and name not in seen_people:
                seen_people.add(name)
                detected_people.append(name)

    # 8. Feelings — seed vocabulary only; treats matches as hypotheses
    detected_feelings: List[str] = []
    seen_feelings = set()
    for pat in _FEELING_RES:
        for m in pat.finditer(text):
            f = m.group(1).lower()
            if f and f not in seen_feelings:
                seen_feelings.add(f)
                detected_feelings.append(f)
    # If we found at least one feeling via the strict pattern, also pick
    # up coordinated continuations ("I am tired AND stressed AND grateful").
    if detected_feelings:
        for m in _FEELING_CONTINUATION.finditer(text):
            f = m.group(1).lower()
            if f and f not in seen_feelings:
                seen_feelings.add(f)
                detected_feelings.append(f)

    return Categorization(
        detected_anchors=detected_anchors,
        detected_action_shapes=detected_action_shapes,
        detected_scope=detected_scope,
        detected_packet_shape=detected_packet_shape,
        detected_packet_confidence=detected_packet_confidence,
        detected_tasks=detected_tasks,
        detected_dates=detected_dates,
        detected_people=detected_people,
        detected_feelings=detected_feelings,
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
        limit: Optional[int] = None,
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
        if limit is not None:
            out = out[:limit]
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
    #
    # The packet shape coming out of categorize() is in two-part form
    # (e.g. "governance.proposal", "scripture.anchor-cluster"); the
    # ledger's find_closest expects the base axis ("governance",
    # "scripture") since dimensions are indexed by that. Strip the
    # subtype before lookup.
    if look_up_precedent and entry.categorization.detected_packet_shape:
        try:
            from .ledger import find_closest
            stub_packet: Dict[str, Any] = {}
            if entry.categorization.detected_anchors:
                stub_packet["scripture_anchors"] = list(
                    entry.categorization.detected_anchors
                )
            base_axis = entry.categorization.detected_packet_shape.split(".")[0]
            stub_packet["domain"] = base_axis
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


# ── Emergence (see what is being created before the creator) ───────


@dataclass
class Emergence:
    """Patterns the engine sees across a window of recent entries
    that the writer may not have named yet.

    Per Matt 2026-05-03: *"We see what is being created before the
    creator. This helps them see the path they are on. It keeps them
    organized and on track."*

    Each field surfaces a *pattern* — never a directive, never a
    judgment. The writer does the work of seeing what (if anything)
    to do with the pattern.
    """
    window_seconds: float = 0.0
    entries_in_window: int = 0

    # Recurring signals — what's been showing up
    recurring_anchors: Dict[str, int] = field(default_factory=dict)
    recurring_people: Dict[str, int] = field(default_factory=dict)
    recurring_action_shapes: Dict[str, int] = field(default_factory=dict)
    feeling_distribution: Dict[str, int] = field(default_factory=dict)

    # Tasks that haven't been struck through (kept from older entries
    # and not annotated as done)
    standing_tasks: List[Dict[str, Any]] = field(default_factory=list)

    # Upcoming dates the engine noticed across entries
    upcoming_dates: List[Dict[str, Any]] = field(default_factory=list)

    # Plain-language narrative the renderer can lean on
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def emergence(
    *,
    since: Optional[float] = None,
    window_days: int = 30,
    store: Optional[JournalStore] = None,
    now: Optional[float] = None,
) -> Emergence:
    """Surface emerging patterns across recent entries.

    Read-only. Aggregates categorization signals across the window
    and surfaces what's recurring (anchors / people / action shapes /
    feelings), what tasks are still standing (mentioned in entries,
    no later annotation marking them done), and what dates appeared.
    """
    store = store or JournalStore()
    now_epoch = now if now is not None else _now()
    if since is None:
        since = now_epoch - (window_days * 86400)

    entries = [e for e in store.list_all() if e.written_at >= since]

    recurring_anchors: Dict[str, int] = {}
    recurring_people: Dict[str, int] = {}
    recurring_action_shapes: Dict[str, int] = {}
    feeling_distribution: Dict[str, int] = {}
    upcoming_dates: List[Dict[str, Any]] = []
    standing_tasks: List[Dict[str, Any]] = []

    for entry in entries:
        cat = entry.categorization
        for a in cat.detected_anchors or []:
            recurring_anchors[a] = recurring_anchors.get(a, 0) + 1
        for p in cat.detected_people or []:
            recurring_people[p] = recurring_people.get(p, 0) + 1
        for s in cat.detected_action_shapes or []:
            recurring_action_shapes[s] = recurring_action_shapes.get(s, 0) + 1
        for f in cat.detected_feelings or []:
            feeling_distribution[f] = feeling_distribution.get(f, 0) + 1

        for d in cat.detected_dates or []:
            upcoming_dates.append({
                "date_text": d,
                "entry_id": entry.id,
                "entry_written_at": entry.written_at,
            })

        for t in cat.detected_tasks or []:
            # If the entry has an annotation later than the entry's
            # written_at that mentions "done" or "completed", treat as
            # struck through. Otherwise, the task is still standing.
            done = False
            for ann in entry.annotations or []:
                if ann.timestamp > entry.written_at:
                    note_l = (ann.note or "").lower()
                    if any(k in note_l for k in ("done", "completed", "finished", "handled")):
                        done = True
                        break
            if not done:
                standing_tasks.append({
                    "task": t,
                    "entry_id": entry.id,
                    "entry_written_at": entry.written_at,
                })

    notes: List[str] = []
    # Surface plain-language patterns. Never directive — only naming
    # what the engine sees.
    if recurring_anchors:
        top = sorted(recurring_anchors.items(), key=lambda x: -x[1])[:3]
        if top[0][1] >= 3:
            notes.append(
                f"You've returned to {top[0][0]} {top[0][1]} times in this window."
            )
    if recurring_action_shapes:
        top = sorted(recurring_action_shapes.items(), key=lambda x: -x[1])[:1]
        shape, count = top[0]
        if count >= 3:
            notes.append(
                f"Action shape {shape} appears in {count} of {len(entries)} entries."
            )
    if feeling_distribution:
        top = sorted(feeling_distribution.items(), key=lambda x: -x[1])[:3]
        if top[0][1] >= 3:
            words = ", ".join(f"{w}({c})" for w, c in top)
            notes.append(f"Feelings recurring: {words}.")
    if standing_tasks:
        notes.append(
            f"{len(standing_tasks)} task(s) still standing — surfaced from your "
            f"writing, not yet marked done in an annotation."
        )
    if recurring_people:
        top = sorted(recurring_people.items(), key=lambda x: -x[1])[:3]
        if top[0][1] >= 3:
            people = ", ".join(f"{n}({c})" for n, c in top)
            notes.append(f"People you've named multiple times: {people}.")

    return Emergence(
        window_seconds=now_epoch - since,
        entries_in_window=len(entries),
        recurring_anchors=recurring_anchors,
        recurring_people=recurring_people,
        recurring_action_shapes=recurring_action_shapes,
        feeling_distribution=feeling_distribution,
        standing_tasks=standing_tasks,
        upcoming_dates=upcoming_dates,
        notes=notes,
    )


def render_emergence(em: Emergence) -> str:
    """Render an Emergence as human-readable markdown.

    Honors the doctrine: descriptive only, never prescriptive. The
    renderer names what the engine sees and stops. The user does the
    work of deciding what (if anything) to do with the pattern.
    """
    lines: List[str] = []
    lines.append("## What the engine sees emerging")
    lines.append("")
    days = em.window_seconds / 86400 if em.window_seconds else 0
    lines.append(
        f"_Across {em.entries_in_window} entries in the last "
        f"{days:.0f} day(s)._"
    )
    lines.append("")

    if not em.notes and not em.standing_tasks and not em.upcoming_dates:
        lines.append("_No patterns surfaced yet. The keeping continues._")
        lines.append("")
        return "\n".join(lines)

    if em.notes:
        for n in em.notes:
            lines.append(f"- {n}")
        lines.append("")

    if em.standing_tasks:
        lines.append("### Tasks still standing")
        lines.append("")
        for t in em.standing_tasks[:10]:
            lines.append(f"- {t['task']}  _(from `{t['entry_id']}`)_")
        if len(em.standing_tasks) > 10:
            lines.append(f"- _+{len(em.standing_tasks) - 10} more_")
        lines.append("")

    if em.upcoming_dates:
        lines.append("### Dates noted in your writing")
        lines.append("")
        for d in em.upcoming_dates[:8]:
            lines.append(f"- `{d['date_text']}`  _(from `{d['entry_id']}`)_")
        if len(em.upcoming_dates) > 8:
            lines.append(f"- _+{len(em.upcoming_dates) - 8} more_")
        lines.append("")

    return "\n".join(lines)


# ── Sharing (community tier — widespread or directly shared) ───────


# Tag conventions on a JournalEntry's user_tags:
#   "shelf"           — widespread; anyone reaching for your shelf sees it
#   "shared_with:<u>" — directly shared with user `u`; only `u` sees it in
#                       their community feed
SHELF_TAG = "shelf"
DIRECT_SHARE_PREFIX = "shared_with:"


def share_widespread(
    entry_id: str,
    *,
    store: Optional[JournalStore] = None,
) -> Optional[JournalEntry]:
    """Publish a seed to the shelf — anyone reaching for your shelf
    will see it. Idempotent."""
    store = store or JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return None
    if SHELF_TAG not in entry.user_tags:
        entry.user_tags = list(entry.user_tags) + [SHELF_TAG]
        entry.modified_at = _now()
        store.save(entry)
    return entry


def share_with(
    entry_id: str,
    *,
    recipient: str,
    store: Optional[JournalStore] = None,
) -> Optional[JournalEntry]:
    """Share a seed directly with one person. Adds `shared_with:<u>`
    to the entry's tags. Multiple direct-share recipients can be
    added by calling this repeatedly. Idempotent per-recipient."""
    if not recipient or not recipient.strip():
        raise ValueError("recipient cannot be empty")
    recipient = recipient.strip()
    store = store or JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return None
    tag = DIRECT_SHARE_PREFIX + recipient
    if tag not in entry.user_tags:
        entry.user_tags = list(entry.user_tags) + [tag]
        entry.modified_at = _now()
        store.save(entry)
    return entry


def unshare_with(
    entry_id: str,
    *,
    recipient: str,
    store: Optional[JournalStore] = None,
) -> Optional[JournalEntry]:
    """Withdraw a direct share. The seed remains in the library
    untouched; only the share tag is removed."""
    store = store or JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        return None
    tag = DIRECT_SHARE_PREFIX + recipient.strip()
    if tag in entry.user_tags:
        entry.user_tags = [t for t in entry.user_tags if t != tag]
        entry.modified_at = _now()
        store.save(entry)
    return entry


@dataclass
class CommunityItem:
    """One entry visible to the current viewer in the community feed.

    Either `widespread=True` (entry is on the shelf, anyone sees) or
    `widespread=False` and `direct=True` (entry was shared specifically
    with the current viewer). Both can be true if the entry is on the
    shelf AND directly addressed to this viewer.
    """
    entry: JournalEntry
    widespread: bool
    direct: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry": self.entry.to_dict(),
            "widespread": self.widespread,
            "direct": self.direct,
        }


def community_feed(
    *,
    viewer: str = "default",
    limit: int = 20,
    store: Optional[JournalStore] = None,
) -> List[CommunityItem]:
    """Return the community feed visible to a given viewer.

    Includes:
      * Every entry on the shelf (widespread; anyone sees these)
      * Every entry tagged `shared_with:<viewer>` (direct shares to
        the current viewer; private to them)

    Newest first. The viewer parameter defaults to `default` for
    single-user deployments; multi-user installs pass the
    authenticated user's id.
    """
    store = store or JournalStore()
    direct_tag = DIRECT_SHARE_PREFIX + viewer.strip()

    seen: Dict[str, CommunityItem] = {}
    for entry in store.list_all():
        widespread = SHELF_TAG in entry.user_tags
        direct = direct_tag in entry.user_tags
        if not (widespread or direct):
            continue
        seen[entry.id] = CommunityItem(
            entry=entry, widespread=widespread, direct=direct,
        )
    items = list(seen.values())
    items.sort(key=lambda i: i.entry.modified_at, reverse=True)
    return items[:limit]


# ── Bins — emergent clusters of the user's life ─────────────────────


# Per the project's "fractal bins architecture" memory: bins are NAMED
# BY USE, REBALANCED FOR OPTIMAL RECALL, PACKETS TRANSPORT BETWEEN
# THEM. Bins are not pre-defined categories the user sorts into;
# they emerge from what the writing has shown.
#
# Bins themselves are a fractal of the larger system:
#   * each bin has its own anchor / scope / action / feeling
#     fingerprint — its signal-signature
#   * bins can be widespread (shelf-shaped) or private to the user
#   * bins can be reviewed, merged, split, renamed, or promoted
#   * the engine never invents a bin without a use-pattern in the
#     entries — explicit absence over invented structure


# Minimum entries needed for the engine to infer a bin from a
# single recurring signal. Tunable; lower = more bins, higher = only
# the strong patterns surface.
BIN_MIN_RECURRENCE = 3


@dataclass
class Bin:
    """One emergent cluster of journal entries that share a signal.

    A bin is named by what made it visible (an anchor recurring, a
    person recurring, an action shape clustering). Membership is the
    set of entry ids whose categorization carries the signal. Bins
    overlap — an entry can belong to several at once.
    """
    bin_id: str  # synthesized from kind+key, e.g. "anchor:Mt 5:37"
    kind: str    # "anchor" | "person" | "action" | "feeling" | "shape"
    name: str    # human-readable, derived from the kind+key
    signal_key: str  # the literal signal — "Mt 5:37", "Sarah", "Hold"
    entry_ids: List[str] = field(default_factory=list)
    sample_entries: List[Dict[str, Any]] = field(default_factory=list)
    size: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def infer_bins(
    *,
    min_recurrence: int = BIN_MIN_RECURRENCE,
    store: Optional[JournalStore] = None,
) -> List[Bin]:
    """Walk the user's library and surface emergent bins.

    Bins are inferred along five axes: anchor, person, action shape,
    feeling, and packet shape. A signal that recurs in `min_recurrence`
    or more entries becomes a bin. Bins are sorted by size descending
    so the strongest patterns surface first.

    The engine does NOT name bins by topic — it names them by the
    literal signal that grouped the entries. "Mt 5:37" not "spiritual
    discernment." "Sarah" not "relationship." The user does the
    abstracting if they want to.
    """
    store = store or JournalStore()
    entries = store.list_all()

    # signal-key → list of entry ids
    by_kind: Dict[str, Dict[str, List[str]]] = {
        "anchor":  {},
        "person":  {},
        "action":  {},
        "feeling": {},
        "shape":   {},
    }
    entry_lookup: Dict[str, JournalEntry] = {e.id: e for e in entries}

    for entry in entries:
        cat = entry.categorization
        for a in cat.detected_anchors or []:
            by_kind["anchor"].setdefault(a, []).append(entry.id)
        for p in cat.detected_people or []:
            by_kind["person"].setdefault(p, []).append(entry.id)
        for s in cat.detected_action_shapes or []:
            by_kind["action"].setdefault(s, []).append(entry.id)
        for f in cat.detected_feelings or []:
            by_kind["feeling"].setdefault(f, []).append(entry.id)
        if cat.detected_packet_shape:
            by_kind["shape"].setdefault(
                cat.detected_packet_shape, []).append(entry.id)

    bins: List[Bin] = []
    for kind, mapping in by_kind.items():
        for key, ids in mapping.items():
            if len(ids) < min_recurrence:
                continue
            # Pick a few sample previews for the bin's surface.
            samples: List[Dict[str, Any]] = []
            for eid in ids[:3]:
                e = entry_lookup.get(eid)
                if e is None:
                    continue
                preview = e.text.replace("\n", " ").strip()[:80]
                samples.append({"id": eid, "preview": preview})
            bins.append(Bin(
                bin_id=f"{kind}:{key}",
                kind=kind,
                name=key,
                signal_key=key,
                entry_ids=list(ids),
                sample_entries=samples,
                size=len(ids),
            ))

    # Strongest signals first.
    bins.sort(key=lambda b: b.size, reverse=True)
    return bins


def review_bin(
    bin_id: str,
    *,
    store: Optional[JournalStore] = None,
) -> Optional[Dict[str, Any]]:
    """Look at one bin: its full entry list with previews. Returns
    None if the bin doesn't currently exist (signal stopped recurring,
    or never did)."""
    bins = infer_bins(min_recurrence=1, store=store)  # widen so any signal counts
    for b in bins:
        if b.bin_id == bin_id:
            store = store or JournalStore()
            full_entries = []
            for eid in b.entry_ids:
                e = store.load(eid)
                if e is None:
                    continue
                full_entries.append({
                    "id": e.id,
                    "text": e.text,
                    "written_at": e.written_at,
                    "user_tags": list(e.user_tags),
                    "anchors": list(e.categorization.detected_anchors or []),
                    "actions": list(e.categorization.detected_action_shapes or []),
                    "scope": e.categorization.detected_scope,
                })
            return {
                "bin": b.to_dict(),
                "entries": full_entries,
            }
    return None


def render_bins(bins: List[Bin]) -> str:
    """Render bins as human-readable markdown.

    Per doctrine: descriptive only. "Bin X has 5 entries" not "you
    should focus on bin X." The user does the deciding."""
    if not bins:
        return ("## Bins forming\n\n_No bins yet. Bins emerge once a "
                "signal recurs across several entries — the engine "
                "doesn't invent them. Keep writing._")
    lines: List[str] = ["## Bins forming"]
    lines.append("")
    lines.append(
        f"_{len(bins)} bin(s) the engine sees in your library. "
        f"Each bin is named by the recurring signal — anchor, person, "
        f"action shape, feeling, or packet shape — that grouped the "
        f"entries. Review and rebalance as you like; the engine does "
        f"not impose structure._"
    )
    lines.append("")
    by_kind: Dict[str, List[Bin]] = {}
    for b in bins:
        by_kind.setdefault(b.kind, []).append(b)
    for kind in ("anchor", "person", "action", "feeling", "shape"):
        kind_bins = by_kind.get(kind, [])
        if not kind_bins:
            continue
        lines.append(f"### {kind} bins")
        lines.append("")
        for b in kind_bins:
            lines.append(f"- **`{b.name}`** — {b.size} entries")
            for s in b.sample_entries:
                lines.append(f"    - `{s['id']}` — {s['preview']}")
        lines.append("")
    return "\n".join(lines)


# ── Promotion (individual → community → central, by survival) ───────


@dataclass
class PromotionResult:
    """The outcome of attempting to promote a journal seed to the
    central seed bank (audit chain).

    Honors the elimination doctrine: when promotion fails, the gate
    verdicts and reasons are surfaced so the user can see the
    elimination trail. The seed itself is never destroyed — failed
    promotions leave the original entry untouched in the library.
    """
    entry_id: str
    overall: str  # "PASS" | "REJECT" | "QUARANTINE" | "ERROR"
    promoted: bool  # True only if PASS and sealed to ledger
    precedent_id: Optional[str] = None
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)
    packet_used: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _entry_to_packet(
    entry: "JournalEntry",
    *,
    confession: str,
    witnesses: List[str],
    wait_window_seconds: Optional[int] = None,
) -> Dict[str, Any]:
    """Translate a journal entry into a packet shape the four-gate
    pipeline can run on.

    Inputs the engine cannot infer from text — confession (humility
    statement), explicit witness list, optional wait window — must be
    supplied by the caller. The engine reads what's there; it does
    not invent attestations.
    """
    cat = entry.categorization

    # Axis: prefer the recognized packet shape; fall back to
    # 'governance' for personal/family/community-scope decisions
    # (governance is the generic "decision packet" axis).
    axis = cat.detected_packet_shape or "governance"

    # Scope: map detected scope to engine scope vocabulary.
    # Personal/family → adapter; team/community → mesh;
    # region → canon. Default adapter.
    scope_map = {
        "personal":  "adapter",
        "family":    "adapter",
        "team":      "mesh",
        "community": "mesh",
        "region":    "canon",
    }
    engine_scope = scope_map.get(cat.detected_scope or "personal", "adapter")

    # Anchors: convert the engine's preferred Anchor-dict shape.
    anchors_dicts = [
        {"ref": a, "layer": "bible"}  # default layer; user may override
        for a in (cat.detected_anchors or [])
    ]

    # Action: the first detected action shape, or "Hold" as a safe default.
    action = "Hold"
    if cat.detected_action_shapes:
        action = cat.detected_action_shapes[0]

    decision_packet: Dict[str, Any] = {
        "title": entry.text[:80],
        "decision": entry.text,
        "rationale": confession or "(no confession supplied)",
        "scope": engine_scope,
        "scripture_anchors": list(cat.detected_anchors or []),
        "witnesses": list(witnesses),
        "action": action,
        # Floor / red items default empty; the engine treats absence as
        # explicit absence and lets gates run.
        "red_items": [],
        "floor_items": [],
    }

    packet: Dict[str, Any] = {
        "domain": axis,
        "scope": engine_scope,
        "created_epoch": int(entry.written_at),  # schema requires int
        "witness_count": len(witnesses),
        "scripture_anchors": anchors_dicts,
        "DECISION_PACKET": decision_packet,
    }
    if wait_window_seconds is not None:
        packet["wait_window_seconds"] = int(wait_window_seconds)

    return packet


def promote(
    entry_id: str,
    *,
    confession: str,
    witnesses: Optional[List[str]] = None,
    wait_window_seconds: Optional[int] = None,
    summary: Optional[str] = None,
    store: Optional[JournalStore] = None,
    now_epoch: Optional[int] = None,
) -> PromotionResult:
    """Promote a journal seed to the central seed bank.

    The path: translate the seed's categorization into a packet,
    run it through the four gates (RED/FLOOR/WAY/BROTHERS/GOD), and
    on PASS seal it to the audit chain as a precedent. The original
    journal entry is preserved verbatim; on success it gains a
    `sealed` user-tag and the precedent_id stored in annotations
    so the trail back is intact.

    Failures are NOT exceptions — they're returned in the
    PromotionResult with overall=REJECT/QUARANTINE/ERROR and the
    full gate trail. The elimination is the reasoning. The seed
    survives in the library and can be promoted again later (after
    annotation, more witnesses, or wait-window elapse).
    """
    if not confession or not confession.strip():
        raise ValueError(
            "promotion requires a confession — a humility statement "
            "naming the seed's claim. The engine never invents this."
        )
    witnesses = list(witnesses or [])

    store = store or JournalStore()
    entry = store.load(entry_id)
    if entry is None:
        raise ValueError(f"no journal entry found with id {entry_id}")

    packet = _entry_to_packet(
        entry,
        confession=confession,
        witnesses=witnesses,
        wait_window_seconds=wait_window_seconds,
    )

    # Run the gates. Lazy-import to keep journal.py loadable even when
    # the engine pipeline has issues at import time.
    try:
        from .engine import EngineConfig, validate_and_seal
        from . import ledger as _ledger
    except ImportError as e:
        return PromotionResult(
            entry_id=entry_id,
            overall="ERROR",
            promoted=False,
            reasons=[f"engine pipeline not available: {e}"],
            packet_used=packet,
        )

    cfg = EngineConfig(schema_path="", run_verifiers=True)

    try:
        record = validate_and_seal(
            packet,
            now_epoch=now_epoch,
            config=cfg,
            packet_id=entry_id,
        )
    except Exception as e:
        return PromotionResult(
            entry_id=entry_id,
            overall="ERROR",
            promoted=False,
            reasons=[f"engine raised: {type(e).__name__}: {e}"],
            packet_used=packet,
        )

    # Collect the gate trail for the result, regardless of overall.
    gate_results: List[Dict[str, Any]] = []
    reasons: List[str] = []
    for gr in record.gate_results or []:
        gate_results.append({
            "gate": gr.gate,
            "status": gr.status,
            "reasons": list(gr.reasons or []),
        })
        if gr.status in ("REJECT", "QUARANTINE") and gr.reasons:
            for r in gr.reasons:
                reasons.append(f"{gr.gate}: {r}")

    if record.overall != "PASS":
        # Elimination trail visible; seed unchanged.
        return PromotionResult(
            entry_id=entry_id,
            overall=record.overall,
            promoted=False,
            gate_results=gate_results,
            reasons=reasons,
            packet_used=packet,
        )

    # PASS — seal to the ledger.
    try:
        target = _ledger.seal_to_ledger(
            record,
            summary=summary or entry.text[:120],
        )
    except Exception as e:
        return PromotionResult(
            entry_id=entry_id,
            overall="ERROR",
            promoted=False,
            gate_results=gate_results,
            reasons=[f"seal_to_ledger raised: {type(e).__name__}: {e}"],
            packet_used=packet,
        )

    # Mark the journal entry: tag + annotation pointing at the
    # sealed precedent. Original text is preserved.
    precedent_id = None
    try:
        from pathlib import Path as _P
        # The seal_to_ledger return is a Path to the file; the
        # precedent_id is in the file's content.
        if isinstance(target, _P) and target.exists():
            data = json.loads(target.read_text(encoding="utf-8"))
            precedent_id = data.get("precedent_id")
    except Exception:
        pass

    if "sealed" not in entry.user_tags:
        entry.user_tags = list(entry.user_tags) + ["sealed"]
    entry.modified_at = _now()
    entry.annotations.append(Annotation(
        note=f"sealed to central as {precedent_id or '(unknown id)'}",
        timestamp=_now(),
        author="engine",
    ))
    store.save(entry)

    return PromotionResult(
        entry_id=entry_id,
        overall="PASS",
        promoted=True,
        precedent_id=precedent_id,
        gate_results=gate_results,
        reasons=[],
        packet_used=packet,
    )


def render_promotion(result: PromotionResult) -> str:
    """Render a PromotionResult as human-readable markdown.

    PASS rendering names the new precedent and the path through the
    gates. REJECT/QUARANTINE rendering surfaces the elimination
    trail — what was NOT the answer — so the user can see what to
    address. Never directs the user; only names what happened.
    """
    lines: List[str] = []
    lines.append(f"## Promotion of `{result.entry_id}`")
    lines.append("")

    if result.promoted:
        lines.append(
            f"_Sealed to the central seed bank as_ "
            f"`{result.precedent_id or '(unknown id)'}`."
        )
        lines.append("")
        lines.append("### Gates the seed survived")
        lines.append("")
        for gr in result.gate_results:
            lines.append(f"- **{gr['gate']}** — {gr['status']}")
        lines.append("")
        lines.append(
            "_The original journal entry remains in your library, "
            "now tagged `sealed` with an annotation pointing to the "
            "precedent. Both records are kept; neither replaces the "
            "other._"
        )
    else:
        lines.append(f"_Outcome:_ **{result.overall}** — not promoted.")
        lines.append("")
        lines.append("### Where elimination fired")
        lines.append("")
        for gr in result.gate_results:
            lines.append(f"- **{gr['gate']}** — {gr['status']}")
            for r in gr.get("reasons") or []:
                lines.append(f"    - {r}")
        if result.reasons and not result.gate_results:
            lines.append("")
            for r in result.reasons:
                lines.append(f"- {r}")
        lines.append("")
        lines.append(
            "_The seed survives in your library unchanged. The "
            "elimination trail is the reasoning — address what's "
            "missing (a witness, a wait, an anchor) and try again, "
            "or leave the seed where it is._"
        )

    return "\n".join(lines)


__all__ = [
    "Categorization",
    "Annotation",
    "JournalEntry",
    "JournalStore",
    "Calibration",
    "Emergence",
    "PromotionResult",
    "CommunityItem",
    "SHELF_TAG",
    "DIRECT_SHARE_PREFIX",
    "categorize",
    "calibrate",
    "render_calibration",
    "capture",
    "annotate",
    "thread",
    "emergence",
    "render_emergence",
    "promote",
    "render_promotion",
    "share_widespread",
    "share_with",
    "unshare_with",
    "community_feed",
    "Bin",
    "BIN_MIN_RECURRENCE",
    "infer_bins",
    "review_bin",
    "render_bins",
]
