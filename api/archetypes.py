"""Biblical archetype recognition.

The engine does not say "you are Jonah." It surfaces "this situation
shape resembles a combination of Jonah, Saul, and Esther; here are
the markers that matched; here is the failure mode and restoration
path each one took."

A real person is rarely one archetype — usually a combination. The
recognizer returns the blend, not a singleton. The combination IS the
answer.

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
# Source order is also authority order: Bible is the primary substrate;
# literature and history sit below as secondary patterns. Lower-authority
# entries don't override higher ones if id collisions ever occur.
_SOURCE_FILES = [
    ("Bible",      _DATA_DIR / "bible.jsonl"),
    ("Literature", _DATA_DIR / "literature.jsonl"),
    ("History",    _DATA_DIR / "history.jsonl"),
]
# Backward compat for any code that imports the old name
_BIBLE_FILE = _SOURCE_FILES[0][1]

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


# Category-pair signatures. Order-independent: keyed by frozenset.
# These are LOOKUPS — the engine doesn't generate phrases for unknown
# pairs. If a combination isn't in this table, the engine surfaces the
# raw categories and lets the human name the blend.
_PAIR_SIGNATURES: Dict[frozenset, str] = {
    # original 36
    frozenset({"fleer", "fleer"}):                     "doubled flight",
    frozenset({"fleer", "disqualified"}):              "fleeing toward disqualification",
    frozenset({"fleer", "betrayer"}):                  "fleeing that ends in betrayal",
    frozenset({"fleer", "wrestler"}):                  "running while wrestling",
    frozenset({"fleer", "yielder"}):                   "outward yielding masking inner flight",
    frozenset({"fleer", "called_reluctant"}):          "reluctant calling becoming flight",
    frozenset({"fleer", "converted"}):                 "the fleer turned back",
    frozenset({"fleer", "positioned"}):                "position with the heart turned away",
    frozenset({"yielder", "yielder"}):                 "consenting trust",
    frozenset({"yielder", "wrestler"}):                "yielding through the wrestle",
    frozenset({"yielder", "positioned"}):              "yielding into position",
    frozenset({"yielder", "faithful_exile"}):          "faithful yielding in exile",
    frozenset({"yielder", "called_reluctant"}):        "reluctance giving way to yield",
    frozenset({"wrestler", "wrestler"}):               "doubled wrestle",
    frozenset({"wrestler", "positioned"}):             "wrestling into position",
    frozenset({"wrestler", "faithful_exile"}):         "wrestling faithful in exile",
    frozenset({"wrestler", "called_reluctant"}):       "wrestling with the calling",
    frozenset({"wrestler", "denier_restored"}):        "the wrestle that includes denial",
    frozenset({"denier_restored", "converted"}):       "denial restored, then converted",
    frozenset({"denier_restored", "wrestler"}):        "denial inside the wrestle",
    frozenset({"denier_restored", "called_reluctant"}): "reluctant call that includes denial",
    frozenset({"betrayer", "disqualified"}):           "betrayal compounding disqualification",
    frozenset({"betrayer", "converted"}):              "betrayer turned, if turning happens",
    frozenset({"converted", "converted"}):             "doubled conversion",
    frozenset({"converted", "positioned"}):            "the converted placed in position",
    frozenset({"converted", "called_reluctant"}):      "conversion through reluctant calling",
    frozenset({"converted", "faithful_exile"}):        "converted to faithful exile",
    frozenset({"positioned", "positioned"}):           "doubled positioning",
    frozenset({"positioned", "faithful_exile"}):       "positioned faithful exile",
    frozenset({"positioned", "called_reluctant"}):     "reluctance into position",
    frozenset({"faithful_exile", "faithful_exile"}):   "doubled exile faithfulness",
    frozenset({"faithful_exile", "called_reluctant"}): "reluctant calling, faithful in exile",
    frozenset({"called_reluctant", "called_reluctant"}): "doubled reluctant calling",
    frozenset({"called_reluctant", "disqualified"}):   "reluctance hardening into disqualification",
    frozenset({"disqualified", "disqualified"}):       "doubled disqualification",
    frozenset({"parable_figure", "parable_figure"}):   "parable inside parable",
    frozenset({"type_of_christ", "type_of_christ"}):   "doubled type",
    # second wave covering the 15 new categories
    frozenset({"shepherd_leader", "shepherd_leader"}): "doubled shepherd-king",
    frozenset({"shepherd_leader", "intercessor"}):     "shepherd who stands in the gap",
    frozenset({"shepherd_leader", "wrestler"}):        "shepherd-king inside the wrestle",
    frozenset({"shepherd_leader", "disqualified"}):    "shepherd disqualified by his own appetites",
    frozenset({"shepherd_leader", "proud_humbled"}):   "shepherd-king who must be humbled",
    frozenset({"intercessor", "intercessor"}):         "doubled intercession",
    frozenset({"intercessor", "yielder"}):             "intercession out of yielded place",
    frozenset({"intercessor", "wrestler"}):            "intercession wrestled out",
    frozenset({"intercessor", "watchman"}):            "watchful intercession",
    frozenset({"builder", "builder"}):                 "doubled building",
    frozenset({"builder", "faithful_exile"}):          "the exile rebuilds",
    frozenset({"builder", "repairer"}):                "build and repair as one work",
    frozenset({"builder", "watchman"}):                "builds with sword and trowel",
    frozenset({"watchman", "watchman"}):               "doubled watch",
    frozenset({"watchman", "lone_voice"}):             "the watchman who is the only voice",
    frozenset({"watchman", "faithful_exile"}):         "watching faithful in exile",
    frozenset({"watchman", "yielder"}):                "watching yielded waiting",
    frozenset({"mother_in_promise", "mother_in_promise"}): "doubled mothering of promise",
    frozenset({"mother_in_promise", "intercessor"}):   "mother who intercedes",
    frozenset({"mother_in_promise", "yielder"}):       "yielding into promise",
    frozenset({"loyal_friend", "loyal_friend"}):       "doubled fidelity",
    frozenset({"loyal_friend", "vindicated"}):         "fidelity vindicated late",
    frozenset({"loyal_friend", "shepherd_leader"}):    "loyal companion of the shepherd-king",
    frozenset({"loyal_friend", "encourager"}):         "fidelity that encourages",
    frozenset({"vindicated", "vindicated"}):           "doubled vindication",
    frozenset({"vindicated", "wrestler"}):             "the long wrestle ending in vindication",
    frozenset({"vindicated", "faithful_exile"}):       "the exile vindicated",
    frozenset({"proud_humbled", "proud_humbled"}):     "the same lesson twice",
    frozenset({"proud_humbled", "converted"}):         "humbled to conversion",
    frozenset({"proud_humbled", "disqualified"}):      "humbled into disqualification",
    frozenset({"false_prophet", "false_prophet"}):     "doubled deceit",
    frozenset({"false_prophet", "betrayer"}):          "false prophet who betrays",
    frozenset({"false_prophet", "disqualified"}):      "false prophet disqualified",
    frozenset({"lone_voice", "lone_voice"}):           "doubled solitary witness",
    frozenset({"lone_voice", "wrestler"}):             "the wrestle of the lone witness",
    frozenset({"lone_voice", "watchman"}):             "lone watchful voice",
    frozenset({"lone_voice", "called_reluctant"}):     "reluctant lone witness",
    frozenset({"lukewarm", "lukewarm"}):               "doubled drift",
    frozenset({"lukewarm", "fleer"}):                  "drift that becomes flight",
    frozenset({"lukewarm", "disqualified"}):           "drift hardened into disqualification",
    frozenset({"repairer", "repairer"}):               "doubled repair",
    frozenset({"repairer", "watchman"}):               "watchman who repairs",
    frozenset({"repairer", "builder"}):                "repair as building",
    frozenset({"last_mercy", "last_mercy"}):           "doubled last-hour mercy",
    frozenset({"last_mercy", "converted"}):            "converted at the last hour",
    frozenset({"encourager", "encourager"}):           "doubled encouragement",
    frozenset({"encourager", "yielder"}):              "yielding encourager",
    frozenset({"encourager", "loyal_friend"}):         "loyal encourager",
    frozenset({"resurrected", "type_of_christ"}):      "resurrection as a type",
    frozenset({"resurrected", "resurrected"}):         "doubled resurrection sign",
}


def _signature_for(categories: List[str]) -> Optional[str]:
    """Look up a structural label for the top categories.

    Uses top 2 (most common case). If they share a category, returns
    the same-category label. Otherwise looks up the pair. Returns None
    if no entry exists — the engine does not invent labels.
    """
    cats = [c for c in categories if c]
    if not cats:
        return None
    if len(cats) == 1:
        return _PAIR_SIGNATURES.get(frozenset({cats[0], cats[0]}))
    pair = frozenset({cats[0], cats[1]})
    return _PAIR_SIGNATURES.get(pair)


def _tokens(text: str) -> set:
    """Lowercase, alphanum-strip, drop stop words, return token set."""
    if not text:
        return set()
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return {t for t in s.split() if t and t not in _STOP and len(t) > 2}


def _max_mtime() -> float:
    """Return the latest mtime across all source files. If any source
    changes on disk, we reload everything."""
    latest = 0.0
    for _, path in _SOURCE_FILES:
        try:
            if path.exists():
                latest = max(latest, path.stat().st_mtime)
        except OSError:
            continue
    return latest


def _load_entries() -> List[Dict[str, Any]]:
    """Load archetype entries from every source file, with mtime-based
    cache. Sources are concatenated in authority order (Bible first)."""
    mtime = _max_mtime()
    if _CACHE["entries"] and mtime <= _CACHE["mtime"]:
        return _CACHE["entries"]
    entries: List[Dict[str, Any]] = []
    seen_ids: set = set()
    for source_label, path in _SOURCE_FILES:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Source-file label wins over any embedded "source" field
                    # so we know exactly which substrate it came from.
                    rec.setdefault("source", source_label)
                    # First-wins on id collisions — Bible authority preserved
                    rid = rec.get("id")
                    if not rid or rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    entries.append(rec)
        except OSError:
            continue
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
            "combination": None,
            "note": "No archetype markers matched. Engine has no shape to surface; describe the situation in more concrete terms.",
        }

    # Normalize weights so the combination sums to 1.0 — a person is
    # rarely a singleton; the blend IS the reading.
    total_score = sum(s for s, _, _ in top) or 1.0
    max_score = top[0][0]

    candidates = []
    for score, entry, hits in top:
        weight = round(score / total_score, 3)        # share of the blend
        confidence = round(score / max(0.001, max_score), 3)  # relative to leader
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
            "weight": weight,             # share of the combination
            "confidence": confidence,     # strength vs the leader
            "rhymes_with": entry.get("rhymes_with", []),
            "contrast_to": entry.get("contrast_to", []),
        })

    # Combination signature — structural, not generated.
    top_cats = [c["category"] for c in candidates[:2] if c.get("category")]
    sig_label = _signature_for(top_cats)
    if len(candidates) == 1:
        sig_summary = candidates[0]["name"]
    else:
        names = [c["name"] for c in candidates]
        weights = [c["weight"] for c in candidates]
        # "Jonah (0.55) + Saul (0.28) + Esther (0.17)"
        sig_summary = " + ".join(f"{n} ({w})" for n, w in zip(names, weights))

    combination = {
        "summary": sig_summary,
        "categories": top_cats,
        "signature": sig_label,  # may be None if pair not in lookup
        "dominant": candidates[0]["name"] if candidates else None,
        "is_blend": len([c for c in candidates if c["weight"] >= 0.20]) > 1,
    }

    return {
        "situation": text,
        "candidates": candidates,
        "combination": combination,
        "note": "Engine surfaces the combination. A person is rarely one type.",
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
    combo = rec.get("combination", {}) or {}
    # The engine never says CONCORDANT for an archetype — only
    # PROVISIONAL ("this combination is present, name it yourself") or
    # QUARANTINE if nothing matches.
    if combo.get("signature"):
        reason = f"combination: {combo['signature']} — {combo.get('summary','')}"
    else:
        reason = f"combination: {combo.get('summary', cands[0]['name'])}"
    return {
        "verdict": "PROVISIONAL",
        "reason": reason,
        "data": rec,
    }
