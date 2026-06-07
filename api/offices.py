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
import time
from pathlib import Path
from typing import Any, Dict, Optional

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
