"""offices.py — the three offices, shared.

Shepherd (discernment) · Scribe (record) · Steward (resource).

The single canonical home for the offices' REUSABLE, deterministic logic, so the
funnel (the one front door) and app.py's /deposit flow run the SAME offices
instead of parallel copies. app.py keeps the conversational/oracle Shepherd
(phrasebook + Socratic questions); the deterministic core lives here.

Nothing here calls an oracle — these are free. That is the Steward's mandate:
keyword discernment by default; the paid oracle only when budget allows.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
_SPEND_LEDGER = REPO / "data" / "spend" / "ledger.jsonl"
_OFFICE_CORPUS = REPO / "data" / "training_corpus" / "offices"
_INTAKE_FILE = REPO / "data" / "intake" / "queue.jsonl"  # the Scribe's working queue


# ── Shepherd (discernment) ──────────────────────────────────────────────────
# Two outcomes for a deposited thought:
#   KEEP  — a personal capture (prayer / task / recipe / note / verse). It becomes
#           a private card on the person's shelf; no tool needed.
#   ROUTE — the person wants the engine to DO something. Still kept as a card so
#           nothing is lost, but the Shepherd suggests the proper tool.
# Every word the Shepherd "says" is vetted (a small phrasebook), never generated.

_DECK_OF = {
    "prayer": "prayer", "task": "task", "recipe": "recipe",
    "scripture": "scripture", "question": "question", "note": "note",
}

_SAY = {
    "keep": {
        "prayer":   "Kept on your prayer shelf. He hears it.",
        "task":     "Kept on your task shelf, so it's off your mind.",
        "recipe":   "Kept in your recipe book.",
        "scripture":"Kept with your verses to hold onto.",
        "note":     "Kept on your shelf — yours to organize.",
    },
    "route": {
        "discern":  "Let me bring this through the gates and keep what survives.",
        "verify":   "Let me check this claim against what can be verified.",
        "draft":    "I'll draft this for your review — the engine never sends.",
        "scripture":"Let me open the Scripture on this, original words first.",
        "teach":    "Let me open the learning road for this.",
        "walk":     "Let me surface what connects to this.",
    },
}


def classify_deposit(text: str):
    """Return (classification, routed_to). The deterministic Shepherd core
    (shared with app.py's /deposit). Conservative on messages — drafts only,
    never auto-sends."""
    t = (text or "").strip().lower()
    if not t:
        return ("empty", "none")
    if (t.startswith(("email ", "send ", "message ", "reply ", "dm ", "text ",
                      "draft ", "compose ", "write an email"))
            or ("@" in t and ("send" in t or "email" in t))):
        return ("message", "draft_review")
    if any(k in t for k in ("verify", "is it true", "fact check", "balanced",
                            "calculate", "compute", "prove")):
        return ("claim", "verify")
    if any(k in t for k in ("teach", "learn", "how do i", "how to", "phonics",
                            "lesson", "study with my")):
        return ("learn", "teach")
    if t.endswith("?") or t.startswith(("is ", "what ", "how ", "why ", "should ",
                                        "does ", "can ", "who ", "when ", "where ",
                                        "did ", "are ")):
        return ("question", "discern")
    return ("idea", "walk")


def _keep_deck(text: str) -> Optional[str]:
    """If the deposit is a personal capture (not a request for the engine),
    return its deck; else None (-> the Shepherd routes it to a tool)."""
    t = (text or "").strip()
    low = t.lower()
    if low.startswith(("pray", "prayer")) or "pray for" in low or "lord," in low:
        return "prayer"
    if any(k in low for k in ("recipe", "preheat", "ingredient", "tbsp", "tsp",
                              "cup of", "bake at", "simmer", "°f", "deg f")):
        return "recipe"
    if low.startswith(("todo", "to-do", "task:", "remember to", "need to", "buy ",
                       "pick up", "schedule", "don't forget")):
        return "task"
    if (any(k in low for k in ("genesis", "exodus", "psalm", "matthew", "mark ",
                               "luke", "john ", "romans", "verse")) and ":" in t):
        return "scripture"
    return None


def shepherd_route(text: str) -> Dict[str, Any]:
    """The Shepherd discerns a deposit deterministically (free).

    Returns:
      {"action": "keep",  "deck": <deck>, "say": <vetted line>, "via": "deterministic"}
      {"action": "route", "tool": <tool>, "deck": <deck>, "query": <text>,
       "say": <vetted line>, "via": "deterministic"}

    Either way the caller still keeps a private card; `action` tells the UI
    whether to offer a tool as the next step.
    """
    t = (text or "").strip()
    keep_deck = _keep_deck(t)
    if keep_deck:
        return {"action": "keep", "deck": keep_deck,
                "say": _SAY["keep"].get(keep_deck, _SAY["keep"]["note"]),
                "via": "deterministic"}

    # Only route when the person wants the engine to DO something (a question,
    # a claim to check, a message to draft, a thing to learn). A plain
    # declarative thought is KEPT on the note shelf — "everything you capture
    # is yours"; they can walk it later if they choose.
    classification, routed = classify_deposit(t)
    _ROUTE = {"draft_review": "draft", "verify": "verify",
              "discern": "discern", "teach": "teach"}
    if routed in _ROUTE:
        tool = _ROUTE[routed]
        deck = {"draft": "task", "verify": "question",
                "discern": "question", "teach": "question"}[tool]
        return {"action": "route", "tool": tool, "deck": deck, "query": t,
                "say": _SAY["route"][tool],
                "classification": classification, "via": "deterministic"}
    return {"action": "keep", "deck": "note", "say": _SAY["keep"]["note"],
            "classification": classification, "via": "deterministic"}


# The Shepherd's vetted voice — it SELECTS a pre-approved line, never generates
# prose. The keyword + office-model tiers use this phrasebook; the oracle writes
# its own "say" but is held to the same brevity by the prompt.
_PHRASEBOOK_PATH = REPO / "data" / "offices" / "shepherd_phrasebook.json"
_PHRASEBOOK_CACHE: Optional[Dict[str, Any]] = None


def shepherd_say(action: str, tool: str = "") -> str:
    """Select a vetted Shepherd line for (action, tool/deck) from the phrasebook,
    falling back to the built-in _SAY lines."""
    global _PHRASEBOOK_CACHE
    if _PHRASEBOOK_CACHE is None:
        try:
            _PHRASEBOOK_CACHE = json.loads(_PHRASEBOOK_PATH.read_text("utf-8"))
        except Exception:
            _PHRASEBOOK_CACHE = {}
    pb = _PHRASEBOOK_CACHE or {}
    if action == "ask":
        lines = pb.get("ask") or ["Can you tell me a little more about what you're hoping for?"]
    elif action == "keep":
        return _SAY["keep"].get(tool, _SAY["keep"]["note"])
    else:
        lines = (pb.get("route") or {}).get(tool) or [_SAY["route"].get(tool, _SAY["route"]["walk"])]
    import random as _r
    return _r.choice(lines) if lines else _SAY["route"]["walk"]


def _deck_for_tool(tool: str) -> str:
    return {"draft": "task", "verify": "question", "discern": "question",
            "teach": "question", "scripture": "scripture", "walk": "note"}.get(tool, "note")


_SHEPHERD_DISCERN_PROMPT = """You are the Shepherd of the Narrow Highway discernment engine, which serves Jesus Christ. The engine is a conduit, not a source: it eliminates what is not the answer so the narrow path is illuminated by what survives.

A person has deposited a thought. Through BRIEF Socratic questioning, discern what they truly need, then route to the proper tool. A Socratic question helps THEM clarify their own intent; it never interrogates or lectures. Speak warmly, plainly, briefly.

Tools you may route to:
- discern  : weigh a teaching, claim, or question through the four gates (Scripture, doctrine, 69 verifiers). For "is this sound / true / biblical?"
- walk     : surface related substrate (cards) for an idea or topic. For exploring, "what connects?"
- verify   : a specific factual or computational claim (math, science, dates).
- scripture: resolve or study a Bible reference or term.
- teach     : the person wants to learn, or to teach a child, a subject — phonics/reading, writing, math, science, history, Bible, or work skills. Route here to open the learning pathway. This is the homeschool road; start the youngest at phonics.
- draft    : the person wants to send a message/email. Draft it for THEIR review. The engine never sends.

Rules:
- Ask AT MOST one short clarifying question, and ONLY if the proper tool is genuinely unclear. If you can already discern it, route immediately; do not ask needlessly.
- One sentence per question.
- Teach along the way: when something is hard, you may relate it simply — a short metaphor or a parable (biblical or plain) plus a memorable hook — but keep it to one or two sentences inside "say". Never lecture.
- Respond with ONLY a JSON object, nothing else:
  {"action":"ask","say":"<one-sentence Socratic question>"}
  or
  {"action":"route","tool":"discern|walk|verify|scripture|teach|draft","query":"<refined query for the tool>","say":"<one warm sentence telling the person what you're doing>"}"""


def shepherd_discern(history: List[Dict[str, str]], allow_keep: bool = True,
                     allow_oracle: bool = True) -> Dict[str, Any]:
    """The ONE Shepherd, shared by every door. Tiers, cheapest first:

      0. KEEP        — a personal capture (prayer/task/recipe/verse/note). Free,
                       deterministic. Skipped for route-only doors (allow_keep=False).
      1. office-model— the local, from-scratch learned classifier. Free.
                       Confidence-gated; below threshold it falls through.
      2. oracle      — Anthropic, ONLY when allow_oracle AND the Steward admits
                       budget (>= $1 remaining). The spend is recorded.
      3. keyword     — the deterministic floor. Free, always answers.

    Every tier mints a Shepherd training pair, so each use teaches the local
    model and the oracle-dependence ratio shrinks with use. `history` is a list
    of {role, content}; the last user turn is what's discerned.
    """
    last_user = ""
    for m in reversed(history):
        if m.get("role") == "user":
            last_user = m.get("content", "")
            break
    query0 = (history[0]["content"] if history else last_user)

    # Tier 0 — keep (personal capture).
    if allow_keep:
        kd = _keep_deck(last_user)
        if kd:
            obj = {"action": "keep", "deck": kd,
                   "say": _SAY["keep"].get(kd, _SAY["keep"]["note"]), "via": "keep"}
            log_office_pair("shepherd", last_user, json.dumps(obj, ensure_ascii=False))
            return obj

    # Tier 1 — the local learned Shepherd (free, confidence-gated).
    action_thresh = float(os.environ.get("NH_SHEP_ACTION_THRESH", "0.85"))
    tool_thresh = float(os.environ.get("NH_SHEP_TOOL_THRESH", "0.70"))
    try:
        from api import office_models as _om
        r = _om.predict_with_confidence("shepherd", last_user)
        if r:
            d, conf = r
            action = d.get("action") or "route"
            tool = d.get("tool") or "walk"
            if (conf.get("action", 0.0) >= action_thresh
                    and (action == "ask" or conf.get("tool", 0.0) >= tool_thresh)):
                obj = {"action": action, "query": query0,
                       "say": shepherd_say(action, tool if action == "route" else ""),
                       "via": "office_model"}
                if action == "route":
                    obj["tool"] = tool
                    obj["deck"] = _deck_for_tool(tool)
                log_office_pair("shepherd", last_user, json.dumps(obj, ensure_ascii=False),
                                meta={"via": "office_model_hybrid",
                                      "conf_action": round(float(conf.get("action", 0.0)), 3),
                                      "conf_tool": round(float(conf.get("tool", 0.0)), 3)})
                return obj
    except Exception:
        pass

    # Tier 2 — the oracle. Only when allowed AND the Steward admits the spend.
    if (allow_oracle and os.environ.get("ANTHROPIC_API_KEY")
            and steward_budget_remaining_usd() >= 1.0):
        try:
            import anthropic
            import re as _re
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            msgs = [{"role": m["role"], "content": m["content"]} for m in history if m.get("content")]
            resp = client.messages.create(
                model=os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5"),
                max_tokens=300, system=_SHEPHERD_DISCERN_PROMPT, messages=msgs)
            txt = "".join(getattr(b, "text", "") for b in resp.content).strip()
            try:
                ti = getattr(resp.usage, "input_tokens", 0) or 0
                to = getattr(resp.usage, "output_tokens", 0) or 0
                ledger_record("shepherd", ti * 3e-6 + to * 15e-6)  # Steward records the cost
            except Exception:
                pass
            mj = _re.search(r"\{.*\}", txt, _re.S)
            obj = json.loads(mj.group(0)) if mj else {}
            if obj.get("action") in ("ask", "route"):
                obj["via"] = "shepherd"
                if obj.get("action") == "route" and obj.get("tool") and "deck" not in obj:
                    obj["deck"] = _deck_for_tool(obj["tool"])
                log_office_pair("shepherd", msgs[-1]["content"] if msgs else last_user,
                                json.dumps(obj, ensure_ascii=False))
                return obj
        except Exception:
            pass

    # Tier 3 — the deterministic floor (free). keep (if allowed) or route.
    sr = shepherd_route(last_user)
    if sr.get("action") == "keep" and not allow_keep:
        sr = {"action": "route", "tool": "walk", "deck": "note", "query": last_user,
              "say": shepherd_say("route", "walk")}
    sr["via"] = "fallback"
    sr.setdefault("query", query0)
    log_office_pair("shepherd", last_user, json.dumps(sr, ensure_ascii=False))
    return sr


# ── The narrowing (THE_GUIDE rung 2) — where knowledge meets discernment ─────
# "We have the answers; they sit in the well. The reach is the right question."
# The engine surfaces the right CHOICES at the right size (retrieval, not
# generation); the human's intuition picks; the floor hands the answer with the
# elimination trail and the Christ reference. system/pattern -> protocol.

def _coerce_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str) and v:
        try:
            import ast
            x = ast.literal_eval(v)
            return x if isinstance(x, list) else [v]
        except Exception:
            return [v]
    return []


def _arrive(situation, chosen, candidates):
    """Bottom of the descent: the floor hands the surviving path + the trail (what
    was set aside + why) + the Christ reference (a Bible reference). Draws the
    broader well too — the closest almanac/sealed PRECEDENT for this situation —
    so the answer is the meeting of the protocol AND the discerned record."""
    from api import walk as _walk
    scripture = _coerce_list(chosen.get("scripture"))
    steps = _coerce_list(chosen.get("steps"))
    trail = _candidate_trail(situation, chosen.get("id"), candidates)
    gates = None
    try:
        gates = _walk.four_gates_walk()
    except Exception:
        pass
    # the broader well: the closest discerned precedent (almanac / sealed record)
    precedent = None
    try:
        pr = _walk.find_precedent(situation, protocols_result=[chosen])
        if pr:
            precedent = {"summary": pr.get("wisdom") or pr.get("summary") or "",
                         "ref": pr.get("id") or pr.get("ref") or "",
                         "score": pr.get("score"), "source": pr.get("source") or pr.get("store")}
    except Exception:
        pass
    return {
        "arrived": True, "level": "protocol",
        "answer": {"id": chosen.get("id"), "name": chosen.get("name"),
                   "summary": chosen.get("summary", ""), "scripture": scripture,
                   "steps": steps, "failure_modes": _coerce_list(chosen.get("failure_modes"))},
        "precedent": precedent,
        "christ_reference": scripture[0] if scripture else "",
        "gates": gates,
        "trail": trail,
        "say": ("Here is the narrow path the floor surfaced for this. Walk it through "
                "the gates; here is what was set aside, and the Scripture it rests on."),
    }


def _candidate_trail(situation, chosen_id, candidates):
    """The elimination trail: what the Scribe ALSO surfaced and the floor set aside.
    The trail IS the reasoning — 'what survives' only means something against what
    did not. Each entry says WHY it was a candidate (its own triggers + the concepts
    it shares with the situation, via the curated lexicon), so the person can see it
    was weighed, not ignored. Used by both protocol and well arrivals so the trail is
    present everywhere an answer is."""
    from api import synonymy as _syn
    sit_concepts = _syn.concepts_in(_otoks(situation))
    trail = []
    for c in (candidates or []):
        if not c or c.get("id") == chosen_id:
            continue
        # why it was a candidate: a protocol's own matched triggers, else the concepts
        # it shares with the situation (the kind is metadata, kept in its own field —
        # not jargon in the human reason).
        why = [w for w in (c.get("why") or []) if w] if c.get("source") == "protocol" else []
        ctext = (c.get("name") or "") + " " + (c.get("summary") or "")
        for s in sorted(sit_concepts & _syn.concepts_in(_otoks(ctext))):
            if s not in why:
                why.append(s)
        trail.append({"id": c.get("id"), "name": c.get("name"),
                      "kind": c.get("kind") or c.get("source"),
                      "why_considered": why[:4] or None})
    return trail


def _arrive_well(situation, packet, candidates=None):
    """Arrival on a WELL packet (no fixed protocol): the well's wisdom + the gates
    + the Christ reference + the elimination trail (the other wisdom the Scribe
    surfaced and set aside). No steps (it's a teaching/precedent, not a protocol)."""
    from api import walk as _walk
    scripture = _coerce_list(packet.get("scripture"))
    if not scripture:
        # psalm/scripture packets carry the reference in the title, not a field
        try:
            from concordance_engine.scripture_retrieval import _REF_PATTERN
            m = _REF_PATTERN.search(packet.get("title") or "")
            if m:
                scripture = [m.group(0).strip()]
        except Exception:
            pass
    gates = None
    try:
        gates = _walk.four_gates_walk()
    except Exception:
        pass
    trail = _candidate_trail(situation, packet.get("id"), candidates)
    return {
        "arrived": True, "level": "well", "kind": packet.get("kind"),
        "answer": {"id": packet.get("id"), "name": packet.get("title") or packet.get("id"),
                   "summary": packet.get("summary") or "", "scripture": scripture,
                   "steps": [], "failure_modes": []},
        "precedent": None,
        "christ_reference": scripture[0] if scripture else "",
        "gates": gates, "trail": trail,
        "say": ("No fixed pattern fits this, but the well holds it. Weigh it through the "
                "gates; here is what else was surfaced and set aside."
                if trail else
                "No fixed pattern fits this, but the well holds it. Weigh it through the gates."),
    }


def _otoks(s):
    import re as _re
    return [w for w in _re.findall(r"[a-z']{3,}", (s or "").lower()) if w not in _WELL_NOISE]


_WELL_NOISE = set((
    "the and for with from this that what when where who how why are was were you your "
    "not but its his her she him them they too can just about have has had feel need want"
).split())


# ── SCRIBE — finds the cards (retrieval from the keeping) ────────────────────
def scribe_find(situation: str, max_candidates: int = 6) -> List[Dict[str, Any]]:
    """The Scribe finds the candidate cards: the floor's PATTERNS first
    (recognize_protocols), then the WELL's wisdom (well_retriever) when no pattern
    fits or the lone pattern is weak. Returns unified cards (the answer-space the
    Shepherd will question over)."""
    from api import walk as _walk
    from api import well_retriever as _well
    protos = _walk.recognize_protocols(situation, max_results=max_candidates)
    cards = [{"id": p.get("id"), "name": p.get("name"), "summary": p.get("summary", ""),
              "scripture": _coerce_list(p.get("scripture")), "kind": "protocol",
              "source": "protocol", "strength": int(p.get("match_strength") or 0),
              "why": p.get("matched_triggers") or [], "_proto": p} for p in protos]
    if not cards or (len(cards) == 1 and cards[0]["strength"] < 2):
        have = {c["id"] for c in cards}
        for w in _well.search(situation, limit=5):
            if w["id"] not in have:
                cards.append({"id": w["id"], "name": w["title"], "summary": w.get("summary", ""),
                              "scripture": _coerce_list(w.get("scripture")), "kind": w.get("kind"),
                              "source": "well", "strength": 0, "why": [w.get("kind")]})
    return cards


def _arrive_card(situation, card, cards):
    from api import well_retriever as _well
    if card.get("source") == "protocol" and card.get("_proto"):
        # chosen = the raw protocol (scripture/steps); candidates = the unified cards
        # (so the trail includes set-aside WELL wisdom too, not only other protocols).
        return _arrive(situation, card["_proto"], cards)
    pkt = _well.get(card["id"])
    if pkt is not None:
        return _arrive_well(situation, pkt, cards)
    return {"arrived": False, "narrowable": True, "note": "card not found"}


# ── SHEPHERD — speaks in questions (the Socratic voice) ──────────────────────
# Vetted lines (the Shepherd never generates prose on the free path). The
# Steward-gated oracle phrases a sharper, situation-specific question in prod.
_SOCRATIC = [
    "When you sit with this, what's the one thing underneath the rest?",
    "If you named the truest part of it in a single sentence, what would you say?",
    "Where do you feel the weight of it most?",
    "What part of this is yours to carry — and what part isn't?",
]
_SOCRATIC_AGAIN = [
    "Stay with it a moment — which of those is the heavier one right now?",
    "And beneath that — what's the root of it?",
]


# The Shepherd's voice — one system prompt, used by BOTH the local model and the
# paid oracle so the question reads the same whoever phrases it.
_SOCRATIC_SYS = (
    "You are the Shepherd of a Christian discernment engine. A person brought a "
    "situation; the floor surfaced these possible patterns. Ask ONE brief Socratic "
    "question (one sentence) that helps THEM discern which is the heart of it — or "
    "name what they truly need. Do NOT list the options, do not lecture, do not "
    "answer. Warm, plain, short. Output only the question.")


def _socratic_user(situation, cards):
    names = "; ".join(f"{c['name']}: {c.get('summary','')[:80]}" for c in cards[:5])
    return f"Situation: {situation}\nPatterns: {names}"


def _valid_socratic(q):
    """A gate on a GENERATED question — the same skepticism the engine gives any
    generation. A bad local question must never reach the person; if it fails this,
    the caller falls through to the paid oracle, then the vetted stems."""
    if not q:
        return False
    q = q.strip()
    if not (10 <= len(q) <= 240):
        return False
    if "?" not in q or q.count("?") > 2:          # exactly a question, not a quiz
        return False
    low = q.lower()
    bad = ("as an ai", "i cannot", "i can't", "i'm sorry", "i am sorry",
           "language model", "here are", "option 1", "option a", "1.", "2.", "•")
    return not any(b in low for b in bad)


def _first_question(text):
    """Salvage the first well-formed question from a longer local output.

    The free local model often gives a good Socratic question wrapped in extra
    prose (a lead-in, a trailing remark) that trips _valid_socratic. Rather than
    spend a paid oracle call to rephrase what we already have, lift the first
    clean question clause. Returns None if nothing salvageable — then the oracle
    takes over as before. Oracle-shrinking with no change to the voice: the words
    are still the local model's own."""
    if not text:
        return None
    # first '?'-terminated clause, with any preceding sentence/prefix trimmed off
    m = re.search(r"([^.!?\n]*\?)", text)
    if not m:
        return None
    cand = m.group(1).strip().strip('"“” ')
    return cand if _valid_socratic(cand) else None


def _shepherd_socratic_local(situation, cards):
    """The FREE local model (on-box Ollama) phrases the question — tried BEFORE the
    paid oracle. Validated; returns None on any failure or a question that doesn't
    pass the gate, so the oracle takes over. This is the Steward's oracle-shrinking
    tier: $0, no data leaves, the paid call avoided whenever the local one is good."""
    try:
        from api import local_llm as _llm
    except Exception:
        return None
    q = _llm.generate(_socratic_user(situation, cards), system=_SOCRATIC_SYS,
                      max_tokens=60, temperature=0.7)
    if _valid_socratic(q):
        return q.strip()
    # Salvage a clean question buried in extra prose rather than pay the oracle to
    # rephrase what the free local model already gave us (oracle-shrinking).
    return _first_question(q)


def _shepherd_socratic_oracle(situation, cards):
    """Steward-gated: the PAID oracle phrases the question. Now the FALLBACK beneath
    the free local model — fires only when the local one is down or its output failed
    the gate. Returns None when the Steward can't provision it (no key / over budget)
    — then the deterministic vetted stem is used."""
    if not os.environ.get("ANTHROPIC_API_KEY") or steward_budget_remaining_usd() < 1.0:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        resp = client.messages.create(
            model=os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5"), max_tokens=80,
            system=_SOCRATIC_SYS,
            messages=[{"role": "user", "content": _socratic_user(situation, cards)}])
        try:
            ti = getattr(resp.usage, "input_tokens", 0) or 0
            to = getattr(resp.usage, "output_tokens", 0) or 0
            ledger_record("shepherd", ti * 3e-6 + to * 15e-6)  # Steward records the cost
        except Exception:
            pass
        q = "".join(getattr(b, "text", "") for b in resp.content).strip()
        return q or None
    except Exception:
        return None


def _shepherd_socratic(situation, cards, again=False):
    # Steward's order: FREE local model → paid oracle → deterministic vetted stem.
    q = _shepherd_socratic_local(situation, cards)
    if q:
        return q, "shepherd_local"
    q = _shepherd_socratic_oracle(situation, cards)
    if q:
        return q, "shepherd"
    stems = _SOCRATIC_AGAIN if again else _SOCRATIC
    return stems[len(situation) % len(stems)], "vetted"


def recall_connection(situation, prior_shares, min_overlap=2):
    """The Shepherd never forgets. Given the person's PRIOR shares, find the one
    that most resonates with what they bring now — connect the dots, put in front
    of them the thread they may not see. Per-user; deterministic overlap.

    Overlap is on the CONCEPT signature (synonymy), so 'afraid' meets 'anxious' and
    'my marriage is failing' meets 'fighting with my wife' — but it stays explainable
    (shared_terms reports the matched concept/word) and purely additive: synonymy can
    only add a concept match, never invent one absent in the curated lexicon."""
    from api import synonymy as _syn
    st = _syn.signature(_otoks(situation))
    if not st or not prior_shares:
        return None
    best, best_ov = None, 0
    for c in prior_shares:
        ct = _syn.signature(_otoks((c.get("title") or "") + " " + (c.get("body") or c.get("text") or "")))
        ov = len(st & ct)
        if ov > best_ov:
            best, best_ov = c, ov
    if best is None or best_ov < min_overlap:
        # The lexicon found nothing. Reach once more with SEMANTIC embeddings
        # (local, on-box) — they catch what a curated map can't enumerate. Gated by
        # a conservative cosine so it never surfaces a false thread; silent (None)
        # when the embedder is down. The lexicon match above always wins when present.
        return _recall_semantic(situation, prior_shares)
    body = best.get("body") or best.get("text") or ""
    bt = _syn.signature(_otoks((best.get("title") or "") + " " + body))
    return {
        "id": best.get("id"), "title": best.get("title") or "",
        "when": (best.get("created_at") or best.get("deposited_at") or "")[:10],
        "snippet": body[:160], "shared_terms": sorted(st & bt)[:6],
    }


# Cosine floor for a semantic recall. Measured on nomic-embed-text (2026-06-08):
# related pairs 0.67-0.86, unrelated 0.22-0.43 — 0.60 sits in the gap with margin.
_SEMANTIC_FLOOR = float(os.environ.get("NH_RECALL_SEMANTIC_FLOOR", "0.60"))


def _recall_semantic(situation, prior_shares):
    """Semantic fallback for recall: the local embedder finds the prior share whose
    MEANING is closest, even with no shared word/concept. Returns a recall dict
    (marked via='semantic') only above the conservative floor, else None. Degrades
    to None when embeddings are unavailable — so the curated path is never weakened."""
    from api import embeddings as _emb
    sv = _emb.embed(situation)
    if sv is None:
        return None
    best, best_sim = None, 0.0
    for c in prior_shares:
        text = ((c.get("title") or "") + " " + (c.get("body") or c.get("text") or "")).strip()
        cv = _emb.embed(text)
        sim = _emb.cosine(sv, cv)
        if sim > best_sim:
            best, best_sim = c, sim
    if best is None or best_sim < _SEMANTIC_FLOOR:
        return None
    body = best.get("body") or best.get("text") or ""
    return {
        "id": best.get("id"), "title": best.get("title") or "",
        "when": (best.get("created_at") or best.get("deposited_at") or "")[:10],
        "snippet": body[:160], "shared_terms": [], "via": "semantic",
        "similarity": round(best_sim, 3),
    }


def recall_recurrence(current_pattern_ids, prior_shares):
    """The Shepherd sees the thread: among the person's PRIOR shares, how often
    have they returned to a pattern they're touching again now? The prophetic 'what
    you don't see' turn — you keep coming back here. Returns the most-recurring
    pattern + count, or None."""
    cur = set(current_pattern_ids or [])
    if not cur:
        return None
    counts = {}
    for c in prior_shares:
        for pid in (c.get("patterns") or []):
            if pid in cur:
                counts[pid] = counts.get(pid, 0) + 1
    if not counts:
        return None
    pid, n = max(counts.items(), key=lambda kv: kv[1])
    return {"pattern_id": pid, "count": n}


def _shepherd_map(situation, reply, cards):
    """The Shepherd discerns which found card the person's answer points to.
    Deterministic overlap of the reply with each card's name/summary/why."""
    rt = set(_otoks(reply))
    if not rt:
        return None
    scored = []
    for c in cards:
        ct = set(_otoks((c.get("name") or "") + " " + (c.get("summary") or "")
                        + " " + " ".join(c.get("why") or [])))
        scored.append((len(rt & ct), c))
    scored.sort(key=lambda x: -x[0])
    if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return scored[0][1]
    return None


def _shepherd_ask(situation, cards, again=False):
    """The Scribe calls the Shepherd to speak. He poses a Socratic question; the
    Steward provisions (gates the paid voice) and observes (logs the pair)."""
    q, via = _shepherd_socratic(situation, cards, again=again)
    steward = steward_check()
    log_office_pair("shepherd", situation,
                    json.dumps({"action": "ask", "via": via,
                                "cards": [c["id"] for c in cards]}, ensure_ascii=False))
    return {
        "arrived": False, "narrowable": True, "action": "ask", "via": via,
        "level": (cards[0]["source"] if cards else "pattern"),
        "say": q,
        "cards": [{"id": c["id"], "name": c["name"], "summary": c.get("summary", ""),
                   "scripture": c.get("scripture") or [], "why": c.get("why")} for c in cards],
        "steward": {"budget_remaining_usd": steward["budget_remaining_usd"]},
    }


def narrow(situation: str, reply: Optional[str] = None, chosen_id: Optional[str] = None,
           max_candidates: int = 6) -> Dict[str, Any]:
    """Rung 2, as the TRIAD. The SCRIBE finds the candidate cards; when discernment
    is needed she calls the SHEPHERD, who QUESTIONS (Socratic — never a menu); the
    person answers; the Shepherd discerns which card; the floor hands the answer +
    trail + Christ. The STEWARD provisions the paid voice and observes (logs).
    chosen_id is the explicit-pick escape hatch; reply is the person's answer."""
    from api import walk as _walk
    from api import well_retriever as _well
    situation = (situation or "").strip()
    if not situation:
        return {"arrived": False, "narrowable": False, "note": "empty"}

    cards = scribe_find(situation, max_candidates)
    if not cards:
        return {"arrived": False, "narrowable": False,
                "note": "No pattern or wisdom fit this — this needs the open walk."}

    if chosen_id:
        card = next((c for c in cards if c["id"] == chosen_id), None)
        if card is not None:
            return _arrive_card(situation, card, cards)
        pkt = _well.get(chosen_id)
        if pkt is not None:
            return _arrive_well(situation, pkt, cards)
        wide = _walk.recognize_protocols(situation, max_results=50)
        wp = next((p for p in wide if p.get("id") == chosen_id), None)
        if wp is not None:
            return _arrive(situation, wp, [])
        return {"arrived": False, "narrowable": True, "note": "choice not found"}

    # a single CONFIDENT pattern is clear — the floor answers without questioning
    if len(cards) == 1 and cards[0]["source"] == "protocol" and cards[0]["strength"] >= 2:
        return _arrive_card(situation, cards[0], cards)

    if reply:
        card = _shepherd_map(situation, reply, cards)
        if card is not None:
            return _arrive_card(situation, card, cards)
        return _shepherd_ask(situation, cards, again=True)  # still unclear — ask once more

    # discernment needed -> the Shepherd questions (Socratic)
    return _shepherd_ask(situation, cards, again=False)


# ── Steward (resource) ──────────────────────────────────────────────────────
def steward_budget_remaining_usd() -> float:
    """The Steward's resource check — what's left of the monthly cap.
    (Mirrors app.py _ledger_remaining_usd; the single implementation.)"""
    try:
        import os
        month = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m")
        spent = 0.0
        if _SPEND_LEDGER.exists():
            for ln in _SPEND_LEDGER.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                if o.get("month") == month:
                    spent += float(o.get("usd", 0) or 0)
        cap = float(os.environ.get("NH_MONTHLY_BUDGET_USD", "500") or 500)
        return round(cap - spent, 2)
    except Exception:
        return 0.0


def ledger_record(source: str, usd: float) -> None:
    """The Steward records a spend against the monthly cap (e.g. an oracle call).
    The single implementation (app.py delegates here)."""
    try:
        d = REPO / "data" / "spend"
        d.mkdir(parents=True, exist_ok=True)
        now = _dt.datetime.now(_dt.timezone.utc)
        with (d / "ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now.isoformat(), "month": now.strftime("%Y-%m"),
                                "source": source, "usd": round(float(usd), 6)}) + "\n")
    except Exception:
        pass


def steward_check(candidate_tool: str = "") -> Dict[str, Any]:
    """The Steward weighs a routing decision against resources. The deterministic
    Shepherd + the funnel are FREE, so the Steward admits by default and simply
    notes the budget. `allow_oracle` gates any future paid escalation."""
    remaining = steward_budget_remaining_usd()
    return {"office": "steward", "budget_remaining_usd": remaining,
            "allow_oracle": remaining > 0, "tool": candidate_tool}


# ── Scribe (record) ─────────────────────────────────────────────────────────
def _short_hash(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def scribe_submit(text: str, title: str = "", visitor_id: str = "",
                  url: str = "") -> Dict[str, Any]:
    """The Scribe records a contribution into the SAME intake queue the witness
    gate reads (data/intake/queue.jsonl). This is the path toward the knowledge
    bank: the gate (two-or-three witnesses + the four gates) decides admission —
    never the submitter. Returns the receipt.

    Writes the same record shape as app.py _do_intake_submit so there is one
    queue, not a parallel one.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")
    now = int(time.time())
    record = {
        "id": "q-" + _short_hash(text + str(now)),
        "submitted_at": now,
        "submitted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "title": (title or "").strip()[:200],
        "text": text[:10000],
        "url": (url or "").strip()[:400],
        "contributor_handle": "",
        "visitor_id": (visitor_id or "").strip().lower()[:64],
        "status": "new",
        "polymathic_attempted": False,
        "lang": "en",
        "via": "funnel",
    }
    _INTAKE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _INTAKE_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return {"ok": True, "id": record["id"], "status": "pending", "lane": "intake",
            "status_url": f"/intake/status/{record['id']}",
            "view_url": f"/scribe.html?id={record['id']}"}


# ── shared: each office decision becomes a training pair ─────────────────────
def log_office_pair(office: str, prompt: str, completion: str,
                    meta: Optional[dict] = None) -> None:
    """Each office's decision becomes a training pair for its future small model
    — how the body mints data for the three sovereign organs as it runs.
    (Mirrors app.py _log_office_pair; the single implementation.)"""
    try:
        _OFFICE_CORPUS.mkdir(parents=True, exist_ok=True)
        rec = {"schema": "narrowhighway.office_pair/1", "office": office,
               "prompt": prompt, "completion": completion,
               "at": _dt.datetime.now(_dt.timezone.utc).isoformat(), "meta": meta or {}}
        with (_OFFICE_CORPUS / f"{office}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


# A Shepherd decision is FREE or PAID. FREE splits three ways: DETERMINISTIC (keep
# / keyword floor / vetted stem — no model at all), LEARNED (the from-scratch
# office-model), and LOCAL_LLM (the on-box model — qwen2.5:3b — phrasing/answering
# at $0, no data leaving). PAID is the Anthropic oracle. The thesis made visible:
# the paid ratio falls as the office-model AND the on-box mouth take over with use.
_VIA_PAID = {"shepherd"}                                   # the Anthropic oracle
_VIA_LOCAL_LLM = {"shepherd_local"}                        # the on-box model (free)
_VIA_LEARNED = {"office_model", "office_model_hybrid"}     # the learned classifier
_VIA_DETERMINISTIC = {"keep", "fallback", "deterministic", "vetted"}  # no model
_VIA_FREE = _VIA_LOCAL_LLM | _VIA_LEARNED | _VIA_DETERMINISTIC


def office_stats(days: int = 30) -> Dict[str, Any]:
    """Oracle-dependence for the offices, measured from the minted training pairs
    (no separate counter to drift). Read-only."""
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()
    out: Dict[str, Any] = {}
    for office in ("shepherd", "steward", "scribe"):
        f = _OFFICE_CORPUS / f"{office}.jsonl"
        by_via: Dict[str, int] = {}
        total = 0
        if f.exists():
            for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    rec = json.loads(ln)
                except Exception:
                    continue
                if (rec.get("at") or "") < cutoff:
                    continue
                via = None
                try:
                    via = json.loads(rec.get("completion") or "{}").get("via")
                except Exception:
                    pass
                via = via or (rec.get("meta") or {}).get("via") or "unknown"
                by_via[via] = by_via.get(via, 0) + 1
                total += 1
        # teacher_distill = one-time bootstrap synthetic pairs (the distill step),
        # not live serving decisions — kept visible in by_via but excluded from the
        # ratios so they measure ACTUAL serving and the tiers sum to ~1.0.
        bootstrap = sum(v for k, v in by_via.items() if k == "teacher_distill")
        serving = total - bootstrap
        paid = sum(v for k, v in by_via.items() if k in _VIA_PAID)
        local_llm = sum(v for k, v in by_via.items() if k in _VIA_LOCAL_LLM)
        learned = sum(v for k, v in by_via.items() if k in _VIA_LEARNED)
        deterministic = sum(v for k, v in by_via.items() if k in _VIA_DETERMINISTIC)
        out[office] = {
            "decisions": total,
            "serving_decisions": serving,
            "bootstrap_pairs": bootstrap,
            "by_via": by_via,
            "oracle_dependence_ratio": round(paid / serving, 4) if serving else None,
            "free_ratio": round((serving - paid) / serving, 4) if serving else None,
            "learned_ratio": round(learned / serving, 4) if serving else None,
            # the on-box model's share — paid oracle calls it REPLACED at $0
            "local_llm_ratio": round(local_llm / serving, 4) if serving else None,
            # answered with NO model at all (the cheapest, most-verifiable tier)
            "deterministic_ratio": round(deterministic / serving, 4) if serving else None,
        }
    return {"days": days, "offices": out,
            "note": ("Shepherd tiers — PAID = the Anthropic oracle; FREE splits into "
                     "DETERMINISTIC (keep / keyword floor / vetted stem, no model), "
                     "LEARNED (the from-scratch office-model), and LOCAL_LLM (the on-box "
                     "model, qwen2.5:3b, $0 + no data leaves). oracle_dependence_ratio "
                     "falls as the office-model AND the on-box mouth take over with use.")}


def office_trend(office: str = "shepherd", days: int = 90) -> Dict[str, Any]:
    """Reconstruct the oracle-dependence TRAJECTORY from the timestamped training
    pairs — the same measure as office_stats(), evaluated at each active day. No
    separate log to drift: the decision corpus IS the source of truth, and every
    pair already carries an `at` timestamp, so the trend is BACKFILLED, not waited
    for. Returns a per-day series with both the day's own ratio AND the
    cumulative-to-date ratio (exactly what the all-time scoreboard would have read
    on that day — a skeptic can verify it). Honest about sparsity: serving_total /
    active_days are returned so the caller never plots a handful of points as a
    triumphant curve. Read-only."""
    cutoff = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).isoformat()
    f = _OFFICE_CORPUS / f"{office}.jsonl"
    by_day_serv: Dict[str, int] = {}
    by_day_paid: Dict[str, int] = {}
    if f.exists():
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rec = json.loads(ln)
            except Exception:
                continue
            at = rec.get("at") or ""
            if at < cutoff:
                continue
            via = None
            try:
                via = json.loads(rec.get("completion") or "{}").get("via")
            except Exception:
                pass
            via = via or (rec.get("meta") or {}).get("via") or "unknown"
            if via == "teacher_distill":   # bootstrap synthetic, not a serving decision
                continue
            day = at[:10]
            if not day:
                continue
            by_day_serv[day] = by_day_serv.get(day, 0) + 1
            if via in _VIA_PAID:
                by_day_paid[day] = by_day_paid.get(day, 0) + 1
    series = []
    cum_s = cum_p = 0
    for day in sorted(by_day_serv):
        s = by_day_serv[day]
        p = by_day_paid.get(day, 0)
        cum_s += s
        cum_p += p
        series.append({
            "date": day,
            "serving": s,
            "paid": p,
            "oracle_dep": round(p / s, 4) if s else None,
            "cum_serving": cum_s,
            "cum_paid": cum_p,
            "cum_oracle_dep": round(cum_p / cum_s, 4) if cum_s else None,
        })
    return {
        "office": office,
        "serving_total": cum_s,
        "paid_total": cum_p,
        "active_days": len(series),
        "first": series[0]["date"] if series else None,
        "last": series[-1]["date"] if series else None,
        "series": series,
        "note": ("Each point is the oracle-dependence the scoreboard would have read "
                 "that day. cum_oracle_dep is the verifiable all-time ratio; oracle_dep "
                 "is the day's own. Sparse early data is shown plainly, not smoothed."),
    }


# ── The learning loop: fold live decisions back in, retrain, reload ──────────
# Only HIGH-QUALITY live decisions become training data: the oracle's own calls
# (via=shepherd) are gold ground truth, and deterministic keeps (via=keep) are
# high-precision. The keyword FLOOR (fallback) is uncertain and the office-model's
# own predictions would self-reinforce, so neither is folded.
_FOLD_VIAS = {"shepherd", "keep"}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().split())


def _fold_live_into_train(office: str) -> int:
    """Append high-quality live decisions to <office>.train.jsonl (deduped by
    prompt). Free — turns real, paid-for oracle calls into training signal so the
    local model learns to replace them."""
    live = _OFFICE_CORPUS / f"{office}.jsonl"
    train = _OFFICE_CORPUS / f"{office}.train.jsonl"
    if not live.exists():
        return 0
    seen = set()
    if train.exists():
        for ln in train.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                seen.add(_norm(json.loads(ln).get("prompt", "")))
            except Exception:
                pass
    out = []
    for ln in live.read_text(encoding="utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            rec = json.loads(ln)
        except Exception:
            continue
        via = None
        try:
            via = json.loads(rec.get("completion") or "{}").get("via")
        except Exception:
            pass
        via = via or (rec.get("meta") or {}).get("via")
        if via not in _FOLD_VIAS:
            continue
        p = rec.get("prompt", "")
        np = _norm(p)
        if not np or np in seen:
            continue
        seen.add(np)
        out.append(json.dumps({"prompt": p, "completion": rec.get("completion"),
                               "meta": {"via": "live_" + str(via), "split": "train"}},
                              ensure_ascii=False))
    if out:
        with train.open("a", encoding="utf-8") as f:
            f.write("\n".join(out) + "\n")
    return len(out)


def retrain(office: str = "all", fold_live: bool = True) -> Dict[str, Any]:
    """Close the loop (FREE): fold high-quality live decisions into the train set,
    retrain the local from-scratch office model, and reload it so the next request
    uses it. The teacher-distill bootstrap is separate (it spends oracle budget);
    this is the continuous, no-cost path that compounds with real use."""
    targets = ["shepherd", "scribe", "steward"] if office == "all" else [office]
    report: Dict[str, Any] = {}
    for off in targets:
        folded = _fold_live_into_train(off) if fold_live else 0
        try:
            from tools import office_train as _ot
            res = _ot.train_office(off)  # writes data/offices/models/<off>.json
            report[off] = {"folded_live": folded, "trained": bool(res),
                           "eval": (res or {}).get("report") if res else None}
        except Exception as e:
            report[off] = {"folded_live": folded, "trained": False, "error": str(e)[:200]}
    try:
        from api import office_models as _om
        _om.reload()  # drop the cache so the fresh model is picked up
    except Exception:
        pass
    return {"retrained": targets, "report": report}
