"""The Apothecary — compound a remedy from the substrate.

For a stated condition (e.g. "I can't forgive my brother", "marriage feels flat",
"exhausted and bitter"), retrieve one packet of each ingredient kind from across
the substrate, ranked by axis-overlap and keyword match. Returns a compounded
prescription card.

The engine still eliminates; it doesn't generate. Each ingredient is an existing
packet selected by deterministic retrieval. The "compounding" is rhetorical
form — the substance is the substrate.

Ingredients (in order of presentation):
  1. Scripture anchor   — proverb / psalm / sermon-on-mount / ecclesiastes / james
  2. Protocol           — Scripture-defined sequence
  3. Mind practice      — cognitive anchor
  4. Parable            — small story
  5. Body insight       — Nested Control layer (when axes align)
  6. Philosopher's note — Aurelius / La Rochefoucauld / Augustine
  7. Almanac confirmation — verified observation
"""
from __future__ import annotations
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from api import substrate as _substrate
from api import walk as _walk_mod
from api import scripture_lookup as _scripture_lookup
from api import mt_adapter as _mt_adapter

_REPO = Path(__file__).parent.parent

# Ingredient kind groupings — order matters; we present in this sequence.
# Proverb is its own slot (always present); other Scripture kinds pool into "scripture".
_SCRIPTURE_KINDS = ["psalm", "sermon_on_mount", "ecclesiastes", "james"]
_PHILOSOPHER_KINDS = ["aurelius", "larochefoucauld", "augustine_confessions",
                      "imitation_christ", "boethius_consolation", "pirkei_avot",
                      "pilgrim"]
_FATHERS_KINDS = ["didache", "clement1", "polycarp", "barnabas",
                  "martyrdom_polycarp", "ignatius_eph", "ignatius_mag",
                  "ignatius_tra", "ignatius_rom", "ignatius_phild",
                  "ignatius_smy", "ignatius_polyc"]

# Curated condition presets — common conditions a visitor might name.
# First-time visitors don't know what to type; these are one-click chips.
# Grouped by life-domain. Add new conditions to the relevant cluster
# (keeps the picker organized and avoids duplicates).
CONDITION_PRESETS = [
    # Inner — emotions
    "anxiety", "anger", "fear", "loneliness", "grief", "shame", "guilt",
    "envy", "pride", "lust", "addiction", "doubt", "discouragement",
    "burnout", "exhaustion", "bitterness", "unforgiveness", "regret",
    "depression", "despair", "numbness", "rage", "self-hatred",
    "impatience", "panic", "obsessive thoughts",

    # Relationships
    "marriage strain", "parenting struggle", "rebellious child",
    "aging parent", "broken friendship", "betrayal", "estrangement",
    "in-law conflict", "step-parent tension", "isolation in a crowd",
    "saying no to family", "loving difficult people",

    # Work & money
    "work pressure", "unemployment", "financial debt", "lawsuit",
    "career change", "fired or laid off", "starting a business",
    "money fear", "tithing reluctance", "envy of coworkers",
    "ethics under pressure",

    # Body & health
    "chronic illness", "pain", "sleep problems", "weight",
    "infertility", "miscarriage", "dementia diagnosis",
    "caregiver fatigue", "addiction recovery", "eating disorder",

    # Life transitions
    "moving home", "loss of a loved one", "empty nest",
    "retirement", "aging body", "midlife reassessment",
    "child leaving for college", "first child",

    # Spiritual / vocational
    "decision under uncertainty", "calling unclear",
    "spiritual dryness", "loss of meaning", "comparison and envy",
    "doubting Scripture", "prayer feels empty", "church hurt",
    "leaving a church", "discerning a teacher",

    # Outward-facing
    "speaking in public", "being mistreated", "facing injustice",
    "forgiving abuse", "telling the truth costs me",
    "needing to confess", "needing to apologize",

    # Practical / daily
    "decision fatigue", "procrastination", "social media addiction",
    "phone overuse", "news anxiety", "political bitterness",
]

# Substrate file paths
_FILES = {
    # Scripture
    "proverb":         _REPO / "data" / "proverbs" / "verses.jsonl",
    "psalm":           _REPO / "data" / "psalms" / "chapters.jsonl",
    "sermon_on_mount": _REPO / "data" / "sermon_on_mount" / "units.jsonl",
    "ecclesiastes":    _REPO / "data" / "ecclesiastes" / "verses.jsonl",
    "james":           _REPO / "data" / "james" / "verses.jsonl",
    # Sequences + practices
    "protocol":        _REPO / "data" / "protocols" / "scripture_protocols.jsonl",
    "mind":            _REPO / "data" / "mind" / "practices.jsonl",
    "parable":         _REPO / "data" / "parables" / "seeds.jsonl",
    # Allegory + fable — short stories whose form pairs with the Parable slot
    "pilgrim":         _REPO / "data" / "pilgrim" / "sections.jsonl",
    "aesop":           _REPO / "data" / "aesop" / "fables.jsonl",
    # Body
    "body_layer":      _REPO / "data" / "body" / "layers.jsonl",
    # Philosophers
    "aurelius":             _REPO / "data" / "aurelius" / "sayings.jsonl",
    "larochefoucauld":      _REPO / "data" / "larochefoucauld" / "maxims.jsonl",
    "augustine_confessions":_REPO / "data" / "augustine_confessions" / "sections.jsonl",
    "imitation_christ":     _REPO / "data" / "imitation_christ" / "chapters.jsonl",
    "boethius_consolation": _REPO / "data" / "boethius_consolation" / "sections.jsonl",
    "pirkei_avot":          _REPO / "data" / "pirkei_avot" / "sayings.jsonl",
    # Early Fathers
    "didache":             _REPO / "data" / "didache" / "chapters.jsonl",
    "clement1":            _REPO / "data" / "clement1" / "chapters.jsonl",
    "polycarp":            _REPO / "data" / "polycarp" / "chapters.jsonl",
    "barnabas":            _REPO / "data" / "barnabas" / "chapters.jsonl",
    "martyrdom_polycarp":  _REPO / "data" / "martyrdom_polycarp" / "chapters.jsonl",
    # Almanac
    "almanac":             _REPO / "data" / "almanac" / "entries.jsonl",
    # Floor (Concordance theology)
    "floor":               _REPO / "data" / "floor" / "sections.jsonl",
    # Practice (NEW): Training sequences + FieldKit cards
    "training":            _REPO / "data" / "training" / "sequences.jsonl",
    "fieldkit":            _REPO / "data" / "fieldkit" / "v1_cards.jsonl",
}

_CACHE: Dict[str, Any] = {"mtime": 0.0, "items": {}}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Thin delegate to the shared substrate reader (kept for call-site stability)."""
    return _substrate.read_jsonl(path)


def _latest_mtime() -> float:
    latest = 0.0
    for p in _FILES.values():
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _load_all() -> Dict[str, List[Dict[str, Any]]]:
    mtime = _latest_mtime()
    if _CACHE["items"] and mtime <= _CACHE["mtime"]:
        return _CACHE["items"]
    items: Dict[str, List[Dict[str, Any]]] = {}
    for kind, path in _FILES.items():
        items[kind] = _read_jsonl(path)
    _CACHE["items"] = items
    _CACHE["mtime"] = mtime
    return items


# ── Retrieval ────────────────────────────────────────────────────────────

def _jaccard(a: Set[str], b: Set[str]) -> float:
    """Delegate to the one canonical jaccard (api/substrate.jaccard)."""
    return _substrate.jaccard(a, b)


def _text_of(packet: Dict[str, Any]) -> str:
    """Get the main text-bearing field for a packet, varies by kind."""
    for field in ("text", "summary", "parable", "verification", "wisdom"):
        v = packet.get(field)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def _score_packet(packet: Dict[str, Any], cond_axes: Set[str], cond_lower: str) -> float:
    """Score a packet against a stated condition by axis overlap + keyword."""
    p_axes = set(a.lower() for a in (packet.get("axes") or []))
    ax_score = _jaccard(cond_axes, p_axes)

    body = _text_of(packet).lower()
    title = (packet.get("title") or packet.get("reference") or "").lower()
    kw_score = 0.0
    # Tokenize condition
    tokens = [t for t in re.findall(r"[a-z]+", cond_lower) if len(t) >= 4]
    hits = 0
    for tok in tokens:
        if tok in title:
            hits += 2
        elif tok in body:
            hits += 1
    if hits:
        kw_score = min(0.5, hits * 0.05)

    # Theme + trigger keyword bonus for kinds that carry them
    themes = packet.get("themes") or []
    if themes and cond_lower:
        theme_hits = sum(1 for t in themes if any(tok in t.lower() for tok in tokens))
        if theme_hits:
            kw_score += min(0.20, theme_hits * 0.05)

    # triggers can be a list (protocols) or a dict with 'keywords' (parables, almanac)
    raw_triggers = packet.get("triggers")
    triggers: List[str] = []
    if isinstance(raw_triggers, list):
        triggers = [t for t in raw_triggers if isinstance(t, str)]
    elif isinstance(raw_triggers, dict):
        triggers = [t for t in (raw_triggers.get("keywords") or []) if isinstance(t, str)]
    if triggers and cond_lower:
        trig_hits = sum(1 for t in triggers if t.lower() in cond_lower)
        if trig_hits:
            kw_score += min(0.25, trig_hits * 0.08)

    return ax_score + kw_score


def _has_topical_hit(packet: Dict[str, Any], cond_lower: str) -> bool:
    """True if the condition's content words actually appear in the packet's
    title / body / themes / triggers — genuine topical evidence, not mere axis
    overlap. (Axis overlap alone surfaced a forgiveness protocol for 'loneliness'.)"""
    tokens = [t for t in re.findall(r"[a-z]+", cond_lower) if len(t) >= 4]
    if not tokens:
        return False
    hay = (_text_of(packet) + " " + str(packet.get("title") or packet.get("reference") or "")).lower()
    hay += " " + " ".join(str(t).lower() for t in (packet.get("themes") or []))
    raw_trig = packet.get("triggers")
    if isinstance(raw_trig, list):
        hay += " " + " ".join(str(t).lower() for t in raw_trig)
    elif isinstance(raw_trig, dict):
        hay += " " + " ".join(str(t).lower() for t in (raw_trig.get("keywords") or []))
    return any(t in hay for t in tokens)


def _best(packets: List[Dict[str, Any]], cond_axes: Set[str], cond_lower: str,
          min_score: float = 0.05, require_keyword: bool = False) -> Optional[Dict[str, Any]]:
    if not packets:
        return None
    if require_keyword:
        # Topical ingredient (protocol, fieldkit): require real keyword evidence,
        # not just axis overlap. If nothing topically matches, return None (omit it)
        # — NEVER hash-pick an arbitrary protocol, which mislabels the condition
        # (e.g. "loneliness" -> a forgiveness protocol). An honest gap beats a
        # confident mismatch. The other ingredients still fill the compound.
        packets = [p for p in packets if _has_topical_hit(p, cond_lower)]
        if not packets:
            return None
    best = None
    best_score = -1.0
    for p in packets:
        s = _score_packet(p, cond_axes, cond_lower)
        if s > best_score:
            best = p
            best_score = s
    if best is None or best_score < min_score:
        if require_keyword:
            return None  # topical ingredients are omitted, never hash-picked
        # Fall back to deterministic hash pick (broadly-applicable wisdom only)
        import hashlib
        h = hashlib.sha256(cond_lower.encode("utf-8")).digest()
        idx = int.from_bytes(h[:8], "big") % max(1, len(packets))
        sorted_pkts = sorted(packets, key=lambda p: p.get("id", ""))
        return sorted_pkts[idx]
    return best


_SCRIPTURE_PACKET_KINDS = {"proverb", "psalm", "sermon_on_mount", "ecclesiastes", "james"}


def _maybe_swap_scripture_text(packet: Dict[str, Any], kind: str,
                               lang: str) -> tuple[str, Optional[str]]:
    """For Scripture-kind packets and a non-English `lang`, try to swap the
    text to the parallel PD translation. Returns (text, swapped_label).
    `swapped_label` is the translation name (e.g. "Reina-Valera 1909") when
    the swap succeeded, else None and the original English text is kept.
    """
    en_text = _text_of(packet)
    if not lang or lang == "en":
        return en_text, None
    if kind not in _SCRIPTURE_PACKET_KINDS:
        return en_text, None

    book = packet.get("book") or "Matthew" if kind == "sermon_on_mount" else packet.get("book")
    swapped: Optional[str] = None

    try:
        if kind == "psalm":
            ch = packet.get("chapter")
            if isinstance(ch, int):
                swapped = _scripture_lookup.lookup_chapter(lang, "Psalms", ch)
        elif kind == "sermon_on_mount":
            ch = packet.get("chapter")
            vs = packet.get("verse_start")
            ve = packet.get("verse_end")
            if isinstance(ch, int) and isinstance(vs, int) and isinstance(ve, int):
                swapped = _scripture_lookup.lookup_range(lang, "Matthew", ch, vs, ve)
        else:
            # proverb, ecclesiastes, james — single verse via book/ch/v
            swapped = _scripture_lookup.lookup_packet(lang, packet)
    except Exception:
        swapped = None

    if swapped:
        return swapped, _scripture_lookup.translation_label(lang)
    return en_text, None


def _packet_view(packet: Optional[Dict[str, Any]], kind: str,
                 lang: str = "en") -> Optional[Dict[str, Any]]:
    if not packet:
        return None
    text, swapped_label = _maybe_swap_scripture_text(packet, kind, lang)
    view: Dict[str, Any] = {
        "kind": kind,
        "id": packet.get("id"),
        "reference": packet.get("reference") or packet.get("title") or packet.get("id"),
        "title": packet.get("title"),
        "text": text,
        "axes": packet.get("axes") or [],
        "source": swapped_label or packet.get("source"),
        "license": packet.get("license"),
        # Carry extras when present (truthy values only — keeps JSON tidy)
        "question": packet.get("question"),
        "practice": packet.get("practice"),
        "scripture": packet.get("scripture"),
        "scripture_anchor": packet.get("scripture_anchor"),
        "steps": packet.get("steps"),
        "function": packet.get("function"),
        "falsifiable_check": packet.get("falsifiable_check"),
    }
    # Training-specific surface
    if kind == "training":
        view["category"]       = packet.get("category")
        view["duration"]       = packet.get("duration")
        view["common_failure"] = packet.get("common_failure")
        view["permalink"]      = f"/training.html?id={packet.get('id','')}"
    # FieldKit-specific surface
    if kind == "fieldkit":
        view["rarity"]         = packet.get("rarity")
        view["practice_7day"]  = packet.get("practice_7day")
        view["common_drift"]   = packet.get("common_drift")
        view["prompt"]         = packet.get("prompt")
        view["permalink"]      = f"/fieldkit.html#{packet.get('id','')}"
    return view


def compound(condition: str, lang: str = "en") -> Dict[str, Any]:
    """Compound a remedy for the stated condition.

    Returns a dict with one packet per ingredient kind. Missing ingredients
    (e.g., no relevant body layer) come back as None.

    `lang` is the reader's language code (e.g. "es"). Scripture-kind slots
    swap to a parallel PD translation when one is available. Engine-authored
    slots (parable, protocol, training, mind, fieldkit, almanac) stay English
    today — translation of those is a separate (MT) layer to be added later.
    """
    condition = (condition or "").strip()
    lang = (lang or "en").strip().lower() or "en"
    if not condition:
        return {"condition": "", "compound": None, "error": "condition is required"}

    items = _load_all()
    cond_lower = condition.lower()

    # Derive axes from the condition using Coach's same machinery.
    try:
        cond_axes_list = _walk_mod.derive_axes(condition)
    except Exception:
        cond_axes_list = []
    cond_axes = set(cond_axes_list)

    # Proverb — its own slot (NEW). Proverbs are universal; always include the best
    # match from the 915-verse substrate. Promotes Proverbs out of the Scripture pool.
    proverb = _best(items.get("proverb", []), cond_axes, cond_lower, min_score=0.02)

    # Scripture: pick best across psalm/SoM/Ecclesiastes/James (Proverb has its own slot now).
    # Weighted toward red-letter (sermon_on_mount) and explicit topical books (James).
    scripture_candidates: List[tuple[float, Dict[str, Any], str]] = []
    for k in _SCRIPTURE_KINDS:
        for p in items.get(k, []):
            s = _score_packet(p, cond_axes, cond_lower)
            if k == "sermon_on_mount":
                s += 0.05
            elif k == "james":
                s += 0.03
            if s > 0:
                scripture_candidates.append((s, p, k))
    scripture = None
    scripture_kind = None
    if scripture_candidates:
        scripture_candidates.sort(key=lambda x: x[0], reverse=True)
        s, p, scripture_kind = scripture_candidates[0]
        scripture = p

    # Protocol — exactly one, and only if it TOPICALLY matches the condition
    # (require_keyword): a protocol claims specific relevance, so axis overlap alone
    # isn't enough. No topical protocol -> omit it rather than mislabel.
    protocol = _best(items.get("protocol", []), cond_axes, cond_lower, require_keyword=True)

    # Training — NEW practical slot. Multi-week sequence the visitor can walk.
    # Lower threshold (axes overlap is the main signal; keyword may not hit
    # because Training is body-of-knowledge, not topical-to-emotion).
    training = _best(items.get("training", []), cond_axes, cond_lower, min_score=0.04)

    # Mind — exactly one
    mind = _best(items.get("mind", []), cond_axes, cond_lower)

    # Parable — exactly one, pooled across engine-authored parables + Aesop's
    # fables (Townsend 1887, PD). Engine parables are short Scripture-anchored
    # stories; Aesop's are short moral stories. Both fit the form. Ranked
    # together by score so the best match wins regardless of source.
    parable_candidates: List[tuple[float, Dict[str, Any], str]] = []
    for k in ("parable", "aesop"):
        for p in items.get(k, []):
            s = _score_packet(p, cond_axes, cond_lower)
            # Slight lean toward engine parables: they're more Scripture-tight
            if k == "parable":
                s += 0.03
            if s > 0:
                parable_candidates.append((s, p, k))
    parable = None
    parable_kind = "parable"
    if parable_candidates:
        parable_candidates.sort(key=lambda x: x[0], reverse=True)
        s, parable, parable_kind = parable_candidates[0]
    else:
        # Fallback to the deterministic hash pick on engine parables
        parable = _best(items.get("parable", []), cond_axes, cond_lower)

    # FieldKit — NEW pattern-name slot. The card that names the situation. Topical
    # (require_keyword): naming the wrong situation is worse than naming none.
    fieldkit = _best(items.get("fieldkit", []), cond_axes, cond_lower, min_score=0.06, require_keyword=True)

    # Body layer — only if axes intersect
    body = None
    body_candidates = items.get("body_layer", [])
    if body_candidates and cond_axes:
        scored = [(_score_packet(b, cond_axes, cond_lower), b) for b in body_candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] >= 0.10:
            body = scored[0][1]

    # Philosopher's note — best across philosopher kinds
    phil_candidates: List[tuple[float, Dict[str, Any], str]] = []
    for k in _PHILOSOPHER_KINDS:
        for p in items.get(k, []):
            s = _score_packet(p, cond_axes, cond_lower)
            if s > 0:
                phil_candidates.append((s, p, k))
    philosopher = None
    philosopher_kind = None
    if phil_candidates:
        phil_candidates.sort(key=lambda x: x[0], reverse=True)
        s, p, philosopher_kind = phil_candidates[0]
        philosopher = p

    # Early fathers — opportunistic (only if score is meaningful)
    father = None
    father_kind = None
    fath_candidates: List[tuple[float, Dict[str, Any], str]] = []
    for k in _FATHERS_KINDS:
        for p in items.get(k, []):
            s = _score_packet(p, cond_axes, cond_lower)
            if s >= 0.15:
                fath_candidates.append((s, p, k))
    if fath_candidates:
        fath_candidates.sort(key=lambda x: x[0], reverse=True)
        s, p, father_kind = fath_candidates[0]
        father = p

    # Almanac confirmation — best almanac
    almanac = _best(items.get("almanac", []), cond_axes, cond_lower, min_score=0.10)

    compound_views = {
        "scripture":     _packet_view(scripture, scripture_kind or "scripture", lang),
        "proverb":       _packet_view(proverb, "proverb", lang),
        "protocol":      _packet_view(protocol, "protocol", lang),
        "training":      _packet_view(training, "training", lang),
        "mind":          _packet_view(mind, "mind", lang),
        "parable":       _packet_view(parable, parable_kind or "parable", lang),
        "fieldkit":      _packet_view(fieldkit, "fieldkit", lang),
        "body":          _packet_view(body, "body_layer", lang),
        "philosopher":   _packet_view(philosopher, philosopher_kind or "philosopher", lang),
        "father":        _packet_view(father, father_kind or "father", lang) if father else None,
        "almanac":       _packet_view(almanac, "almanac", lang),
    }

    # MT-pass for engine-authored prose. Scripture + Proverb already
    # swapped via parallel-translation lookup in _packet_view; skip them.
    # When MT is not configured, translate() is a no-op (returns input
    # unchanged), so this block is safe to always run.
    #
    # Time budget: each Anthropic API call takes 2-5s; nine slots × ~3
    # fields = 27 calls → 54-135s without a cap. Budget the whole MT pass
    # at 10 seconds and bail out when exceeded. The Scripture swap (from
    # local PD files) already happened in _packet_view — that's instant.
    # The MT pass is additive; English is the floor.
    mt_used = False
    if lang and lang != "en" and _mt_adapter.is_available():
        mt_deadline = time.time() + 10  # 10-second budget for all MT
        for slot in ("protocol", "training", "mind", "parable",
                     "fieldkit", "body", "philosopher", "father", "almanac"):
            if time.time() > mt_deadline:
                break  # Time budget exceeded — remaining slots stay English
            view = compound_views.get(slot)
            if view:
                _mt_adapter.translate_packet_view(view, lang, deadline=mt_deadline)
                if view.get("_mt_lang"):
                    mt_used = True

    # ── Stand the whole compound on the WHOLE floor ──────────────────────
    # The apothecary used to return Scripture + Almanac — two shards. Now its
    # output is put on the full floor in one call: Canon anchor, the four
    # gates, the medicine verifier pointer, Calibre, and (load-bearing here)
    # the Nested Control Systems layer — which body control-system is most
    # likely failing for this condition, with the referral gates attached so
    # the remedy never stands between the person and a physician.
    floor_standing = None
    try:
        from api import floor as _floor
        floor_standing = _floor.stand_on_floor(condition, domain="health", kind="condition")
    except Exception:
        floor_standing = None

    return {
        "condition":   condition,
        "lang":        lang,
        "shared_axes": sorted(cond_axes),
        "mt_active":   mt_used,
        "compound":    compound_views,
        "floor":       floor_standing,
    }
