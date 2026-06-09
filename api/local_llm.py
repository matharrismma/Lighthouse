"""local_llm.py — the local 'mouth': text generation via on-box Ollama.

The Steward's FREE tier, placed UNDER the paid oracle: the local model (a small
instruct model, qwen2.5:3b by default) answers first; the paid Anthropic oracle
fires only when the local one can't (down, timeout, or its output fails the
caller's quality gate). This drives the oracle-dependence ratio down at $0 and
keeps everything on the box — no data leaves.

Like api/embeddings.py, every function DEGRADES TO None on any failure so callers
fall back to the paid oracle and then the deterministic vetted stems. The local
model can only REPLACE a paid call when it produces something the caller validates;
it never blocks and never lowers the floor.

Measured on the box (CPX31, CPU-only, 2026-06-09): ~1.5s warm / ~6s cold for a
short question at ~20 tok/s. Model unloads after OLLAMA_KEEP_ALIVE idle.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Optional

_URL = os.environ.get("NH_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
_MODEL = os.environ.get("NH_LOCAL_LLM", "qwen2.5:3b")
_TIMEOUT = float(os.environ.get("NH_LOCAL_LLM_TIMEOUT", "25"))

_AVAIL: Optional[bool] = None


def generate(prompt: str, system: Optional[str] = None,
             max_tokens: int = 80, temperature: float = 0.7) -> Optional[str]:
    """One completion from the local model, or None on any failure. Non-streaming,
    bounded by num_predict + timeout so it can't hang the request."""
    prompt = (prompt or "").strip()
    if not prompt:
        return None
    try:
        body = {
            "model": _MODEL, "prompt": prompt[:6000], "stream": False,
            "options": {"num_predict": max_tokens, "temperature": temperature},
        }
        if system:
            body["system"] = system
        req = urllib.request.Request(
            _URL + "/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            out = (json.load(r).get("response") or "").strip()
        return out or None
    except Exception:
        return None


def available() -> bool:
    """True if the local model answers. Cached after the first probe so callers
    cheaply skip the local tier when Ollama/the model isn't up (e.g. local dev)."""
    global _AVAIL
    if _AVAIL is None:
        _AVAIL = generate("Reply with the single word: ok", max_tokens=5) is not None
    return _AVAIL
