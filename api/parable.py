"""The Parable lens — surface the closest precedent as a small story.

This module is not a verifier and does not generate. It retrieves
pre-rendered parable seeds keyed to packets in the substrate, using
the same axis-Jaccard + trigger-keyword retrieval as Coach.

The parable is the rhetorical form. The trail underneath — source
packet, axes hit, score — is the proof. Generation is form, not
content. The engine still eliminates; it does not invent.

Front door for the visitor who does not yet know what they need.
"""
from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from api import walk as _walk_mod

_SEEDS_FILE = Path(__file__).parent.parent / "data" / "parables" / "seeds.jsonl"
_SEEDS_CACHE: Dict[str, Any] = {"mtime": 0.0, "items": []}


def _load_seeds() -> List[Dict[str, Any]]:
    """mtime-cached parable seeds load."""
    if not _SEEDS_FILE.exists():
        return []
    try:
        mtime = _SEEDS_FILE.stat().st_mtime
    except OSError:
        return []
    if _SEEDS_CACHE["items"] and mtime <= _SEEDS_CACHE["mtime"]:
        return _SEEDS_CACHE["items"]
    items: List[Dict[str, Any]] = []
    try:
        with _SEEDS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                items.append(rec)
    except OSError:
        return []
    _SEEDS_CACHE["mtime"] = mtime
    _SEEDS_CACHE["items"] = items
    return items


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return len(a & b) / union


def _score_seed(seed: Dict[str, Any], sit_axes: Set[str], sit_lower: str) -> float:
    s_axes = set(seed.get("axes") or [])
    ax_score = _jaccard(sit_axes, s_axes)

    kw_bonus = 0.0
    triggers = (seed.get("triggers") or {}).get("keywords") or []
    if sit_lower and triggers:
        hits = 0
        for kw in triggers:
            kw_l = (kw or "").lower().strip()
            if kw_l and len(kw_l) >= 3 and kw_l in sit_lower:
                hits += 1
        if hits:
            kw_bonus = min(0.30, hits * 0.08)

    return ax_score + kw_bonus


def _public_view(seed: Dict[str, Any], score: float, match_kind: str) -> Dict[str, Any]:
    return {
        "parable": {
            "id": seed.get("id"),
            "text": seed.get("parable", ""),
            "question": seed.get("question", ""),
            "gate": seed.get("gate", ""),
            "wisdom": seed.get("wisdom", ""),
        },
        "trail": {
            "source_packet_id": seed.get("source_packet_id"),
            "axes": seed.get("axes") or [],
            "triggers": (seed.get("triggers") or {}).get("keywords") or [],
            "score": round(score, 3),
            "match_kind": match_kind,
        },
    }


def find_parable(situation: str = "") -> Dict[str, Any]:
    """Find the closest parable to a situation. Empty situation returns
    a random parable. Returns the public view (parable + trail).
    """
    seeds = _load_seeds()
    if not seeds:
        return {
            "parable": None,
            "trail": None,
            "error": "no parable seeds available",
        }

    situation = (situation or "").strip()
    sit_lower = situation.lower()

    if not situation:
        chosen = random.choice(seeds)
        return _public_view(chosen, 0.0, "random")

    # Derive axes from the situation using the same Coach machinery.
    try:
        sit_axes_list = _walk_mod.derive_axes(situation)
    except Exception:
        sit_axes_list = []
    sit_axes = set(sit_axes_list)

    best: Optional[Dict[str, Any]] = None
    best_score = 0.0
    for seed in seeds:
        score = _score_seed(seed, sit_axes, sit_lower)
        if score > best_score:
            best = seed
            best_score = score

    if best is None or best_score < 0.05:
        chosen = random.choice(seeds)
        return _public_view(chosen, 0.0, "random_fallback")

    return _public_view(best, best_score, "axes_keywords")


def list_seeds() -> List[Dict[str, Any]]:
    """Public index of all parable seeds — id, source, gate, axes."""
    seeds = _load_seeds()
    return [
        {
            "id": s.get("id"),
            "source_packet_id": s.get("source_packet_id"),
            "gate": s.get("gate"),
            "axes": s.get("axes") or [],
            "preview": (s.get("parable") or "")[:120],
        }
        for s in seeds
    ]
