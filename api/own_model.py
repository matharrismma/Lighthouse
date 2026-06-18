"""own_model.py — Narrow Highway's OWN model, built to grow until it stands alone.

The goal (Matt): work toward NOT needing a separate model. Ours will be small at
first; over time it improves until it no longer needs Ollama or any other — they
can still work with it, but they are the shrinking fallback, not the engine.

How it grows: DISTILLATION from the fallback. Every time the fallback LLM decides
something, we record it as a lesson; our model learns it, and next time handles
that kind of input itself. The model acts ONLY when it is confident; otherwise it
defers to the fallback and learns from what the fallback chose. So coverage rises
on its own with use, and the fallback is needed less and less.

Owned by construction: pure Python, no torch, no numpy, no external runtime — it
runs anywhere the engine runs (a droplet, a laptop, a microSD). Weights are a
small JSON file we own (data/own_model/router.json).

v1 task: INTENT ROUTING — the highest-volume edge. Given what a person brought,
predict the intent (note / search / settings / learn / open / verify / list /
draft / ask). A transparent online multinomial naive Bayes over word features.
Next owned components (same pattern, same loop): a prose->spec parser, then
retrieval-first drafting, then a small generative core for the residual.
"""
from __future__ import annotations

import json
import math
import re
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

_DIR = Path(__file__).parent.parent / "data" / "own_model"
_PATH = _DIR / "router.json"
_LOCK = threading.Lock()

# Intents the router can serve NATIVELY with no generation at all — a wrong guess
# here is non-destructive (a note is kept; open/learn/search/settings just route).
# verify / list / draft / ask still need the fallback to produce content, so the
# router never acts on those yet (it only learns them, for later owned components).
NATIVE_INTENTS = {"note", "search", "settings", "learn", "open"}

# Bootstrap lessons so the model is useful before it has seen real traffic. These
# are erased by nothing — real distilled examples accumulate on top of them.
_SEED = {
    "note": ["remember the wifi password is", "note to self", "keep this", "remember that",
             "don't forget to", "a thought i had", "remember my locker combo is"],
    "search": ["look up", "search for", "find the verse about", "what do we have on",
               "show me articles about", "find information on"],
    "settings": ["my settings", "my preferences", "change my profile", "my household",
                 "my schedule", "open settings", "account settings"],
    "learn": ["teach me", "i want to learn", "explain how", "help me understand",
              "teach my child", "learn about photosynthesis", "how do fractions work"],
    "open": ["open the chess board", "open the calendar", "play a game", "open the bible",
             "start the radio", "open the reading plan"],
    "verify": ["is it true that", "the speed of light is", "91 is a prime number",
               "the derivative of", "water boils at", "verify that", "is 7 times 13"],
    "list": ["milk eggs bread", "grocery list", "to do list", "packing list",
             "add to my shopping list", "things to buy"],
    "draft": ["write an email to", "draft a message to", "tell my mom that",
              "compose a letter to", "reply to my boss saying"],
    "ask": ["why does", "what should i do about", "how can i", "what is the meaning of",
            "i need advice on", "can you help me with"],
}

_TOK = re.compile(r"[a-z0-9']{2,}")


def _toks(text: str):
    return _TOK.findall((text or "").lower())[:60]


def _blank():
    return {"classes": {}, "feat": {}, "feat_tot": {}, "vocab": {},
            "docs": 0, "native": 0, "fallback": 0, "v": 1}


def _load() -> dict:
    try:
        if _PATH.exists():
            return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return _blank()


def _save(m: dict) -> None:
    try:
        _DIR.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(m), encoding="utf-8")
    except Exception:
        pass


def _learn_into(m: dict, text: str, intent: str) -> None:
    toks = _toks(text)
    if not intent or not toks:
        return
    m["classes"][intent] = m["classes"].get(intent, 0) + 1
    fc = m["feat"].setdefault(intent, {})
    for t in toks:
        fc[t] = fc.get(t, 0) + 1
        m["vocab"][t] = m["vocab"].get(t, 0) + 1
    m["feat_tot"][intent] = m["feat_tot"].get(intent, 0) + len(toks)
    m["docs"] = m.get("docs", 0) + 1


def _ensure_seeded(m: dict) -> dict:
    if m.get("docs", 0) == 0:
        for intent, examples in _SEED.items():
            for ex in examples:
                _learn_into(m, ex, intent)
        m["seeded"] = True
    return m


# Module-level cache (rebuilt on write). One process, low write volume.
_M = _ensure_seeded(_load())
if not _M.get("seeded_saved"):
    _M["seeded_saved"] = True
    _save(_M)


def predict(text: str) -> Tuple[Optional[str], float]:
    """Return (intent, confidence in 0..1). Confidence is the posterior of the
    top class; callers gate on it. (None, 0.0) when there is nothing to go on."""
    m = _M
    toks = _toks(text)
    classes = m.get("classes") or {}
    if not toks or not classes:
        return (None, 0.0)
    vocab = len(m.get("vocab") or {}) or 1
    total_docs = sum(classes.values()) or 1
    known = sum(1 for t in toks if t in (m.get("vocab") or {}))
    if known == 0:
        return (None, 0.0)
    logp: Dict[str, float] = {}
    for c, cn in classes.items():
        lp = math.log(cn / total_docs)
        fc = m["feat"].get(c, {})
        denom = (m["feat_tot"].get(c, 0) or 0) + vocab  # Laplace
        for t in toks:
            lp += math.log(((fc.get(t, 0) or 0) + 1) / denom)
        logp[c] = lp
    # softmax for a comparable confidence
    top = max(logp, key=logp.get)
    mx = logp[top]
    z = sum(math.exp(v - mx) for v in logp.values())
    conf = 1.0 / z if z > 0 else 0.0
    return (top, round(conf, 4))


def route(text: str, min_conf: float = 0.88, min_docs: int = 150) -> Optional[dict]:
    """If our own model is confident AND the intent is one it can serve natively
    (no generation), return a routing dict; else None (caller falls back). Records
    the coverage either way is the caller's job via mark_native/mark_fallback."""
    if (_M.get("docs", 0) or 0) < min_docs:
        return None
    intent, conf = predict(text)
    if intent in NATIVE_INTENTS and conf >= min_conf:
        return {"intent": intent, "confidence": conf}
    return None


def learn(text: str, intent: str, *, was_native: bool = False) -> None:
    """Distill: record one (input -> intent) lesson and update coverage. For
    fallback decisions, first measure whether our model WOULD have agreed
    (shadow accuracy, before learning this example) — that rising curve is how we
    know when to trust it to act on its own."""
    with _LOCK:
        if not was_native:
            pi, _ = predict(text)
            _M["shadow_total"] = _M.get("shadow_total", 0) + 1
            if pi == intent:
                _M["shadow_hits"] = _M.get("shadow_hits", 0) + 1
            _M["fallback"] = _M.get("fallback", 0) + 1
        else:
            _M["native"] = _M.get("native", 0) + 1
        _learn_into(_M, text, intent)
        _save(_M)


def stats() -> dict:
    m = _M
    nat, fb = m.get("native", 0), m.get("fallback", 0)
    tot = nat + fb
    return {
        "docs": m.get("docs", 0),
        "intents": sorted((m.get("classes") or {}).keys()),
        "vocab": len(m.get("vocab") or {}),
        "decisions": tot,
        "native": nat,
        "fallback": fb,
        "native_coverage": round(nat / tot, 4) if tot else 0.0,
        "shadow_total": m.get("shadow_total", 0),
        "shadow_hits": m.get("shadow_hits", 0),
        "shadow_accuracy": round(m.get("shadow_hits", 0) / m["shadow_total"], 4) if m.get("shadow_total") else 0.0,
        "note": "our own model; grows by distilling from the fallback. shadow_accuracy "
                "= how often it already agrees with the fallback; when it stays high, it "
                "can take over more, and the fallback is needed less.",
        "ts": int(time.time()),
    }
