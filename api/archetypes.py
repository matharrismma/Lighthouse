"""Biblical archetype recognition.

The engine does not say "you are Jonah." It surfaces "this situation
shape resembles Jonah's pattern; here are the markers that matched;
here is the failure mode and the restoration path that one took."

Engine shows. Human names.

Substrate: data/archetypes/bible.jsonl  (Layer 0 source)
Schema:
  id, name, category, source, scripture[], pattern, failure_mode,
  restoration_path, markers[], rhymes_with[], contrast_to[]
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = Path(__file__).parent.parent / "data" / "archetypes"
_BIBLE_FILE = _DATA_DIR / "bible.jsonl"

# Stop words we strip when comparing situation text to markers.
_STOP = {
    "a", "an", "the", "and", "or", "but", "of", "in", "on", "at", "to",
    "for", "with", "by", "from", "as", "is", "am", "are", "was", "were",
    "be", "been", "being", "do", "does", "did", "have", "has", "had",
    "this", "that", "these", "those", "i", "me", "my", "we", "us", "our",
    "you", "your", "he", "she", "it", "its", "they", "them", "their",
    "not", "no", "if", "then", "so", "what", "who", "whom", "which",
    "very", "just", "like", "than", "more", "much", "some", "any",
    "would", "could", "should", "will", "shall", "can", "may", "might",
}

_CACHE: Dict[str, Any] = {"mtime": 0.0, "entries": []}


def _tokens(text: str) -> set:
    """Lowercase, alphanum-strip, drop stop words, return token set."""
    if not text:
        return set()
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return {t for t in s.split() if t and t not in _STOP and len(t) > 2}


def _load_entries() -> List[Dict[str, Any]]:
    """Load all archetype entries from disk, with mtime-based cache."""
    if not _BIBLE_FILE.exists():
        return []
    try:
        mtime = _BIBLE_FILE.stat().st_mtime
    except OSError:
        mtime = 0.0
    if _CACHE["entries"] and mtime <= _CACHE["mtime"]:
        return _CACHE["entries"]
    entries: List[Dict[str, Any]] = []
    try:
        with _BIBLE_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    # Precompute marker token sets for fast scoring
    for e in entries:
        e["_marker_sets"] = [_tokens(m) for m in (e.get("markers") or [])]
        e["_pattern_set"] = _tokens(e.get("pattern", ""))
        e["_failure_set"] = _tokens(e.get("failure_mode", ""))
    _CACHE["entries"] = entries
    _CACHE["mtime"] = mtime
    return entries


def list_entries() -> List[Dict[str, Any]]:
    """Public entries — strips internal precompute fields."""
    out = []
    for e in _load_entries():
        out.append({k: v for k, v in e.items() if not k.startswith("_")})
    return out


def get_entry(archetype_id: str) -> Optional[Dict[str, Any]]:
    aid = (archetype_id or "").strip().lower()
    for e in _load_entries():
        if e.get("id", "").lower() == aid:
            return {k: v for k, v in e.items() if not k.startswith("_")}
    return None


def recognize(situation: str, top_k: int = 3) -> Dict[str, Any]:
    """Surface the closest archetypes for a situation description.

    Returns top_k candidates with confidence and matched markers.
    Confidence is overlap-based, not a verdict. Engine shows the
    pattern; the human names whether it fits.
    """
    text = (situation or "").strip()
    if not text:
        return {"situation": "", "candidates": []}

    sit_tokens = _tokens(text)
    if not sit_tokens:
        return {"situation": text, "candidates": []}

    entries = _load_entries()
    scored: List[Tuple[float, Dict[str, Any], List[Dict[str, Any]]]] = []

    for e in entries:
        # Score each marker: overlap of sit_tokens with marker tokens.
        # A marker counts as "hit" if it has at least 1 token overlap
        # AND that token isn't trivial (handled by stop list + len filter).
        hits: List[Dict[str, Any]] = []
        marker_score = 0.0
        for marker_text, marker_set in zip(e.get("markers", []), e["_marker_sets"]):
            if not marker_set:
                continue
            overlap = sit_tokens & marker_set
            if overlap:
                # Score = overlap_size / marker_token_count (Jaccard-ish)
                local = len(overlap) / max(1, len(marker_set))
                marker_score += local
                hits.append({
                    "marker": marker_text,
                    "matched_terms": sorted(overlap),
                    "local_score": round(local, 3),
                })

        # Small bonus for overlap with the pattern + failure_mode prose.
        pattern_overlap = sit_tokens & e["_pattern_set"]
        failure_overlap = sit_tokens & e["_failure_set"]
        prose_bonus = (len(pattern_overlap) + len(failure_overlap)) / 50.0

        total = marker_score + prose_bonus
        if total > 0:
            scored.append((total, e, hits))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[: max(1, top_k)]

    if not top:
        return {
            "situation": text,
            "candidates": [],
            "note": "No archetype markers matched. Engine has no shape to surface; describe the situation in more concrete terms.",
        }

    max_score = top[0][0] if top else 1.0
    candidates = []
    for score, entry, hits in top:
        # Confidence is relative to the top match — surfaces "this is
        # roughly half as strong as the leader" rather than claiming
        # a calibrated probability.
        confidence = round(score / max(0.001, max_score), 3) if max_score > 0 else 0.0
        candidates.append({
            "id": entry.get("id"),
            "name": entry.get("name"),
            "category": entry.get("category"),
            "scripture": entry.get("scripture", []),
            "pattern": entry.get("pattern", ""),
            "failure_mode": entry.get("failure_mode", ""),
            "restoration_path": entry.get("restoration_path", ""),
            "matched_markers": hits,
            "score": round(score, 3),
            "confidence": confidence,
            "rhymes_with": entry.get("rhymes_with", []),
            "contrast_to": entry.get("contrast_to", []),
        })

    return {
        "situation": text,
        "candidates": candidates,
        "note": "Engine surfaces patterns. Human names whether they fit.",
    }


def verify_archetype_pattern(situation: str = "", text: str = "", **kwargs) -> Dict[str, Any]:
    """Polymathic verifier interface.

    Accepts either `situation` or `text` (alias) so the polymathic
    dispatcher can hand it the same field it gives other verifiers.
    Returns the canonical verifier shape: verdict + data.
    """
    src = (situation or text or "").strip()
    if not src:
        return {
            "verdict": "INSUFFICIENT",
            "reason": "no situation text provided",
            "data": {"candidates": []},
        }
    rec = recognize(src, top_k=3)
    cands = rec.get("candidates", [])
    if not cands:
        return {
            "verdict": "QUARANTINE",
            "reason": "no archetype shape recognized in this situation",
            "data": rec,
        }
    top = cands[0]
    # The engine never says CONCORDANT for an archetype — only
    # PROVISIONAL ("this shape is present, name it yourself") or
    # QUARANTINE if nothing matches.
    return {
        "verdict": "PROVISIONAL",
        "reason": f"closest pattern: {top['name']} ({top['category']})",
        "data": rec,
    }
