"""Question type classifier for incoming submissions.

Classifies raw user text into one of nine question types before any
Scripture retrieval or gate evaluation. The classification determines
which Scripture territory is load-bearing and which gate applies first.

Implementation: rule-based weighted signal matching. Replace `classify()`
internals with a learned model when the well has 10,000+ labeled pairs.
The public interface (ClassificationResult, classify()) stays the same.

Urgency ordering (highest-stakes gate wins compound classification):
  CRISIS > DECISION > RELATIONAL > FORMATION > TIMING > RESOURCE
  > DOCTRINE > WISDOM > HISTORICAL
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ── Type constants ─────────────────────────────────────────────────────

WISDOM     = "WISDOM"
DOCTRINE   = "DOCTRINE"
DECISION   = "DECISION"
RELATIONAL = "RELATIONAL"
RESOURCE   = "RESOURCE"
TIMING     = "TIMING"
FORMATION  = "FORMATION"
CRISIS     = "CRISIS"
HISTORICAL = "HISTORICAL"

QUESTION_TYPES = (
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
)

# ── Metadata maps ──────────────────────────────────────────────────────

# Primary gate each type routes to first.
# DECISION → BROTHERS then GOD; FORMATION → all four; CRISIS → RED first.
GATE_MAP: dict[str, str] = {
    WISDOM:     "FLOOR",
    DOCTRINE:   "RED",
    DECISION:   "BROTHERS",
    RELATIONAL: "BROTHERS",
    RESOURCE:   "FLOOR",
    TIMING:     "GOD",
    FORMATION:  "ALL",
    CRISIS:     "RED",
    HISTORICAL: "RED",
}

# Primary Scripture territory per type (ordered by weight).
TERRITORY_MAP: dict[str, list[str]] = {
    WISDOM:     ["Proverbs", "Ecclesiastes", "James", "Matthew 5-7"],
    DOCTRINE:   ["Romans", "Hebrews", "John", "Ephesians"],
    DECISION:   ["Psalms", "Proverbs", "Acts", "Isaiah"],
    RELATIONAL: ["Matthew 18", "Romans 12-15", "1 Corinthians", "Ephesians 4"],
    RESOURCE:   ["Proverbs", "Deuteronomy", "Luke 12-16", "2 Corinthians 8-9"],
    TIMING:     ["Ecclesiastes 3", "Psalms 27", "Psalms 37", "Psalms 40", "Habakkuk"],
    FORMATION:  ["Romans", "Galatians", "Philippians", "1 John"],
    CRISIS:     ["Psalms", "Lamentations", "Job", "Isaiah 40-55"],
    HISTORICAL: ["full canon"],
}

# Urgency rank — compound questions resolve to the higher-stakes type
# ONLY when their scores are within 40% of each other.
_PRIORITY: dict[str, int] = {
    CRISIS: 9, DECISION: 8, RELATIONAL: 7, FORMATION: 6,
    TIMING: 5, RESOURCE: 4, DOCTRINE: 3, WISDOM: 2, HISTORICAL: 1,
}

# Confidence threshold below which clarification is requested before
# the submission proceeds.
CLARIFICATION_THRESHOLD = 0.70

# ── Life-safety fast path ──────────────────────────────────────────────
# Any match returns CRISIS immediately with confidence 1.0 and sets
# life_safety=True. The path composer returns a fixed output for these.

_LIFE_SAFETY_RAW = [
    r"\bsuicide\b",
    r"\bkill (myself|my self)\b",
    r"\bend my life\b",
    r"\bself[- ]harm\b",
    r"\bhurt myself\b",
    r"\bnot worth living\b",
    r"\bwant to die\b",
    r"\bno reason to (live|continue)\b",
    r"can'?t go on",
    r"don'?t want to be here",
    r"\btaking my (own )?life\b",
    r"\bending it (all)?\b",
    r"\bwhether (life is|it'?s?) worth (living|going on)\b",
    r"\b(a point|any reason|any point) (to|in) (continu(e|ing)|going on|living)\b",
    r"\bno (reason|point) (in|to) (continu(e|ing)|going on|living)\b",
]

_LIFE_SAFETY = [re.compile(p, re.IGNORECASE) for p in _LIFE_SAFETY_RAW]

# ── Weighted signal patterns ───────────────────────────────────────────
# Tier weights: strong=3.0, moderate=1.5, weak=0.5
# Each pattern is compiled once at module load and matched as a binary
# hit (1 if any occurrence, 0 if none) — not counted per occurrence.

_SIGNAL_RAW: dict[str, dict[str, list[str]]] = {

    CRISIS: {
        "strong": [
            r"i don'?t know what to do",
            r"i don'?t see a way out",
            r"\bhopeless\b",
            r"\bdesperate\b",
            r"\bdesparate\b",        # common misspelling
            r"\boverwhelmed\b",
            r"\bbreaking down\b",
            r"\bfalling apart\b",
            r"can'?t take (it|this) anymore",
            r"\bin (a )?crisis\b",
            r"\bemergency\b",
            r"\bI need help right now\b",
        ],
        "moderate": [
            r"\bscared\b",
            r"\bafraid\b",
            r"\bterrified\b",
            r"\bpanicking\b",
            r"\bpanic\b",
            r"\btoo much\b",
            r"everything (has |is )?(fallen|falling) apart",
            r"\bspiraling\b",
        ],
        "weak": [
            r"\bplease help\b",
            r"\bneed help\b",
        ],
    },

    DECISION: {
        "strong": [
            # Require action verb after "should I/we" — avoids matching
            # "How should I understand..." or "How should I think about..."
            r"\bshould (i|we) (leave|quit|move|sign|accept|reject|end|take|stay|"
            r"file|commit|separate|divorce|sell|buy|go|start|stop|apply|propose)\b",
            r"\bi'?m deciding\b",
            r"\bdeciding whether (to|if)\b",
            r"\bi need to decide\b",
            r"\bchoosing between\b",
            r"\bquit(ting)? my job\b",
            r"\bleave my (job|marriage|church|home|city|family)\b",
            r"\bget (married|divorced|engaged)\b",
            r"\bmove (to|away|out)\b",
            r"\bsign (the|a) (contract|offer|agreement|deal|papers)\b",
            r"\bfinalize\b",
            r"\birreversible\b",
            r"\bno going back\b",
            r"\bonce i (do|make|take|sign|leave|quit)\b",
            r"\bcommit(ted)? to\b",
            r"\bi have (decided|made my decision)\b",
            r"\baccept(ing)? (the |this )?(offer|position|role)\b",
            r"\bfile for (divorce|bankruptcy)\b",
            r"\bseparat(e|ing|ion)\b",
            r"\bi need to (leave|quit|go|move|end|separate|resign|walk away)\b",
        ],
        "moderate": [
            r"\bdo i (take|make|accept|reject|leave|stay|go|buy|sell)\b",
            r"\boption (a|b|1|2|one|two)\b",
            r"\bdeadline\b",
            r"\bby (monday|tuesday|wednesday|thursday|friday|saturday|sunday|end of|next week)\b",
            r"\boffer (on the table|expires)\b",
            r"\bcontract\b",
            r"\bpurchase agreement\b",
            r"\bwhat would (you|god) have me do\b",
            r"\bwe (are|'re) deciding\b",
            r"\bi'?ve been offered\b",
            r"\bwhether to (leave|quit|move|sign|accept|reject|end|separate|divorce|buy|sell)\b",
        ],
        "weak": [
            r"\bwhat would you do\b",
            r"\bwhat (should|do) i do\b",
        ],
    },

    TIMING: {
        "strong": [
            r"\bis it time (to|for)\b",
            r"\bhow long (do i|should i|must i) wait\b",
            r"\bthe right time\b",
            r"\bnot yet\b",
            r"\bnow or\b",
            r"\bwaiting (on|for) (god|the lord|a sign)\b",
            r"\bwaiting season\b",
            r"\bseason (of|for|to)\b",
            r"\bam i running (from|ahead of)\b",
        ],
        "moderate": [
            r"\bwhen should i\b",
            r"\bwait(ing)?\b",
            r"\bpatience\b",
            r"\bheld back\b",
            r"\bwhen (will|does|is) (god|the lord|it)\b",
            r"\bstill (in|at|on) this\b",
            r"\bopen (door|window)\b",
            r"\btiming (feels|matters|is|seems)\b",
        ],
        "weak": [
            r"\bhow long\b",
            r"\bwhen\b",
        ],
    },

    RELATIONAL: {
        "strong": [
            r"\bmy (husband|wife|spouse|partner|boyfriend|girlfriend|fiance|fiancee)\b",
            r"\bconflict (with|in|among|between)\b",
            r"\bforgive (them|him|her|my)\b",
            r"\bmatthew 18\b",
            r"\bconfront(ing|ation)?\b",
            r"\breconcili(ation|e)\b",
            r"\bthey (hurt|betrayed|lied|abandoned) (me|us)\b",
            r"\bsmall group (conflict|leaving|split|tension)\b",
            r"\bchurch (split|conflict|discipline)\b",
            r"\bpeople (are|have been|were) leaving (our|the|my) (church|group|community)\b",
        ],
        "moderate": [
            r"\bthey said\b",
            r"\bhe said\b",
            r"\bshe said\b",
            # Family and authority relationships — moderate (not strong) so they
            # don't override a dominant doctrine or decision signal
            r"\bmy (brother|sister|parent|father|mother|son|daughter|child|pastor|elder|deacon)\b",
            r"\bmy (boss|employer|manager|supervisor|coworker|colleague)\b",
            r"\bthey (keep|always|never|won'?t)\b",
            r"\bsomeone (keeps|always|is|has been)\b",
            r"\brelationship (with|between)\b",
            r"\bcommunity (conflict|tension|issue)\b",
            r"\bbroken (relationship|trust|friendship)\b",
        ],
        "weak": [
            # Friend moved from strong to weak — "my friend says X" is usually
            # context-framing for a doctrine question, not a relational situation
            r"\bmy (friend)\b",
            r"\bother (person|people)\b",
        ],
    },

    RESOURCE: {
        "strong": [
            r"\$\s*\d",
            r"\b\d[\d,]*k\b",           # e.g. 40k, 100k
            r"\bbudget\b",
            r"\binvest(ment|ing|or)?\b",
            r"\bspend(ing)?\b",
            r"\bsalar(y|ied)\b",
            r"\bdebt\b",
            r"\btithe\b",
            r"\bfinancial(ly)?\b",
            r"\bmoney\b",
            r"\bstewardship\b",
            r"\bgiving\b",
            r"\bwage(s)?\b",
            r"\bpay (off|down|back)\b",
            r"\bcareer (advancement|growth|change|path)\b",
            r"\bbuy or rent\b",
            r"\bhomeownership\b",
            r"\bwhether to (buy|rent|purchase) (a |the |our |my )?(house|home|property|apartment)\b",
        ],
        "moderate": [
            r"\bjob\b",
            r"\bcareer\b",       # exact word "career" — keep here for compound resolution
            r"\btime management\b",
            r"\balloc(ate|ation)\b",
            r"\bpriorities\b",
            r"\bprovide (for|my)\b",
            r"\bsave (for|up|money)\b",
        ],
        "weak": [
            r"\bmaterial\b",
            r"\bpossession(s)?\b",
            r"\bproperty\b",
            r"\bresource(s)?\b",
        ],
    },

    DOCTRINE: {
        "strong": [
            r"\bwhat does (the )?bible say (about|on)\b",
            r"\bis it true that\b",
            r"\bdoes god\b",
            r"\bcan a christian\b",
            r"\bis (it|this) biblical\b",
            r"\bwhat does scripture say (about|on|regarding)\b",
            r"\bheresy\b",
            r"\bdoctrine\b",
            r"\bsalvation\b",
            r"\batonement\b",
            r"\brepentance\b",
            r"\bpredestination\b",
            r"\bgrace (alone|and works|saves)\b",
            r"\bfaith (alone|saves|and)\b",
            r"\bonce saved always saved\b",
            r"\bcan (you|someone) lose (their|your) salvation\b",
        ],
        "moderate": [
            r"\btheolog(y|ical|ically)\b",
            r"\bgod'?s (nature|character|will|word)\b",
            r"\bholy spirit\b",
            r"\btrinity\b",
            r"\bincarnation\b",
            r"\bresurrection\b",
            r"\bgospel\b",
            r"\bjustification\b",
            r"\bsanctification\b",
            r"\bbiblical (teaching|truth|position)\b",
        ],
        "weak": [
            r"\bbiblical\b",
            r"\bscripture\b",
            r"\bbible\b",
        ],
    },

    FORMATION: {
        "strong": [
            # "I keep [behavioral pattern]" — exclude cognitive verbs like
            # "reading/thinking/saying" which are too generic
            r"\bi keep (doing|struggling with|falling into|making the same|going back to|returning to)\b",
            r"\bwhy do i (always|keep|never)\b",
            r"\bi want to (become|be|change|grow into)\b",
            r"\bwho (am|am i) becoming\b",
            r"\bmy character\b",
            r"\bsanctification\b",
            r"\bholiness\b",
            r"\bspiritual (discipline|formation|maturity|growth)\b",
            r"\bhabits? (of|in|for)\b",
            r"\bpattern in my (life|behavior)\b",
            r"\bsame (sin|struggle|pattern)\b",
        ],
        "moderate": [
            r"\bstruggl(e|ing|ed) with\b",   # match all conjugations
            r"\bidentity (in christ|as a christian)\b",
            r"\bgrowth\b",
            r"\bbecoming (more|a|the)\b",
            r"\bwhy (do|am) i (this way|like this|so)\b",
        ],
        "weak": [
            r"\bchange\b",
            r"\bimprove\b",
            r"\bbetter\b",
        ],
    },

    WISDOM: {
        "strong": [
            r"\bhelp me understand\b",
            r"\bwhat does this mean\b",
            r"\bwhy is (this|it)\b",
            r"\bhow do i (understand|think about|process|read|interpret)\b",
            r"\bdiscern(ment)?\b",
            r"\bi'?m confused (about|by)\b",
            r"\bmake sense of\b",
            r"\bwhat (is|are) (god|the lord) (doing|saying|showing)\b",
            # Moved from HISTORICAL: "what does it mean that..." is a wisdom
            # question about present meaning, not historical attestation
            r"\bwhat does it mean (that|for|when|if)\b",
            r"\bnot sure how to (recognize|understand|read|see|navigate|handle|process)\b",
        ],
        "moderate": [
            r"\bwhat should i (think|consider|notice|be aware of)\b",
            r"\bwisdom\b",
            r"\bhow (should|do) i (see|approach|handle)\b",
            r"\bnavigat(e|ing)\b",
            r"\bi'?m not sure (what|how|why|where)\b",
        ],
        "weak": [
            r"\bhow (do i|should i)\b",
            r"\bwhat (is|are)\b",
        ],
    },

    HISTORICAL: {
        "strong": [
            r"\bwhat happened (to|when|with|in)\b",
            # Subject-specific "why did" — for general "why did", use moderate
            r"\bwhy did (they|he|she|god|israel|the church|paul|jesus|the disciples)\b",
            r"\bwhat (led to|caused|triggered|started)\b",
            # Named historical events — these are unambiguously HISTORICAL
            r"\bthe (reformation|crusades|inquisition|exile|diaspora|schism|"
            r"holocaust|conquest|pentecost|dispersion|great awakening|great commission)\b",
            r"\bhistor(y|ical|ically)\b",
            r"\bwhen did (this|it|they)\b",
        ],
        "moderate": [
            # General "why did" without specific subject — could be about
            # historical events even without naming a known subject
            r"\bwhy did\b",
            r"\bin the (old testament|new testament)\b",
            r"\bbiblical histor\b",
            r"\bwhat (was|were) (happening|going on)\b",
            r"\bhistorical (context|background|significance)\b",
        ],
        "weak": [
            r"\bback then\b",
            r"\bused to\b",
            r"\bpast\b",
        ],
    },
}

# Compile all patterns once at module load.
_TIER_WEIGHTS = {"strong": 3.0, "moderate": 1.5, "weak": 0.5}

_SIGNALS: dict[str, dict[str, list[re.Pattern]]] = {
    qtype: {
        tier: [re.compile(p, re.IGNORECASE) for p in patterns]
        for tier, patterns in tiers.items()
    }
    for qtype, tiers in _SIGNAL_RAW.items()
}

# ── Disguised-decision detector ────────────────────────────────────────
# These patterns indicate an irreversible action is embedded inside a
# question phrased as WISDOM or DOCTRINE.

_DECISION_EMBED_RAW = [
    r"\bwhether (to|i should) (leave|quit|move|sign|accept|reject|end|start|file|separate|divorce)\b",
    r"\bif (i|we) (should|ought to) (leave|quit|move|sign|accept|reject|end|start|file|separate)\b",
    r"\b(leave|quit|divorce|end the|sell the|buy the|sign the)\b.{0,40}\b(decide|deciding|decision|right)\b",
    r"\bneed to decide\b",
    r"\bif this is (a sign|god telling me|god saying)\b.{0,60}\b(leave|quit|move|end|accept)\b",
    r"\bi'?ve been offered\b",   # "I've been offered something new" → decision embedded
]
_DECISION_EMBED = [re.compile(p, re.IGNORECASE) for p in _DECISION_EMBED_RAW]

# ── TIMING framing override ────────────────────────────────────────────
# "Is it time to leave" and "When should I move" are TIMING questions even
# when the embedded action looks like a DECISION. These specific phrasings
# indicate the user wants TIMING guidance, not DECISION guidance.
_TIMING_FRAME = re.compile(
    r"\b(is it time (to|for)|am i running (from|ahead of))\b",
    re.IGNORECASE
)

# Pre-compile TIMING strong patterns for the override check.
_TIMING_STRONG = [re.compile(p, re.IGNORECASE) for p in _SIGNAL_RAW[TIMING]["strong"]]

# ── Result type ────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    """Output of classify().

    primary_type       — the detected question type
    confidence         — [0.0, 1.0]; proportion of signal pointing to primary
    secondary_type     — set when confidence < CLARIFICATION_THRESHOLD
    secondary_confidence
    needs_clarification — True when confidence < CLARIFICATION_THRESHOLD
    life_safety        — True when a life-safety pattern matched (fast path)
    crisis_escalated   — True when disguised crisis was detected
    decision_escalated — True when disguised decision was detected
    raw_scores         — per-type weighted scores before normalization (debug)
    """
    primary_type: str
    confidence: float
    secondary_type: Optional[str] = None
    secondary_confidence: float = 0.0
    needs_clarification: bool = False
    life_safety: bool = False
    crisis_escalated: bool = False
    decision_escalated: bool = False
    raw_scores: dict[str, float] = field(default_factory=dict)

    @property
    def gate(self) -> str:
        """Primary gate for this question type."""
        return GATE_MAP[self.primary_type]

    @property
    def territory(self) -> list[str]:
        """Primary Scripture territory for this question type."""
        return TERRITORY_MAP[self.primary_type]

    def to_dict(self) -> dict:
        """JSON-serialisable representation."""
        return {
            "question_type": self.primary_type,
            "confidence": round(self.confidence, 4),
            "secondary_type": self.secondary_type,
            "secondary_confidence": round(self.secondary_confidence, 4),
            "needs_clarification": self.needs_clarification,
            "life_safety": self.life_safety,
            "crisis_escalated": self.crisis_escalated,
            "decision_escalated": self.decision_escalated,
            "gate": self.gate,
            "territory": self.territory,
        }


# ── Core scoring ───────────────────────────────────────────────────────

def _score(text: str) -> dict[str, float]:
    """Return raw weighted score per question type."""
    scores: dict[str, float] = {t: 0.0 for t in QUESTION_TYPES}
    for qtype, tiers in _SIGNALS.items():
        for tier, patterns in tiers.items():
            w = _TIER_WEIGHTS[tier]
            for pat in patterns:
                if pat.search(text):
                    scores[qtype] += w
                    break  # count each tier once per type (not per pattern)
    return scores


def _pick_types(
    scores: dict[str, float],
) -> tuple[str, float, str | None, float]:
    """Return (primary, primary_conf, secondary, secondary_conf)."""
    total = sum(scores.values())
    if total == 0.0:
        # No signals at all — default to WISDOM (least committal)
        return WISDOM, 0.0, None, 0.0

    ranked = sorted(
        scores.items(),
        key=lambda kv: (kv[1], _PRIORITY[kv[0]]),
        reverse=True,
    )
    primary_type, primary_raw = ranked[0]
    primary_conf = primary_raw / total

    secondary_type: str | None = None
    secondary_conf = 0.0
    if len(ranked) > 1 and ranked[1][1] > 0:
        secondary_type = ranked[1][0]
        secondary_conf = ranked[1][1] / total

    return primary_type, primary_conf, secondary_type, secondary_conf


# ── Edge case resolution ───────────────────────────────────────────────

def _check_disguised_decision(text: str, primary: str) -> bool:
    """True when the text embeds an irreversible action despite WISDOM/DOCTRINE framing."""
    if primary in (DECISION, CRISIS):
        return False
    return any(p.search(text) for p in _DECISION_EMBED)


def _check_disguised_crisis(text: str) -> bool:
    """True when calm phrasing with existential/irreversible content should escalate."""
    return bool(re.search(
        r"(whether|if) (there'?s|there is) (a point|any point|reason) "
        r"(to|in) (continu(e|ing)|going on|living)",
        text, re.IGNORECASE,
    ))


# ── Public API ─────────────────────────────────────────────────────────

def classify(text: str) -> ClassificationResult:
    """Classify a raw user submission into one of the nine question types.

    Returns a ClassificationResult. If life_safety is True, the caller
    should return "bring a human witness now" without further processing.
    If needs_clarification is True, prompt the user before proceeding.
    """
    # 1. Life-safety fast path — always checked first, regardless of score.
    for pat in _LIFE_SAFETY:
        if pat.search(text):
            return ClassificationResult(
                primary_type=CRISIS,
                confidence=1.0,
                life_safety=True,
                needs_clarification=False,
            )

    # 2. Weighted signal scoring.
    scores = _score(text)
    total = sum(scores.values())

    # 3. Pick top types.
    primary, primary_conf, secondary, secondary_conf = _pick_types(scores)

    # 4. Disguised-crisis check (calm language but existential stakes).
    crisis_escalated = _check_disguised_crisis(text)
    if crisis_escalated and primary != CRISIS:
        # Escalate to DECISION with BROTHERS flag (per spec §6.2).
        secondary = primary
        secondary_conf = primary_conf
        primary = DECISION
        primary_conf = max(primary_conf, 0.75)

    # 5. Disguised-decision check.
    decision_escalated = False
    if not crisis_escalated:
        decision_escalated = _check_disguised_decision(text, primary)
        if decision_escalated:
            secondary = primary
            secondary_conf = primary_conf
            primary = DECISION
            primary_conf = max(primary_conf, 0.72)

    # 6. Compound resolution: when two types both score, the higher-stakes
    #    gate type wins — BUT only when the scores are close (within 40%).
    #    Large score differences (e.g. DOCTRINE=5.0 vs RELATIONAL=3.0) should
    #    not be overridden by the priority ordering.
    if (not crisis_escalated and not decision_escalated
            and secondary and secondary_conf > 0.25
            and _PRIORITY.get(secondary, 0) > _PRIORITY.get(primary, 0)):
        primary_raw = scores.get(primary, 0.0)
        secondary_raw = scores.get(secondary, 0.0)
        # Only swap when secondary score is at least 67% of primary score.
        if total > 0 and secondary_raw >= primary_raw * 0.67:
            primary, secondary = secondary, primary
            primary_conf, secondary_conf = secondary_conf, primary_conf

    # 7. TIMING framing override: "is it time to X" and "am I running from X"
    #    are TIMING questions even when X is a DECISION-shaped action. When a
    #    TIMING strong pattern explicitly frames the question, prefer TIMING.
    if (not crisis_escalated and not decision_escalated
            and primary != TIMING and scores.get(TIMING, 0.0) > 0):
        timing_strong_fires = any(p.search(text) for p in _TIMING_STRONG)
        timing_frame_fires = bool(_TIMING_FRAME.search(text))
        if timing_strong_fires and timing_frame_fires:
            # Swap primary → TIMING if TIMING score is at least 60% of primary.
            timing_raw = scores.get(TIMING, 0.0)
            primary_raw = scores.get(primary, 0.0)
            if timing_raw >= primary_raw * 0.60:
                old_primary = primary
                old_conf = primary_conf
                primary = TIMING
                primary_conf = timing_raw / total if total > 0 else 0.0
                secondary = old_primary
                secondary_conf = old_conf

    needs_clarification = primary_conf < CLARIFICATION_THRESHOLD

    return ClassificationResult(
        primary_type=primary,
        confidence=round(primary_conf, 4),
        secondary_type=secondary if secondary and secondary_conf > 0.0 else None,
        secondary_confidence=round(secondary_conf, 4),
        needs_clarification=needs_clarification,
        crisis_escalated=crisis_escalated,
        decision_escalated=decision_escalated,
        raw_scores=scores,
    )
