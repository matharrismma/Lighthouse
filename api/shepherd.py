"""shepherd.py — The Interviewer (LOOP 12).

Two roles, separately costed:

  THE INTERVIEWER (this module) — cheap, free, conversational.
    Job: ask follow-ups until the question is shaped well enough to be answered.
    Never burns a search. Never calls a paid API. Never even walks the cards.

  THE WALKER (api/cards.py /cards/walk) — the expensive role.
    Only fires when the Interviewer says ready_to_walk.

Two invariants:
  - Even a "wasted" call leaves cards. Every walk that fires writes its result
    into quarantine as cards. Bounded waste.
  - The user experience continuously trains the intake. Every interview is
    persisted as a quarantined interview-card. The training tool walks the
    archive nightly and tunes the Interviewer's heuristics.

Voice (Matt's, not generic-AI):
  - Short sentences. Declarative. Biblical-tradition idioms.
  - "Set these on the table" not "Here are some helpful results"
  - "I don't have this one yet" not "I couldn't find any relevant information"
  - "Bring me a source and we'll start a card" — invite, not apologize.
  - Never sound like a corporate chatbot. Shepherd is a small-town pastor with
    a deep library.

Endpoints:
  POST /shepherd/interview   one turn of the conversation
  POST /shepherd/clarify     legacy alias for /interview
  GET  /shepherd/intake/stats     intake telemetry counts
  GET  /shepherd/intake/abandoned  queries the user dropped off on (operator backlog)

Hard cap: 3 follow-ups per interview. Always offers "just walk" escape.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore

REPO = Path(__file__).resolve().parent.parent
INTERVIEWS_DIR = REPO / "data" / "quarantine" / "interviews"
CARDS_DIR = REPO / "data" / "cards"

# ---------- Voice patterns (Matt's voice for Shepherd) ----------

OPENING_LINES = {
    "audience": (
        "Quick — who's this for? "
        "Yourself, your kids, or a sermon / class you're preparing?"
    ),
    "tradition": (
        "Confession you read this through? "
        "1689 Baptist, WCF, Three Forms, Heidelberg — or you'd like all of them?"
    ),
    "use": (
        "What are you doing with it? "
        "Understanding it, memorizing it, or teaching it to someone else?"
    ),
    "specificity_doctrinal": (
        "Sharpen this for me. {topic} covers a lot — "
        "are you asking about its meaning, its mode, who it's for, or how it works?"
    ),
    "specificity_broad": (
        "Bring it tighter. When you say '{topic}', "
        "is there a specific verse, hymn, or moment that prompted the question?"
    ),
    "scope_size": (
        "How much do you want? "
        "One card to chew on, a short walk (5-7), or a full study (10-15)?"
    ),
    "time_horizon": (
        "When are you going to use this? "
        "Right now, this week's family time, or a longer season of study?"
    ),
    "out_of_scope": (
        "The library doesn't have cards on this one yet. "
        "Bring me a source — a verse, an author, a recipe card — and we'll start a card together. "
        "Or I can flag this for Matt to add to the backlog."
    ),
}

NARRATION_OPENERS = [
    "Pull these in order. Each one points to its source. The walk is the lesson.",
    "Set them on the table. Read each one against where it came from.",
    "Walk these. The connections between them are the path.",
    "Here. The cards know more than I do. Read them, not me.",
]

# ---------- Specificity detection (rule-based, free) ----------

# Patterns that indicate the question is already well-shaped — straight to Walker.
SHAPED_PATTERNS = [
    # Named scripture references: Genesis, John 3:16, Romans 8:28-30, 1 Cor 13
    re.compile(r"\b(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|Song|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation)\s*\d+", re.IGNORECASE),
    # Named catechism Qs: "Q1", "Q33", "question 1"
    re.compile(r"\b(?:WSC|WLC|HC|catechism)\s*(?:Q\s*)?\d+", re.IGNORECASE),
    re.compile(r"\bQ\s*\d{1,3}\b"),
    # Named creeds
    re.compile(r"\b(?:Apostles'?|Nicene|Chalcedon(?:ian)?|Athanasian|Westminster|Heidelberg|Belgic|Canons of Dort)\b", re.IGNORECASE),
    # Named hymns (substring match against a few load-bearing titles)
    re.compile(r"\b(?:amazing grace|holy holy holy|doxology|come thou fount|a mighty fortress|how great thou art|be thou my vision|crown him|love divine)\b", re.IGNORECASE),
    # Named church fathers
    re.compile(r"\b(?:Augustine|Aquinas|Athanasius|Chrysostom|Tertullian|Irenaeus|Origen|Ambrose|Gregory|Basil|Cyril|Calvin|Luther|Edwards|Bunyan|Spurgeon|Owen|Bavinck|Hodge|Warfield|Machen|Berkhof|Murray|Sproul|Piper)\b", re.IGNORECASE),
    # Specific phrases the library has cards on
    re.compile(r"\bchief end of man\b", re.IGNORECASE),
    re.compile(r"\bregulative principle\b", re.IGNORECASE),
    re.compile(r"\bordo salutis\b", re.IGNORECASE),
]

# Audience inference: keywords that signal who this is for
AUDIENCE_PATTERNS = {
    "kids": [
        r"\bmy (?:kids?|child(?:ren)?|sons?|daughters?|boys?|girls?)\b",
        r"\bkids?\b", r"\bchild(?:ren)?\b",
        r"\bteach(?:ing)?\s+(?:them|kid|my)",
        r"\bSunday school\b",
    ],
    "sermon": [
        r"\bsermon\b", r"\bpreaching\b", r"\bpreach\b", r"\bpulpit\b",
        r"\bSunday service\b", r"\bclass I'?m teaching\b", r"\bfor a class\b",
    ],
    "self": [
        r"\bfor myself\b", r"\bjust me\b", r"\bmyself\b",
        r"\bI'?m studying\b", r"\bI want to learn\b", r"\bwant to understand\b",
        r"\bmyself, ?just me\b",
    ],
    "family_worship": [
        r"\bfamily worship\b", r"\bfamily devotion", r"\bfamily night\b",
        r"\bat the (?:dinner )?table\b",
    ],
}

# Tradition lens inference
TRADITION_PATTERNS = {
    "1689": [r"\b1689\b", r"\bBaptist confession\b", r"\bReformed Baptist\b"],
    "WCF": [r"\bWCF\b", r"\bWestminster Confession\b", r"\bPresbyterian\b", r"\bPCA\b", r"\bOPC\b"],
    "TFU": [r"\bThree Forms\b", r"\bBelgic\b", r"\bCanons of Dort\b", r"\bDutch Reformed\b"],
    "Heidelberg": [r"\bHeidelberg\b", r"\bGerman Reformed\b"],
    "Lutheran": [r"\bLutheran\b", r"\bLCMS\b", r"\bWELS\b", r"\bBook of Concord\b"],
    "Anglican": [r"\b39 Articles\b", r"\bAnglican\b", r"\bBook of Common Prayer\b"],
}

# Doctrinal-query detection — needs the tradition lens follow-up
DOCTRINAL_KEYWORDS = re.compile(
    r"\b(?:baptism|eucharist|communion|lord'?s supper|justif(?:y|ication|ied)|"
    r"sanctif(?:y|ication|ied)|election|predestin|atonement|imputation|"
    r"regeneration|adoption|union with Christ|covenant|sabbath|"
    r"law and gospel|antinomian|free will|sovereignty|infralapsarian|"
    r"supralapsarian|providence|theodicy|trinity|hypostatic|incarnation|"
    r"resurrection|second coming|millennium|kingdom of God|church government)\b",
    re.IGNORECASE,
)

# Use intent inference
USE_INTENT_PATTERNS = {
    "understand": [r"\bunderstand", r"\bwhat does (?:it|this) mean\b", r"\bjust curious\b"],
    "memorize": [r"\bmemori[sz]e\b", r"\blearn by heart\b", r"\brecite\b"],
    "teach": [r"\bteach\b", r"\bteaching\b", r"\bexplain to\b", r"\bhelp my\b"],
    "prepare": [r"\bprepar(?:e|ing)\b", r"\bwrit(?:e|ing)\b", r"\bsermon\b", r"\blesson plan\b"],
}

# Scope size — how many cards to surface in the walk. Throttles /cards/walk k.
SCOPE_SIZE_PATTERNS = {
    "one": [r"\bone card\b", r"\bjust one\b", r"\bsingle card\b", r"\bquick\b"],
    "short": [r"\bshort walk\b", r"\b(?:five|seven|5|7) cards?\b", r"\bbrief\b"],
    "study": [r"\bfull study\b", r"\bdeep dive\b", r"\bten or fifteen\b", r"\b1[05] cards?\b", r"\bfull walk\b"],
}

# Time horizon — when this is going to be used. Controls urgency vs depth.
TIME_HORIZON_PATTERNS = {
    "now": [r"\bright now\b", r"\bthis moment\b", r"\btoday\b", r"\bin a minute\b"],
    "this_week": [r"\bthis week\b", r"\bsunday\b", r"\bfamily time\b", r"\bfamily worship\b", r"\bnext few days\b"],
    "season": [r"\bover the next\b", r"\bnext month\b", r"\bthis season\b", r"\b(?:advent|lent|easter|christmas)\b", r"\bsemester\b", r"\blong[- ]?term\b"],
}


def _infer_scope_size(text: str) -> Optional[str]:
    for size, patterns in SCOPE_SIZE_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return size
    return None


def _infer_time_horizon(text: str) -> Optional[str]:
    for horizon, patterns in TIME_HORIZON_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return horizon
    return None


# Map scope_size → walk k (the Walker reads this from shaped_query metadata)
SCOPE_SIZE_TO_K = {
    "one": 1,
    "short": 7,
    "study": 14,
}


def _infer_use_intent(text: str) -> Optional[str]:
    for intent, patterns in USE_INTENT_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return intent
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _interview_id(seed: str) -> str:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"interview_{h}"


def _detect_shaped(query: str) -> bool:
    """Returns True if the query is specific enough to walk straight away."""
    if not query or len(query.strip()) < 4:
        return False
    for pat in SHAPED_PATTERNS:
        if pat.search(query):
            return True
    return False


def _infer_audience(text: str) -> Optional[str]:
    text_lower = text.lower()
    for audience, patterns in AUDIENCE_PATTERNS.items():
        for p in patterns:
            if re.search(p, text_lower):
                return audience
    return None


def _infer_tradition(text: str) -> Optional[str]:
    for tradition, patterns in TRADITION_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                return tradition
    return None


def _is_doctrinal(text: str) -> bool:
    return bool(DOCTRINAL_KEYWORDS.search(text))


def _save_interview_card(card: dict):
    INTERVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    p = INTERVIEWS_DIR / f"{card['id']}.json"
    p.write_text(json.dumps(card, indent=2), encoding="utf-8")


def _load_interview(interview_id: str) -> Optional[dict]:
    p = INTERVIEWS_DIR / f"{interview_id}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _all_interviews():
    if not INTERVIEWS_DIR.exists():
        return
    for f in INTERVIEWS_DIR.glob("*.json"):
        try:
            yield json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue


def _build_shaped_query(
    original: str,
    audience: Optional[str],
    tradition: Optional[str],
    use_intent: Optional[str],
    scope_size: Optional[str] = None,
    time_horizon: Optional[str] = None,
) -> str:
    """Combine the original query with inferred context into a query the Walker can use."""
    parts = [original]
    if audience:
        parts.append(f"[audience:{audience}]")
    if tradition:
        parts.append(f"[lens:{tradition}]")
    if use_intent:
        parts.append(f"[use:{use_intent}]")
    if scope_size:
        parts.append(f"[scope:{scope_size}]")
    if time_horizon:
        parts.append(f"[when:{time_horizon}]")
    return " ".join(parts)


# ---------- Request / response schemas ----------

if APIRouter is not None:
    class InterviewTurn(BaseModel):
        query: str  # the user's current message
        interview_id: Optional[str] = None  # continue an existing interview, or start new
        asked_by: Optional[str] = "anon"  # household_id or 'anon'
        skip_to_walk: bool = False  # user pressed "just walk"
        topic_hint: Optional[str] = None  # the original topic if we're answering a clarifier


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.post("/shepherd/interview")
    def interview(payload: InterviewTurn):
        # Load existing interview or start a new one
        if payload.interview_id:
            interview_card = _load_interview(payload.interview_id)
            if interview_card is None:
                raise HTTPException(404, f"No interview with id {payload.interview_id}")
        else:
            # New interview — id derived from query + asked_by + timestamp
            iid = _interview_id(f"{payload.query}::{payload.asked_by}::{_now()[:13]}")
            interview_card = {
                "id": iid,
                "kind": "search",  # uses search subtype for storage; conceptually an interview
                "title": f"Interview: {payload.query[:80]}",
                "body": "",
                "source": {"label": "shepherd interview", "url": "", "ref": "", "authority_tier": "engine_derived"},
                "shelf": "intake",
                "box": "interviews",
                "bands": [],
                "connections": [],
                "author": "shepherd",
                "created_at": _now(),
                "visibility": "private",
                "lifecycle_stage": "quarantine",
                "volatility": "current",
                "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
                "extra": {
                    "query": payload.query,
                    "asked_by": payload.asked_by or "anon",
                    "turns": [],  # each turn: {role, text, ts}
                    "audience": None,
                    "tradition": None,
                    "use_intent": None,
                    "scope_size": None,
                    "time_horizon": None,
                    "doctrinal": False,
                    "followups_asked": 0,
                    "outcome": "in_progress",  # in_progress | ready_to_walk | abandoned | out_of_scope
                    "shaped_query": None,
                    "walk_card_id": None,
                },
            }

        # Append this user turn
        interview_card["extra"]["turns"].append({
            "role": "user",
            "text": payload.query,
            "ts": _now(),
        })

        # Combine all user text for inference
        all_user_text = " ".join(
            t["text"] for t in interview_card["extra"]["turns"] if t["role"] == "user"
        )
        original_topic = interview_card["extra"]["turns"][0]["text"]

        # User pressed "just walk" — converge
        if payload.skip_to_walk:
            shaped = _build_shaped_query(
                original_topic,
                interview_card["extra"].get("audience"),
                interview_card["extra"].get("tradition"),
                interview_card["extra"].get("use_intent"),
                interview_card["extra"].get("scope_size"),
                interview_card["extra"].get("time_horizon"),
            )
            interview_card["extra"]["outcome"] = "ready_to_walk"
            interview_card["extra"]["shaped_query"] = shaped
            interview_card["updated_at"] = _now()
            _save_interview_card(interview_card)
            return {
                "interview_id": interview_card["id"],
                "state": "ready_to_walk",
                "shaped_query": shaped,
                "audience": interview_card["extra"]["audience"],
                "tradition": interview_card["extra"]["tradition"],
                "use_intent": interview_card["extra"]["use_intent"],
                "scope_size": interview_card["extra"].get("scope_size"),
                "time_horizon": interview_card["extra"].get("time_horizon"),
                "recommended_k": SCOPE_SIZE_TO_K.get(interview_card["extra"].get("scope_size") or "", 7),
                "shepherd_says": "Walking now.",
            }

        # Infer what we can from accumulated text
        audience = interview_card["extra"].get("audience") or _infer_audience(all_user_text)
        tradition = interview_card["extra"].get("tradition") or _infer_tradition(all_user_text)
        use_intent = interview_card["extra"].get("use_intent") or _infer_use_intent(all_user_text)
        scope_size = interview_card["extra"].get("scope_size") or _infer_scope_size(all_user_text)
        time_horizon = interview_card["extra"].get("time_horizon") or _infer_time_horizon(all_user_text)
        doctrinal = interview_card["extra"].get("doctrinal") or _is_doctrinal(all_user_text)
        shaped_already = _detect_shaped(original_topic)

        interview_card["extra"]["audience"] = audience
        interview_card["extra"]["tradition"] = tradition
        interview_card["extra"]["use_intent"] = use_intent
        interview_card["extra"]["scope_size"] = scope_size
        interview_card["extra"]["time_horizon"] = time_horizon
        interview_card["extra"]["doctrinal"] = doctrinal

        followups_so_far = interview_card["extra"]["followups_asked"]

        # Convergence rules
        # Rule 1: query is already specific enough → walk
        if shaped_already and followups_so_far == 0:
            shaped = _build_shaped_query(original_topic, audience, tradition, None, scope_size, time_horizon)
            interview_card["extra"]["outcome"] = "ready_to_walk"
            interview_card["extra"]["shaped_query"] = shaped
            interview_card["updated_at"] = _now()
            _save_interview_card(interview_card)
            return {
                "interview_id": interview_card["id"],
                "state": "ready_to_walk",
                "shaped_query": shaped,
                "recommended_k": SCOPE_SIZE_TO_K.get(scope_size or "", 7),
                "shepherd_says": "That's specific. Walking it now.",
            }

        # Rule 2: hard cap reached → walk with whatever we have
        if followups_so_far >= 3:
            shaped = _build_shaped_query(
                original_topic, audience, tradition,
                interview_card["extra"].get("use_intent"),
                scope_size, time_horizon,
            )
            interview_card["extra"]["outcome"] = "ready_to_walk"
            interview_card["extra"]["shaped_query"] = shaped
            interview_card["updated_at"] = _now()
            _save_interview_card(interview_card)
            return {
                "interview_id": interview_card["id"],
                "state": "ready_to_walk",
                "shaped_query": shaped,
                "recommended_k": SCOPE_SIZE_TO_K.get(scope_size or "", 7),
                "shepherd_says": "Enough. Let's walk.",
            }

        # Track which ask_kinds we've already used so we never loop on the same question
        asked_kinds = set(
            t.get("ask_kind") for t in interview_card["extra"]["turns"]
            if t.get("role") == "shepherd" and t.get("ask_kind")
        )

        # Rule 3: pick the most leverage-y next follow-up that we haven't asked yet
        next_question = None
        ask_kind = None

        # Priority A: audience (always useful, quickest to answer)
        if "audience" not in asked_kinds and audience is None and followups_so_far < 3:
            next_question = OPENING_LINES["audience"]
            ask_kind = "audience"

        # Priority B: tradition lens (only for doctrinal queries)
        elif "tradition" not in asked_kinds and doctrinal and tradition is None and followups_so_far < 3:
            next_question = OPENING_LINES["tradition"]
            ask_kind = "tradition"

        # Priority C: specificity (only if query is broad)
        elif "specificity" not in asked_kinds and len(original_topic.split()) <= 3 and followups_so_far < 3:
            template = OPENING_LINES["specificity_doctrinal"] if doctrinal else OPENING_LINES["specificity_broad"]
            next_question = template.format(topic=original_topic)
            ask_kind = "specificity"

        # Priority D: use intent
        elif "use_intent" not in asked_kinds and interview_card["extra"].get("use_intent") is None and followups_so_far < 3:
            next_question = OPENING_LINES["use"]
            ask_kind = "use_intent"

        # Priority E: scope_size — directly throttles /cards/walk k.
        # Surface this early when the query looks expensive (broad, doctrinal,
        # or use_intent suggests "preparing" or "teaching"). Asking saves the
        # back-end from doing a 7-card walk when the visitor wanted 1.
        elif "scope_size" not in asked_kinds and scope_size is None and followups_so_far < 3 and (
            doctrinal or use_intent in ("teach", "prepare") or len(original_topic.split()) <= 4
        ):
            next_question = OPENING_LINES["scope_size"]
            ask_kind = "scope_size"

        # Priority F: time_horizon — controls urgency vs depth.
        # Useful when use_intent is "teach" or "prepare" — different cards
        # surface for "Sunday morning" vs "next semester."
        elif "time_horizon" not in asked_kinds and time_horizon is None and followups_so_far < 3 and (
            use_intent in ("teach", "prepare") or audience in ("kids", "family_worship", "sermon")
        ):
            next_question = OPENING_LINES["time_horizon"]
            ask_kind = "time_horizon"

        # Nothing left to ask? Converge.
        if not next_question:
            shaped = _build_shaped_query(
                original_topic, audience, tradition,
                interview_card["extra"].get("use_intent"),
                scope_size, time_horizon,
            )
            interview_card["extra"]["outcome"] = "ready_to_walk"
            interview_card["extra"]["shaped_query"] = shaped
            interview_card["updated_at"] = _now()
            _save_interview_card(interview_card)
            return {
                "interview_id": interview_card["id"],
                "state": "ready_to_walk",
                "shaped_query": shaped,
                "recommended_k": SCOPE_SIZE_TO_K.get(scope_size or "", 7),
                "shepherd_says": "I've got what I need. Walking.",
            }

        # Append Shepherd's turn, persist, return
        interview_card["extra"]["turns"].append({
            "role": "shepherd",
            "text": next_question,
            "ts": _now(),
            "ask_kind": ask_kind,
        })
        interview_card["extra"]["followups_asked"] = followups_so_far + 1
        interview_card["updated_at"] = _now()
        _save_interview_card(interview_card)

        return {
            "interview_id": interview_card["id"],
            "state": "needs_followup",
            "shepherd_says": next_question,
            "ask_kind": ask_kind,
            "followups_asked": interview_card["extra"]["followups_asked"],
            "followups_remaining": 3 - interview_card["extra"]["followups_asked"],
            "can_skip_to_walk": True,
        }

    @router.post("/shepherd/abandon")
    def abandon_interview(body: dict):
        iid = body.get("interview_id")
        if not iid:
            raise HTTPException(400, "interview_id required")
        card = _load_interview(iid)
        if card is None:
            raise HTTPException(404, "No such interview")
        card["extra"]["outcome"] = "abandoned"
        card["extra"]["abandoned_reason"] = (body.get("reason") or "")[:200]
        card["updated_at"] = _now()
        _save_interview_card(card)
        return {"status": "abandoned", "interview_id": iid}

    @router.get("/shepherd/intake/stats")
    def intake_stats():
        total = 0
        by_outcome = {}
        by_audience = {}
        by_tradition = {}
        followup_counts = []
        for c in _all_interviews():
            total += 1
            ex = c.get("extra", {})
            o = ex.get("outcome", "in_progress")
            by_outcome[o] = by_outcome.get(o, 0) + 1
            a = ex.get("audience") or "unknown"
            by_audience[a] = by_audience.get(a, 0) + 1
            t = ex.get("tradition") or "unspecified"
            by_tradition[t] = by_tradition.get(t, 0) + 1
            followup_counts.append(ex.get("followups_asked", 0))
        avg_followups = round(sum(followup_counts) / len(followup_counts), 2) if followup_counts else 0
        converged = by_outcome.get("ready_to_walk", 0)
        return {
            "total_interviews": total,
            "by_outcome": by_outcome,
            "by_audience": by_audience,
            "by_tradition": by_tradition,
            "avg_followups_before_walk": avg_followups,
            "convergence_rate": round(converged / total, 3) if total else None,
        }

    @router.get("/shepherd/intake/abandoned")
    def intake_abandoned(limit: int = 50):
        """Surface queries that dropped off — operator backlog signal.
        These are the things we should build cards for next."""
        items = []
        for c in _all_interviews():
            ex = c.get("extra", {})
            if ex.get("outcome") not in ("abandoned", "in_progress"):
                continue
            items.append({
                "interview_id": c.get("id"),
                "query": ex.get("query"),
                "asked_by": ex.get("asked_by"),
                "outcome": ex.get("outcome"),
                "followups_asked": ex.get("followups_asked", 0),
                "audience": ex.get("audience"),
                "tradition": ex.get("tradition"),
                "created_at": c.get("created_at"),
            })
        # Sort newest first
        items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        return {"count": len(items[:limit]), "items": items[:limit]}

    return router
