"""office_models.py — run the from-scratch office classifiers in the engine.

No lineage, no dependencies. Loads the small JSON models trained by
tools/office_train.py (pure-Python multinomial Naive Bayes) and predicts an
office decision in the same shape the teacher produced — so it's a drop-in for
the Shepherd / Scribe / Steward decision, with Anthropic kept as fallback
during rollout. CPU-instant; the models are a few KB each.

    from api import office_models
    d = office_models.predict("steward", "live traffic is high right now")
    # -> {"aspect": "provision", "decision": "yield", "gate": ""}  or None if no model
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

_MODEL_DIR = Path(__file__).parent.parent / "data" / "offices" / "models"
_TOKEN_RE = re.compile(r"[a-z0-9']+")
_CACHE: Dict[str, Any] = {}
_LOCK = Lock()

STEWARD_DECISIONS = {"keep": ["admit", "quarantine", "deny"],
                     "provision": ["work", "yield"],
                     "build": ["build", "defer"]}


def _toks(s: str) -> List[str]:
    # Word-level tokens for NB fields. Must match tools/office_train.toks().
    return _TOKEN_RE.findall((s or "").lower())


# Char-n-gram hashing for NN fields. Must match tools/office_nn_train.hash_feats().
_NN_BUCKETS_DEFAULT = 5000
_NN_LO_DEFAULT = 3
_NN_HI_DEFAULT = 5


def _hash_ngrams(text: str, lo: int, hi: int, buckets: int) -> List[int]:
    s = "$" + (text or "").lower() + "$"
    out = set()
    for n in range(lo, hi + 1):
        for i in range(len(s) - n + 1):
            out.add(hash(s[i:i + n]) % buckets)
    return list(out)


def _is_nn_field(fm: dict) -> bool:
    """NN fields store `classes` as a list + a weight matrix `W`; NB stores
    `classes` as a dict of per-class log-priors + token-logprob tables."""
    return isinstance(fm.get("classes"), list) and "W" in fm


def _load(office: str):
    with _LOCK:
        if office in _CACHE:
            return _CACHE[office]
        p = _MODEL_DIR / f"{office}.json"
        model = None
        if p.exists():
            try:
                model = json.loads(p.read_text("utf-8"))
            except Exception:
                model = None
        _CACHE[office] = model
        return model


def reload() -> None:
    """Drop the cache so freshly-trained models are picked up (call after retrain)."""
    with _LOCK:
        _CACHE.clear()


def available(office: str) -> bool:
    return _load(office) is not None


def _score(fm: dict, text: str) -> Tuple[Dict[str, float], bool]:
    """Return ({class: score}, is_already_probability). Handles both NB
    (returns log-scores) and NN (returns softmax probabilities directly)."""
    if _is_nn_field(fm):
        classes = fm["classes"]
        W = fm["W"]
        lo = fm.get("ngram_lo", _NN_LO_DEFAULT)
        hi = fm.get("ngram_hi", _NN_HI_DEFAULT)
        buckets = fm.get("buckets", _NN_BUCKETS_DEFAULT)
        feats = _hash_ngrams(text, lo, hi, buckets)
        n = len(classes)
        logits = [0.0] * n
        for f in feats:
            if 0 <= f < len(W):
                row = W[f]
                for c in range(n):
                    logits[c] += row[c]
        m = max(logits) if logits else 0.0
        exps = [math.exp(l - m) for l in logits]
        s = sum(exps) or 1.0
        return {classes[i]: exps[i] / s for i in range(n)}, True
    # NB
    out: Dict[str, float] = {}
    toks = _toks(text)
    for c, p in fm["classes"].items():
        sc = p["log_prior"]
        tk = p["tok"]
        un = p["unseen"]
        for t in toks:
            sc += tk.get(t, un)
        out[c] = sc
    return out, False


def _predict_field(fm: dict, text: str, allowed=None) -> Optional[str]:
    scores, _ = _score(fm, text)
    if allowed:
        restricted = {c: v for c, v in scores.items() if c in allowed}
        scores = restricted or scores
    return max(scores, key=scores.get) if scores else None


def _softmax_max(scores: Dict[str, float], already_probs: bool) -> float:
    """Top-class probability. For NB log-scores, softmax first; for NN
    already-normalized probabilities, just take the max."""
    if not scores:
        return 0.0
    if already_probs:
        return max(scores.values())
    vals = list(scores.values())
    m = max(vals)
    exps = [math.exp(v - m) for v in vals]
    s = sum(exps) or 1.0
    return max(exps) / s


def predict(office: str, text: str) -> Optional[Dict[str, Any]]:
    """Predict the office decision, or None if no trained model is present."""
    model = _load(office)
    if not model:
        return None
    fm = model.get("fields", {})
    out: Dict[str, Any] = {}
    if office == "shepherd":
        out["action"] = _predict_field(fm["action"], text) if "action" in fm else "route"
        if out.get("action") == "route" and "tool" in fm:
            out["tool"] = _predict_field(fm["tool"], text)
    elif office == "scribe":
        if "kind" in fm:
            out["kind"] = _predict_field(fm["kind"], text)
        if "route" in fm:
            out["route"] = _predict_field(fm["route"], text)
    elif office == "steward":
        asp = _predict_field(fm["aspect"], text) if "aspect" in fm else None
        out["aspect"] = asp
        if "decision" in fm:
            out["decision"] = _predict_field(fm["decision"], text, allowed=STEWARD_DECISIONS.get(asp))
        out["gate"] = ""
        if asp == "keep" and "gate" in fm:
            out["gate"] = _predict_field(fm["gate"], text)
    else:
        return None
    out["via"] = "office_model"
    return out


def predict_with_confidence(office: str, text: str) -> Optional[Tuple[Dict[str, Any], Dict[str, float]]]:
    """Like predict(), plus per-field top-class probability — used by the
    engine's hybrid wiring (local when confident; Anthropic on uncertainty)."""
    model = _load(office)
    if not model:
        return None
    fm = model.get("fields", {})
    out: Dict[str, Any] = {}
    conf: Dict[str, float] = {}

    def _pick(name: str, allowed=None):
        if name not in fm:
            return None
        scores, is_probs = _score(fm[name], text)
        if allowed:
            restricted = {c: v for c, v in scores.items() if c in allowed}
            scores = restricted or scores
        out[name] = max(scores, key=scores.get) if scores else None
        conf[name] = _softmax_max(scores, already_probs=is_probs)
        return out[name]

    if office == "shepherd":
        _pick("action")
        if not out.get("action"):
            out["action"] = "route"
        if out["action"] == "route":
            _pick("tool")
    elif office == "scribe":
        _pick("kind")
        _pick("route")
    elif office == "steward":
        _pick("aspect")
        _pick("decision", allowed=STEWARD_DECISIONS.get(out.get("aspect")))
        out["gate"] = ""
        if out.get("aspect") == "keep":
            _pick("gate")
    else:
        return None
    out["via"] = "office_model"
    return out, conf
