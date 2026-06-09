"""embeddings.py — local semantic embeddings via on-box Ollama (nomic-embed-text).

The curated lexicon (api/synonymy.py) handles the common synonyms explainably.
This adds SEMANTIC reach for what the lexicon can't enumerate — "my prayer life
has gone cold" ~ "I feel far from God" — using a model that runs ENTIRELY on the
box (Ollama, 127.0.0.1). No data leaves; $0 per call; conduit, not source.

Design for the integrity bar ("a false connection is worse than none"):
  - Every function DEGRADES TO None / 0.0 on any failure (Ollama down, timeout,
    bad response) so every caller falls back to the deterministic curated path.
    The semantic layer can only ADD a match above a conservative cosine threshold;
    it never blocks and never replaces the explainable lexicon result.
  - Vectors are cached in-process by text so a person's prior shares aren't
    re-embedded every turn.

Threshold guidance (measured on nomic-embed-text, 2026-06-08): related pairs
scored 0.67–0.86, unrelated 0.22–0.43 — a wide gap. Callers use ~0.60.
"""
from __future__ import annotations

import json
import math
import os
import threading
import urllib.request
from typing import List, Optional

_URL = os.environ.get("NH_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
_MODEL = os.environ.get("NH_EMBED_MODEL", "nomic-embed-text")
_TIMEOUT = float(os.environ.get("NH_EMBED_TIMEOUT", "8"))

_LOCK = threading.Lock()
_CACHE: dict = {}          # text-key -> vector
_CACHE_MAX = 4000
_AVAIL: Optional[bool] = None


def _embed_raw(text: str) -> Optional[List[float]]:
    try:
        req = urllib.request.Request(
            _URL + "/api/embeddings",
            data=json.dumps({"model": _MODEL, "prompt": text[:2000]}).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            v = json.load(r).get("embedding")
        return v if (isinstance(v, list) and v) else None
    except Exception:
        return None


def embed(text: str) -> Optional[List[float]]:
    """The embedding vector for a text, or None on any failure. Cached in-process."""
    text = (text or "").strip()
    if not text:
        return None
    key = text[:512]
    with _LOCK:
        v = _CACHE.get(key)
    if v is not None:
        return v
    v = _embed_raw(text)
    if v is None:
        return None
    with _LOCK:
        if len(_CACHE) >= _CACHE_MAX:
            _CACHE.clear()
        _CACHE[key] = v
    return v


def available() -> bool:
    """True if the local embedder answers. Cached after the first probe so callers
    can cheaply skip the semantic path when Ollama isn't up (e.g. local dev)."""
    global _AVAIL
    if _AVAIL is None:
        _AVAIL = embed("ok") is not None
    return _AVAIL


def cosine(a: Optional[List[float]], b: Optional[List[float]]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / math.sqrt(na * nb)
