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
    trail = [{"id": p.get("id"), "name": p.get("name"),
              "why_considered": p.get("matched_triggers")}
             for p in candidates if p.get("id") != chosen.get("id")]
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


def narrow(situation: str, chosen_id: Optional[str] = None, max_candidates: int = 6) -> Dict[str, Any]:
    """Rung 2: the multi-level narrowing. First call surfaces the floor's candidate
    patterns for a need (the right choices at the right size). The human picks one
    (chosen_id); the floor hands the answer + trail + Christ. Retrieval is choosing.

    NOTE: drawing the WHOLE well when no protocol fits is the next increment — it
    needs SEMANTIC ranking (a naive keyword merge surfaces noise: common words like
    'god' flood it). Until then, no-pattern honestly returns the open walk rather
    than hand a false trail. (Gemma 4 local embeddings — free, on-box, no data
    leak — is the aligned tool for that ranking.)"""
    from api import walk as _walk
    situation = (situation or "").strip()
    if not situation:
        return {"arrived": False, "narrowable": False, "note": "empty"}
    protos = _walk.recognize_protocols(situation, max_results=max_candidates)
    if not protos:
        return {"arrived": False, "narrowable": False,
                "note": "No specific pattern matched — this needs the open walk."}
    if chosen_id:
        chosen = next((p for p in protos if p.get("id") == chosen_id), None)
        if chosen is None:
            wide = _walk.recognize_protocols(situation, max_results=50)
            chosen = next((p for p in wide if p.get("id") == chosen_id), None)
        if chosen is None:
            return {"arrived": False, "narrowable": True, "note": "choice not found among matches"}
        return _arrive(situation, chosen, protos)
    if len(protos) == 1:
        return _arrive(situation, protos[0], protos)
    return {
        "arrived": False, "narrowable": True, "level": "pattern",
        "say": "The floor knows several patterns that touch this. Which is closest to yours?",
        "choices": [{"id": p.get("id"), "name": p.get("name"),
                     "summary": p.get("summary", ""),
                     "scripture": _coerce_list(p.get("scripture")),
                     "why": p.get("matched_triggers")} for p in protos],
        "considered": len(protos),
    }


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


# A Shepherd decision is FREE (keep / the local office-model / keyword floor) or
# PAID (the oracle). The thesis, made visible for the offices: the oracle ratio
# falls and the learned share rises as the local model takes over with use.
_VIA_FREE = {"keep", "office_model", "office_model_hybrid", "fallback", "deterministic"}
_VIA_PAID = {"shepherd"}  # the Anthropic oracle tier


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
        paid = sum(v for k, v in by_via.items() if k in _VIA_PAID)
        learned = sum(v for k, v in by_via.items()
                      if k in ("office_model", "office_model_hybrid"))
        out[office] = {
            "decisions": total,
            "by_via": by_via,
            "oracle_dependence_ratio": round(paid / total, 4) if total else None,
            "free_ratio": round((total - paid) / total, 4) if total else None,
            "learned_ratio": round(learned / total, 4) if total else None,
        }
    return {"days": days, "offices": out,
            "note": ("Shepherd FREE = keep / office-model / keyword floor; PAID = "
                     "oracle. The oracle ratio falls and the learned share rises "
                     "as the local model takes over — the thesis, for the offices.")}


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
