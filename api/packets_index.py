"""Unified packet index — gather every packet across every store.

The engine keeps packets in many places (almanac, sealed polymathic
axis_index, misalignment log, build queue, FieldKit, protocols,
archetypes, receipts). This module makes them all retrievable by
**domain** and by **axis** through one shape:

  {
    kind:        "almanac" | "sealed_poly" | "misalignment" | "build_queue"
                 | "fieldkit_card" | "protocol" | "archetype" | "receipt",
    id:          stable identifier within that kind,
    title:       short readable label,
    verdict:     CONCORDANT / CONFIRMED / MISMATCH / DISCORDANT / OBSOLETE / PENDING / None,
    domains:     list of verifier-domain names this packet touches,
    axes:        list of 7-axis dimensions this packet touches,
    summary:     1-line summary (wisdom, situation, or claim excerpt),
    permalink:   the URL where a human can read the full packet,
    api_path:    the JSON endpoint that returns it,
    weight:      relative importance score for ranking (higher = more load-bearing)
  }

This is the **intersection layer**. The wisdom is at the intersections;
this module makes the intersections walkable.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_REPO = Path(__file__).parent.parent

_ALMANAC_FILE   = _REPO / "data" / "almanac" / "entries.jsonl"
_AXIS_INDEX     = _REPO / "data" / "axis_index.json"
_MISALIGN_FILE  = _REPO / "data" / "misalignments" / "log.jsonl"
_BUILD_QUEUE    = _REPO / "data" / "build_queue" / "queue.jsonl"
_FIELDKIT_FILE  = _REPO / "data" / "fieldkit" / "v1_cards.jsonl"
_PROTOCOLS_FILE = _REPO / "data" / "protocols" / "scripture_protocols.jsonl"
_RECEIPTS_FILE  = _REPO / "data" / "receipts" / "promotions.jsonl"
_FLOOR_FILE     = _REPO / "data" / "floor" / "sections.jsonl"
_BODY_FILE      = _REPO / "data" / "body" / "layers.jsonl"
_MIND_FILE      = _REPO / "data" / "mind" / "practices.jsonl"
_DEVOTIONAL_FILE= _REPO / "data" / "devotionals" / "reflections.jsonl"
_SERMON_FILE    = _REPO / "data" / "sermons" / "sermons.jsonl"
_PROVERBS_FILE  = _REPO / "data" / "proverbs" / "verses.jsonl"
_ECCL_FILE      = _REPO / "data" / "ecclesiastes" / "verses.jsonl"
_JAMES_FILE     = _REPO / "data" / "james" / "verses.jsonl"
_PSALMS_FILE    = _REPO / "data" / "psalms" / "chapters.jsonl"
_SOM_FILE       = _REPO / "data" / "sermon_on_mount" / "units.jsonl"
_AURELIUS_FILE  = _REPO / "data" / "aurelius" / "sayings.jsonl"
_LAROCH_FILE    = _REPO / "data" / "larochefoucauld" / "maxims.jsonl"
_DIDACHE_FILE   = _REPO / "data" / "didache" / "chapters.jsonl"
_CLEMENT_FILE   = _REPO / "data" / "clement1" / "chapters.jsonl"
_POLYCARP_FILE  = _REPO / "data" / "polycarp" / "chapters.jsonl"
_AVOT_FILE      = _REPO / "data" / "pirkei_avot" / "sayings.jsonl"
# Tier 1 ANF01 expansion
_IGN_EPH_FILE   = _REPO / "data" / "ignatius_eph"    / "chapters.jsonl"
_IGN_MAG_FILE   = _REPO / "data" / "ignatius_mag"    / "chapters.jsonl"
_IGN_TRA_FILE   = _REPO / "data" / "ignatius_tra"    / "chapters.jsonl"
_IGN_ROM_FILE   = _REPO / "data" / "ignatius_rom"    / "chapters.jsonl"
_IGN_PHILD_FILE = _REPO / "data" / "ignatius_phild"  / "chapters.jsonl"
_IGN_SMY_FILE   = _REPO / "data" / "ignatius_smy"    / "chapters.jsonl"
_IGN_POLYC_FILE = _REPO / "data" / "ignatius_polyc"  / "chapters.jsonl"
_BARNABAS_FILE  = _REPO / "data" / "barnabas"        / "chapters.jsonl"
_MART_POL_FILE  = _REPO / "data" / "martyrdom_polycarp" / "chapters.jsonl"
# Tier 2 classics
_AUG_CONF_FILE  = _REPO / "data" / "augustine_confessions" / "sections.jsonl"
_IMIT_FILE      = _REPO / "data" / "imitation_christ" / "chapters.jsonl"
_BOE_FILE       = _REPO / "data" / "boethius_consolation" / "sections.jsonl"
# Training sequences — gardening, fitness, cooking, home, outdoor, crafts, husbandry
_TRAINING_FILE  = _REPO / "data" / "training" / "sequences.jsonl"
# Easton's Bible Dictionary (1897, PD) and the geographic subset
_EASTON_FILE    = _REPO / "data" / "easton" / "entries.jsonl"
_PLACES_FILE    = _REPO / "data" / "places" / "entries.jsonl"
# Pilgrim's Progress (John Bunyan 1678, PD) — 406 numbered sections
_PILGRIM_FILE   = _REPO / "data" / "pilgrim" / "sections.jsonl"
# Aesop's Fables (Townsend 1887, PD) — 308 fables
_AESOP_FILE     = _REPO / "data" / "aesop" / "fables.jsonl"
# Phonics curriculum (sequenced literacy units)
_PHONICS_FILE   = _REPO / "data" / "phonics" / "units.jsonl"
# WorkReady curriculum (sequenced employability units)
_WORKREADY_FILE = _REPO / "data" / "workready" / "units.jsonl"
# Math curriculum (counting → addition → subtraction → …)
_MATH_FILE      = _REPO / "data" / "math" / "units.jsonl"
# Reading comprehension (main idea → sequencing → cause-effect → …)
_READING_FILE   = _REPO / "data" / "reading" / "units.jsonl"
# Writing mechanics + structure (sentence → capitalization → paragraph → …)
_WRITING_FILE   = _REPO / "data" / "writing" / "units.jsonl"
# Science (seasons → plants → water cycle → senses → states of matter → …)
_SCIENCE_FILE   = _REPO / "data" / "science" / "units.jsonl"
# Bible curriculum (memory work — Psalm 23, Lord's Prayer, Beatitudes, …)
_BIBLE_CURR_FILE = _REPO / "data" / "bible_curriculum" / "units.jsonl"
# Social studies (community helpers → map skills → calendar → citizenship …)
_SOCIAL_FILE    = _REPO / "data" / "social_studies" / "units.jsonl"
# Herb monographs (evidence-honest botanical remedies for the Apothecary)
_HERBS_FILE     = _REPO / "data" / "herbs" / "monographs.jsonl"
# Wedges — intervention catalog (ported from Coach OS v1.0)
_WEDGES_FILE    = _REPO / "data" / "wedges" / "catalog.jsonl"
# Steward audit (every admit/deny + token consume from steward.py)
_STEWARD_AUDIT  = _REPO / "data" / "steward" / "audit.jsonl"
# Seeds — auto-crafted from search misses (search once, reference forever)
_SEEDS_FILE     = _REPO / "data" / "seeds" / "seeds.jsonl"

_CACHE: Dict[str, Any] = {"mtime": 0.0, "packets": []}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _all_mtimes() -> float:
    latest = 0.0
    for p in (_ALMANAC_FILE, _AXIS_INDEX, _MISALIGN_FILE, _BUILD_QUEUE,
              _FIELDKIT_FILE, _PROTOCOLS_FILE, _RECEIPTS_FILE,
              _FLOOR_FILE, _BODY_FILE, _MIND_FILE,
              _DEVOTIONAL_FILE, _SERMON_FILE, _PROVERBS_FILE,
              _ECCL_FILE, _JAMES_FILE, _PSALMS_FILE, _SOM_FILE,
              _AURELIUS_FILE, _LAROCH_FILE, _DIDACHE_FILE,
              _CLEMENT_FILE, _POLYCARP_FILE, _AVOT_FILE,
              _IGN_EPH_FILE, _IGN_MAG_FILE, _IGN_TRA_FILE, _IGN_ROM_FILE,
              _IGN_PHILD_FILE, _IGN_SMY_FILE, _IGN_POLYC_FILE,
              _BARNABAS_FILE, _MART_POL_FILE,
              _AUG_CONF_FILE, _IMIT_FILE, _BOE_FILE,
              _PHONICS_FILE, _WORKREADY_FILE, _MATH_FILE,
              _READING_FILE, _WRITING_FILE, _SCIENCE_FILE,
              _BIBLE_CURR_FILE, _SOCIAL_FILE, _HERBS_FILE,
              _WEDGES_FILE, _STEWARD_AUDIT, _SEEDS_FILE):
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _archetypes_axes_map() -> Dict[str, List[str]]:
    """Lazy import the archetype→axes map so this module doesn't pull
    archetypes.py at import time (it's heavy)."""
    try:
        from api.archetypes import _CATEGORY_AXES
        return _CATEGORY_AXES
    except Exception:
        return {}


def _protocol_axes_map() -> Dict[str, List[str]]:
    """Lazy import the protocol→axes map from walk.py."""
    try:
        from api.walk import _PROTOCOL_AXIS_MAP
        return _PROTOCOL_AXIS_MAP
    except Exception:
        return {}


def _load_archetypes() -> List[Dict[str, Any]]:
    """Read all archetype JSONL files. Multiple files exist; concat."""
    out: List[Dict[str, Any]] = []
    arch_dir = _REPO / "data" / "archetypes"
    if not arch_dir.exists():
        return out
    for f in sorted(arch_dir.glob("*.jsonl")):
        out.extend(_read_jsonl(f))
    return out


def _normalize_packet_records() -> List[Dict[str, Any]]:
    """Walk every substrate and emit unified packet records."""
    packets: List[Dict[str, Any]] = []

    # ── Almanac entries ────────────────────────────────────────────────
    # No native timestamp on almanac entries today; use file mtime as
    # a coarse default so the Chronicle lens has something to sort by.
    almanac_mtime = int(_ALMANAC_FILE.stat().st_mtime) if _ALMANAC_FILE.exists() else 0
    for e in _read_jsonl(_ALMANAC_FILE):
        eid = e.get("id", "")
        title = e.get("title") or e.get("situation") or eid
        ts = e.get("discovered_at") or e.get("created_at") or almanac_mtime
        packets.append({
            "kind": "almanac",
            "id": eid,
            "title": title[:240],
            "verdict": e.get("verdict"),
            "domains": list(e.get("domains") or []),
            "axes": list(e.get("axes") or []),
            "summary": (e.get("wisdom") or e.get("verification") or e.get("situation") or "")[:280],
            "permalink": f"/almanac.html#{eid}",
            "api_path": f"/almanac/{eid}",
            "weight": 0.9 if e.get("verdict") in ("CONFIRMED", "CONCORDANT") else 0.6,
            "timestamp": ts,
        })

    # ── Sealed polymathic axis_index ───────────────────────────────────
    if _AXIS_INDEX.exists():
        try:
            idx = json.loads(_AXIS_INDEX.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            idx = {}
        # Dedupe by hash across the per-axis buckets
        seen: Set[str] = set()
        for axis, bucket in (idx or {}).items():
            if not isinstance(bucket, list):
                continue
            for r in bucket:
                if not isinstance(r, dict):
                    continue
                h = r.get("hash", "")
                if not h or h in seen:
                    continue
                seen.add(h)
                packets.append({
                    "kind": "sealed_poly",
                    "id": h,
                    "title": (r.get("summary") or h)[:140],
                    "verdict": r.get("verdict"),
                    "domains": [],  # sealed records carry dims, not domains
                    "axes": list(r.get("dims") or []),
                    "summary": (r.get("summary") or "")[:280],
                    "permalink": f"/poly.html#hash-{h}",
                    "api_path": f"/journal/by-hash/{h}",
                    "weight": 0.85,
                    "timestamp": r.get("sealed_at") or 0,
                })

    # ── Misalignment log ───────────────────────────────────────────────
    for r in _read_jsonl(_MISALIGN_FILE):
        rid = r.get("id", "")
        domains = sorted({d.get("domain", "") for d in (r.get("domain_results") or []) if d.get("domain")})
        packets.append({
            "kind": "misalignment",
            "id": rid,
            "title": (r.get("claim") or rid)[:140],
            "verdict": r.get("composite_verdict"),
            "domains": [d for d in domains if d],
            "axes": [],  # misalignments don't carry axes today
            "summary": (r.get("claim") or "")[:280],
            "permalink": "/inbox.html",   # operator console
            "api_path": "/misalignments",
            "weight": 0.4,
            "timestamp": r.get("logged_at") or 0,
        })

    # ── Build queue ────────────────────────────────────────────────────
    for r in _read_jsonl(_BUILD_QUEUE):
        rid = r.get("id", "")
        packets.append({
            "kind": "build_queue",
            "id": rid,
            "title": (r.get("claim_pattern") or rid)[:140],
            "verdict": "PENDING",
            "domains": [],
            "axes": [],
            "summary": (r.get("needed_math") or r.get("example_claim") or "")[:280],
            "permalink": "/inbox.html",
            "api_path": "/build_queue",
            "weight": 0.3,
            "timestamp": r.get("queued_at") or r.get("created_at") or 0,
        })

    # ── FieldKit cards ─────────────────────────────────────────────────
    fieldkit_mtime = int(_FIELDKIT_FILE.stat().st_mtime) if _FIELDKIT_FILE.exists() else 0
    for c in _read_jsonl(_FIELDKIT_FILE):
        cid = c.get("id", "")
        packets.append({
            "kind": "fieldkit_card",
            "id": cid,
            "title": c.get("title") or cid,
            "verdict": None,
            "domains": [],
            "axes": list(c.get("axes") or []),
            "summary": (c.get("source") or "")[:280],
            "permalink": f"/fieldkit.html#{cid}",
            "api_path": f"/fieldkit/{cid}",
            "weight": 1.0,  # FieldKit cards are protocols you walk — top weight
            "timestamp": c.get("created_at") or fieldkit_mtime,
        })

    # ── Scripture protocols ────────────────────────────────────────────
    proto_axes = _protocol_axes_map()
    protocols_mtime = int(_PROTOCOLS_FILE.stat().st_mtime) if _PROTOCOLS_FILE.exists() else 0
    for p in _read_jsonl(_PROTOCOLS_FILE):
        pid = p.get("id", "")
        packets.append({
            "kind": "protocol",
            "id": pid,
            "title": p.get("name") or pid,
            "verdict": None,
            "domains": [],
            "axes": list(proto_axes.get(pid, [])),
            "summary": (p.get("summary") or "")[:280],
            "permalink": f"/walk.html?protocol={pid}",
            "api_path": "/walk/protocols",
            "weight": 0.95,
            "timestamp": p.get("created_at") or protocols_mtime,
        })

    # ── Training sequences ─────────────────────────────────────────────
    training_mtime = int(_TRAINING_FILE.stat().st_mtime) if _TRAINING_FILE.exists() else 0
    for t in _read_jsonl(_TRAINING_FILE):
        tid = t.get("id", "")
        packets.append({
            "kind": "training",
            "id": tid,
            "title": t.get("title") or tid,
            "verdict": "CONFIRMED",
            "domains": [t.get("category", "")],
            "axes": list(t.get("axes") or []),
            "summary": (t.get("summary") or "")[:280],
            "permalink": f"/training.html?id={tid}",
            "api_path": f"/training/{tid}",
            "weight": 0.85,
            "timestamp": training_mtime,
        })

    # ── Places (geographic subset of Easton's Bible Dictionary) ────────
    places_mtime = int(_PLACES_FILE.stat().st_mtime) if _PLACES_FILE.exists() else 0
    for p in _read_jsonl(_PLACES_FILE):
        pid = p.get("id", "")
        slug = pid.replace("place_", "", 1) if pid.startswith("place_") else pid
        packets.append({
            "kind": "place",
            "id": pid,
            "title": p.get("name") or pid,
            "verdict": "CONFIRMED",
            "domains": ["geography"],
            "axes": list(p.get("axes") or []),
            "summary": (p.get("text") or "")[:280],
            "permalink": f"/places.html?id={slug}",
            "api_path": f"/places/{slug}",
            "weight": 0.75,
            "timestamp": places_mtime,
        })

    # ── Pilgrim's Progress (Bunyan 1678, PD) ────────────────────────────
    pilgrim_mtime = int(_PILGRIM_FILE.stat().st_mtime) if _PILGRIM_FILE.exists() else 0
    for p in _read_jsonl(_PILGRIM_FILE):
        pid = p.get("id", "")
        section = p.get("section", 0)
        packets.append({
            "kind": "pilgrim",
            "id": pid,
            "title": (p.get("title") or f"Pilgrim's Progress §{section}")[:120],
            "verdict": "CONFIRMED",
            "domains": ["allegory"],
            "axes": list(p.get("axes") or []),
            "summary": (p.get("text") or "")[:280],
            "permalink": f"/packets.html?id={pid}",
            "api_path": f"/pilgrim/{section}",
            "weight": 0.78,
            "timestamp": pilgrim_mtime,
        })

    # ── Aesop's Fables (Townsend 1887, PD) ──────────────────────────────
    aesop_mtime = int(_AESOP_FILE.stat().st_mtime) if _AESOP_FILE.exists() else 0
    for a in _read_jsonl(_AESOP_FILE):
        aid = a.get("id", "")
        title = a.get("title") or aid
        # Use the moral as the summary when present; falls back to first
        # sentence of the fable body.
        summary = (a.get("moral") or "").strip()
        if not summary:
            summary = (a.get("text") or "")[:280]
        packets.append({
            "kind": "aesop",
            "id": aid,
            "title": title[:120],
            "verdict": "CONFIRMED",
            "domains": ["fable"],
            "axes": list(a.get("axes") or []),
            "summary": summary[:280],
            "permalink": f"/packets.html?id={aid}",
            "api_path": f"/aesop/{aid}",
            "weight": 0.78,
            "timestamp": aesop_mtime,
        })

    # ── Phonics curriculum units ───────────────────────────────────────
    # Each unit holds: the rule, example words, a decodable sentence,
    # and a three-word check. Sequenced via `unit_seq` + `next`; the
    # progression layer (mastery, suggest-next) is a later pass.
    phonics_mtime = int(_PHONICS_FILE.stat().st_mtime) if _PHONICS_FILE.exists() else 0
    for u in _read_jsonl(_PHONICS_FILE):
        uid = u.get("id", "")
        examples = u.get("examples") or []
        # Build a rich summary: rule + example words list so token search
        # ("short a", "cat", "decodable") can find the unit.
        rule = (u.get("rule") or "").strip()
        ex_str = ", ".join(examples[:8])
        summary_parts = [s for s in [u.get("summary"), rule, ("Examples: " + ex_str) if ex_str else ""] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "phonics_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["linguistics", "phonics"]),
            "axes": list(u.get("axes") or ["information_encoding", "time_sequence"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/phonics/{uid}",
            "weight": 0.82,
            "timestamp": phonics_mtime,
        })

    # ── WorkReady curriculum units ─────────────────────────────────────
    # Each unit holds: the principle, weak→strong examples, a craft
    # prompt, and a rubric. Same sequencing shape as phonics; the
    # six WorkReady competencies fold into Concordance per the
    # workready_folds_in memory.
    workready_mtime = int(_WORKREADY_FILE.stat().st_mtime) if _WORKREADY_FILE.exists() else 0
    for u in _read_jsonl(_WORKREADY_FILE):
        uid = u.get("id", "")
        principle = (u.get("principle") or "").strip()
        competency = (u.get("competency") or "").strip()
        summary_parts = [s for s in [u.get("summary"), principle] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "workready_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["rhetoric", "labor"]),
            "axes": list(u.get("axes") or ["information_encoding", "authority_trust"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/workready/{uid}",
            "weight": 0.82,
            "timestamp": workready_mtime,
        })

    # ── Math curriculum units ────────────────────────────────────────
    # Same shape as phonics + workready. Each unit carries rule,
    # examples, manipulative, three reading-style modes (coach_models /
    # take_turns / i_solve), check with teaching note, wedge refs,
    # prerequisites + next. Sequenced track: counting → addition →
    # subtraction → addition-within-20 → …
    math_mtime = int(_MATH_FILE.stat().st_mtime) if _MATH_FILE.exists() else 0
    for u in _read_jsonl(_MATH_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        examples = u.get("examples") or []
        ex_str = ", ".join(str(e) for e in examples[:6])
        summary_parts = [s for s in [
            u.get("summary"),
            rule,
            ("Examples: " + ex_str) if ex_str else "",
        ] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "math_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["mathematics", "pedagogy"]),
            "axes": list(u.get("axes") or ["information_encoding", "reasoning"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/math/{uid}",
            "weight": 0.82,
            "timestamp": math_mtime,
        })

    # ── Reading comprehension curriculum units ───────────────────────
    # Post-decoding skills: main idea, sequencing, cause/effect,
    # inference. Same shape as phonics/math/workready.
    reading_mtime = int(_READING_FILE.stat().st_mtime) if _READING_FILE.exists() else 0
    for u in _read_jsonl(_READING_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        summary_parts = [s for s in [u.get("summary"), rule] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "reading_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["rhetoric", "linguistics", "pedagogy"]),
            "axes": list(u.get("axes") or ["information_encoding", "reasoning"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/reading/{uid}",
            "weight": 0.82,
            "timestamp": reading_mtime,
        })

    # ── Writing curriculum units ─────────────────────────────────────
    # Mechanics + structure: complete sentence, capitalization,
    # paragraph. Same shape.
    writing_mtime = int(_WRITING_FILE.stat().st_mtime) if _WRITING_FILE.exists() else 0
    for u in _read_jsonl(_WRITING_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        summary_parts = [s for s in [u.get("summary"), rule] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "writing_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["rhetoric", "linguistics", "pedagogy"]),
            "axes": list(u.get("axes") or ["information_encoding", "authority_trust"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/writing/{uid}",
            "weight": 0.82,
            "timestamp": writing_mtime,
        })

    # ── Science curriculum units ─────────────────────────────────────
    # Primary topics: seasons, plant parts, water cycle, senses,
    # states of matter. Same shape as the other curricula.
    science_mtime = int(_SCIENCE_FILE.stat().st_mtime) if _SCIENCE_FILE.exists() else 0
    for u in _read_jsonl(_SCIENCE_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        summary_parts = [s for s in [u.get("summary"), rule] if s]
        summary = " · ".join(summary_parts)[:280]
        packets.append({
            "kind": "science_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["biology", "pedagogy"]),
            "axes": list(u.get("axes") or ["physical_substance", "information_encoding"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/science/{uid}",
            "weight": 0.82,
            "timestamp": science_mtime,
        })

    # ── Bible curriculum (memory work + theological scaffolding) ──────
    bible_curr_mtime = int(_BIBLE_CURR_FILE.stat().st_mtime) if _BIBLE_CURR_FILE.exists() else 0
    for u in _read_jsonl(_BIBLE_CURR_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        summary = " · ".join([s for s in [u.get("summary"), rule] if s])[:280]
        packets.append({
            "kind": "bible_curriculum_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["scripture", "theology", "pedagogy"]),
            "axes": list(u.get("axes") or ["authority_trust", "information_encoding"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/bible_curriculum/{uid}",
            "weight": 0.90,
            "timestamp": bible_curr_mtime,
        })

    # ── Social studies (community → maps → timelines → citizenship) ───
    social_mtime = int(_SOCIAL_FILE.stat().st_mtime) if _SOCIAL_FILE.exists() else 0
    for u in _read_jsonl(_SOCIAL_FILE):
        uid = u.get("id", "")
        rule = (u.get("rule") or "").strip()
        summary = " · ".join([s for s in [u.get("summary"), rule] if s])[:280]
        packets.append({
            "kind": "social_studies_unit",
            "id": uid,
            "title": (u.get("title") or uid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(u.get("domains") or ["governance", "geography", "pedagogy"]),
            "axes": list(u.get("axes") or ["authority_trust", "information_encoding"]),
            "summary": summary,
            "permalink": f"/packets.html?id={uid}",
            "api_path": f"/social_studies/{uid}",
            "weight": 0.82,
            "timestamp": social_mtime,
        })

    # ── Herb monographs (evidence-honest botanical remedies) ──────────
    # Each monograph has name, scientific_name, evidence_verdicts
    # (CONFIRMED/MIXED/DISCORDANT for each claim), safety_notes, growing
    # notes, and an inline SVG. Searchable across the same substrate.
    herbs_mtime = int(_HERBS_FILE.stat().st_mtime) if _HERBS_FILE.exists() else 0
    for h in _read_jsonl(_HERBS_FILE):
        hid = h.get("id", "")
        traditional = ", ".join((h.get("traditional_uses") or [])[:3])
        summary = (h.get("summary") or "")
        if traditional:
            summary = f"Used for: {traditional}. {summary}"
        packets.append({
            "kind": "herb_monograph",
            "id": hid,
            "title": (h.get("name") or hid)[:120],
            # Most-strong evidence sets the headline verdict
            "verdict": (
                "CONFIRMED" if any(v.get("verdict") == "CONFIRMED"
                                   for v in (h.get("evidence_verdicts") or []))
                else "MIXED"
            ),
            "domains": list(h.get("domains") or ["medicine", "biology"]),
            "axes": list(h.get("axes") or ["physical_substance", "metabolism"]),
            "summary": summary[:280],
            "permalink": f"/packets.html?id={hid}",
            "api_path": f"/herbs/{hid}",
            "weight": 0.86,
            "timestamp": herbs_mtime,
        })

    # ── Wedges (intervention catalog ported from Coach OS v1.0) ───────
    # Each wedge is a named intervention — Repeat, Chunk, Echo, etc.
    # Phonics units and other curricula reference these by id.
    wedges_mtime = int(_WEDGES_FILE.stat().st_mtime) if _WEDGES_FILE.exists() else 0
    for w in _read_jsonl(_WEDGES_FILE):
        wid = w.get("id", "")
        packets.append({
            "kind": "wedge",
            "id": wid,
            "title": (w.get("name") or wid)[:120],
            "verdict": "CONFIRMED",
            "domains": list(w.get("domains") or ["pedagogy"]),
            "axes": list(w.get("axes") or ["authority_trust", "time_sequence"]),
            "summary": (w.get("description") or "")[:280],
            "permalink": f"/packets.html?id={wid}",
            "api_path": f"/wedges/{wid}",
            "weight": 0.76,
            "timestamp": wedges_mtime,
        })

    # ── Steward audit packets ─────────────────────────────────────────
    # Every admit/deny + token consume + corridor set. The audit is
    # the falsifiable substrate of the engine's refusals:
    # "the keeping is the substrate" applies to denials too.
    # Operator-readable; the unified index surfaces them so refusal
    # patterns are visible.
    for r in _read_jsonl(_STEWARD_AUDIT):
        pid = r.get("packet_id", "")
        ptype = r.get("packet_type", "steward_event")
        pl = r.get("payload") or {}
        reason = pl.get("reason_code", "")
        decision = pl.get("decision", "")
        action = pl.get("action", "")

        # Verdict mapping by packet_type + payload shape
        if ptype == "steward_admission_v1":
            verdict = "CONFIRMED" if decision == "admit" else "MISMATCH"
            title = f"{decision.upper() or 'EVENT'} · {action} · {reason}"
        elif ptype == "steward_corridor_set_v1":
            verdict = "CONFIRMED"
            title = f"CORRIDOR SET · {pl.get('name', '?')} · {pl.get('ttl_hours', '?')}h"
        elif ptype == "steward_token_consumed_v1":
            verdict = "CONFIRMED" if pl.get("ok") else "MISMATCH"
            title = f"TOKEN {'OK' if pl.get('ok') else 'FAIL'} · {action} · {reason}"
        else:
            verdict = "CONFIRMED"
            title = f"{ptype} · {action}"

        packets.append({
            "kind": "steward_audit",
            "id": pid,
            "title": title[:140],
            "verdict": verdict,
            "domains": ["governance"],
            "axes": ["authority_trust", "time_sequence"],
            "summary": (pl.get("notes") or "")[:280],
            "permalink": f"/steward.html#{pid}",
            "api_path": "/steward/audit",
            "weight": 0.55,
            "timestamp": int(r.get("created_at_ms", 0)) // 1000,
        })

    # ── Easton's Bible Dictionary (non-place entries: persons, concepts, objects)
    easton_mtime = int(_EASTON_FILE.stat().st_mtime) if _EASTON_FILE.exists() else 0
    for e in _read_jsonl(_EASTON_FILE):
        if (e.get("category") or "") == "place":
            continue  # already emitted as a place packet
        eid = e.get("id", "")
        slug = eid.replace("easton_", "", 1) if eid.startswith("easton_") else eid
        cat = e.get("category") or "concept"
        packets.append({
            "kind": "easton",
            "id": eid,
            "title": e.get("name") or eid,
            "verdict": "CONFIRMED",
            "domains": [cat],
            "axes": list(e.get("axes") or []),
            "summary": (e.get("text") or "")[:280],
            "permalink": f"/places.html?id={slug}",   # same lens, handles all categories
            "api_path": f"/easton/{slug}",
            "weight": 0.70,
            "timestamp": easton_mtime,
        })

    # ── Archetypes ─────────────────────────────────────────────────────
    cat_axes = _archetypes_axes_map()
    arch_dir = _REPO / "data" / "archetypes"
    arch_mtime = int(max((f.stat().st_mtime for f in arch_dir.glob("*.jsonl")), default=0)) if arch_dir.exists() else 0
    for a in _load_archetypes():
        aid = a.get("id", "")
        cat = (a.get("category") or "").lower()
        axes = list(cat_axes.get(cat, []))
        packets.append({
            "kind": "archetype",
            "id": aid,
            "title": a.get("name") or aid,
            "verdict": None,
            "domains": [],
            "axes": axes,
            "summary": (a.get("pattern") or "")[:280],
            "permalink": f"/archetypes.html#{aid}",
            "api_path": f"/archetypes/{aid}",
            "weight": 0.7,
            "timestamp": a.get("created_at") or arch_mtime,
        })

    # ── Floor of Discovery sections ────────────────────────────────────
    floor_mtime = int(_FLOOR_FILE.stat().st_mtime) if _FLOOR_FILE.exists() else 0
    for s in _read_jsonl(_FLOOR_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "floor",
            "id": sid,
            "title": s.get("title") or sid,
            "verdict": "CONFIRMED",
            "domains": [],
            "axes": list(s.get("axes") or []),
            "summary": (s.get("summary") or "")[:280],
            "permalink": f"/daily.html?floor={sid}",
            "api_path": f"/daily?floor={sid}",
            "weight": 0.95,
            "timestamp": floor_mtime,
        })

    # ── Body layers (Nested Control Systems Framework, public domain) ──
    body_mtime = int(_BODY_FILE.stat().st_mtime) if _BODY_FILE.exists() else 0
    for b in _read_jsonl(_BODY_FILE):
        bid = b.get("id", "")
        packets.append({
            "kind": "body_layer",
            "id": bid,
            "title": b.get("title") or bid,
            "verdict": "CONFIRMED",
            "domains": ["medicine", "physiology"],
            "axes": list(b.get("axes") or []),
            "summary": (b.get("function") or "")[:280],
            "permalink": f"/daily.html?body={bid}",
            "api_path": f"/daily?body={bid}",
            "weight": 0.85,
            "timestamp": body_mtime,
        })

    # ── Mind practices ─────────────────────────────────────────────────
    mind_mtime = int(_MIND_FILE.stat().st_mtime) if _MIND_FILE.exists() else 0
    for m in _read_jsonl(_MIND_FILE):
        mid = m.get("id", "")
        packets.append({
            "kind": "mind",
            "id": mid,
            "title": m.get("title") or mid,
            "verdict": "CONFIRMED",
            "domains": [],
            "axes": list(m.get("axes") or []),
            "summary": (m.get("summary") or "")[:280],
            "permalink": f"/daily.html?mind={mid}",
            "api_path": f"/daily?mind={mid}",
            "weight": 0.90,
            "timestamp": mind_mtime,
        })

    # ── Devotional reflections (Matt's own writings) ───────────────────
    devo_mtime = int(_DEVOTIONAL_FILE.stat().st_mtime) if _DEVOTIONAL_FILE.exists() else 0
    for r in _read_jsonl(_DEVOTIONAL_FILE):
        rid = r.get("id", "")
        # Convert iso date to epoch for chronological sort.
        date_str = r.get("date", "")
        ts = devo_mtime
        if date_str:
            try:
                import calendar
                y, mo, dy = map(int, date_str.split("-"))
                ts = int(calendar.timegm((y, mo, dy, 12, 0, 0, 0, 0, 0)))
            except (ValueError, AttributeError):
                pass
        packets.append({
            "kind": "devotional",
            "id": rid,
            "title": r.get("title") or rid,
            "verdict": "CONFIRMED",
            "domains": [],
            "axes": [],
            "summary": (r.get("body") or "")[:280],
            "permalink": f"/daily.html?devotional={rid}",
            "api_path": f"/daily?devotional={rid}",
            "weight": 0.80,
            "timestamp": ts,
        })

    # ── Proverbs (WEB Bible, public domain — 915 verses) ──────────────
    prov_mtime = int(_PROVERBS_FILE.stat().st_mtime) if _PROVERBS_FILE.exists() else 0
    for v in _read_jsonl(_PROVERBS_FILE):
        vid = v.get("id", "")
        ref = v.get("reference", vid)
        packets.append({
            "kind": "proverb",
            "id": vid,
            "title": ref,
            "verdict": "CONFIRMED",
            "domains": ["scripture_anchors", "theology_doctrine"],
            "axes": list(v.get("axes") or []),
            "summary": (v.get("text") or "")[:280],
            "permalink": f"/proverbs.html#{vid}",
            "api_path": f"/proverbs/{vid}",
            "weight": 0.95,
            "timestamp": prov_mtime,
        })

    # ── Ecclesiastes (WEB, 222 verses) ─────────────────────────────────
    eccl_mtime = int(_ECCL_FILE.stat().st_mtime) if _ECCL_FILE.exists() else 0
    for v in _read_jsonl(_ECCL_FILE):
        vid = v.get("id", "")
        packets.append({
            "kind": "ecclesiastes",
            "id": vid,
            "title": v.get("reference") or vid,
            "verdict": "CONFIRMED",
            "domains": ["scripture_anchors", "theology_doctrine"],
            "axes": list(v.get("axes") or []),
            "summary": (v.get("text") or "")[:280],
            "permalink": f"/scripture.html?ref={v.get('reference', '')}",
            "api_path": f"/scripture/{vid}",
            "weight": 0.95,
            "timestamp": eccl_mtime,
        })

    # ── James (WEB, 108 verses) ────────────────────────────────────────
    jas_mtime = int(_JAMES_FILE.stat().st_mtime) if _JAMES_FILE.exists() else 0
    for v in _read_jsonl(_JAMES_FILE):
        vid = v.get("id", "")
        packets.append({
            "kind": "james",
            "id": vid,
            "title": v.get("reference") or vid,
            "verdict": "CONFIRMED",
            "domains": ["scripture_anchors", "theology_doctrine"],
            "axes": list(v.get("axes") or []),
            "summary": (v.get("text") or "")[:280],
            "permalink": f"/scripture.html?ref={v.get('reference', '')}",
            "api_path": f"/scripture/{vid}",
            "weight": 0.95,
            "timestamp": jas_mtime,
        })

    # ── Psalms (WEB, 150 chapters as packets) ──────────────────────────
    ps_mtime = int(_PSALMS_FILE.stat().st_mtime) if _PSALMS_FILE.exists() else 0
    for ch in _read_jsonl(_PSALMS_FILE):
        cid = ch.get("id", "")
        packets.append({
            "kind": "psalm",
            "id": cid,
            "title": f"{ch.get('reference', '')} — {ch.get('title', '')}",
            "verdict": "CONFIRMED",
            "domains": ["scripture_anchors", "theology_doctrine"],
            "axes": list(ch.get("axes") or []),
            "summary": (ch.get("text") or "")[:280],
            "permalink": f"/scripture.html?ref={ch.get('reference', '')}",
            "api_path": f"/scripture/{cid}",
            "weight": 0.95,
            "timestamp": ps_mtime,
        })

    # ── Sermon on the Mount (Mt 5-7, 20 pericopes) ─────────────────────
    som_mtime = int(_SOM_FILE.stat().st_mtime) if _SOM_FILE.exists() else 0
    for p in _read_jsonl(_SOM_FILE):
        pid = p.get("id", "")
        packets.append({
            "kind": "sermon_on_mount",
            "id": pid,
            "title": f"{p.get('reference', '')} — {p.get('title', '')}",
            "verdict": "CONFIRMED",
            "domains": ["scripture_anchors", "theology_doctrine"],
            "axes": list(p.get("axes") or []),
            "summary": (p.get("text") or "")[:280],
            "permalink": f"/scripture.html?ref={p.get('reference', '')}",
            "api_path": f"/scripture/{pid}",
            "weight": 1.0,  # Words of Jesus weighted highest
            "timestamp": som_mtime,
        })

    # ── Marcus Aurelius Meditations (PG #2680) ─────────────────────────
    aur_mtime = int(_AURELIUS_FILE.stat().st_mtime) if _AURELIUS_FILE.exists() else 0
    for s in _read_jsonl(_AURELIUS_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "aurelius",
            "id": sid,
            "title": s.get("reference") or sid,
            "verdict": "CONFIRMED",
            "domains": ["philosophy", "rhetoric"],
            "axes": list(s.get("axes") or []),
            "summary": (s.get("text") or "")[:280],
            "permalink": f"/aurelius.html#{sid}",
            "api_path": f"/aurelius/{sid}",
            "weight": 0.85,
            "timestamp": aur_mtime,
        })

    # ── La Rochefoucauld Maxims (PG #9105) ─────────────────────────────
    lar_mtime = int(_LAROCH_FILE.stat().st_mtime) if _LAROCH_FILE.exists() else 0
    for m in _read_jsonl(_LAROCH_FILE):
        mid = m.get("id", "")
        packets.append({
            "kind": "larochefoucauld",
            "id": mid,
            "title": m.get("reference") or mid,
            "verdict": "CONFIRMED",
            "domains": ["philosophy", "rhetoric"],
            "axes": list(m.get("axes") or []),
            "summary": (m.get("text") or "")[:280],
            "permalink": f"/larochefoucauld.html#{mid}",
            "api_path": f"/larochefoucauld/{mid}",
            "weight": 0.82,
            "timestamp": lar_mtime,
        })

    # ── Didache (PG #42053, Hitchcock-Brown 1884) ──────────────────────
    did_mtime = int(_DIDACHE_FILE.stat().st_mtime) if _DIDACHE_FILE.exists() else 0
    for c in _read_jsonl(_DIDACHE_FILE):
        cid = c.get("id", "")
        packets.append({
            "kind": "didache",
            "id": cid,
            "title": c.get("reference") or cid,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "scripture_anchors"],
            "axes": list(c.get("axes") or []),
            "summary": (c.get("text") or "")[:280],
            "permalink": f"/didache.html#{cid}",
            "api_path": f"/didache/{cid}",
            "weight": 0.95,
            "timestamp": did_mtime,
        })

    # ── 1 Clement (Roberts-Donaldson, ANF01) ───────────────────────────
    cle_mtime = int(_CLEMENT_FILE.stat().st_mtime) if _CLEMENT_FILE.exists() else 0
    for c in _read_jsonl(_CLEMENT_FILE):
        cid = c.get("id", "")
        title_label = (c.get("title") or "").strip()
        ref = c.get("reference") or cid
        packets.append({
            "kind": "clement1",
            "id": cid,
            "title": f"{ref} — {title_label}" if title_label else ref,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "scripture_anchors"],
            "axes": list(c.get("axes") or []),
            "summary": (c.get("text") or "")[:280],
            "permalink": f"/clement1.html#{cid}",
            "api_path": f"/clement1/{cid}",
            "weight": 0.90,
            "timestamp": cle_mtime,
        })

    # ── Polycarp to the Philippians (Roberts-Donaldson, ANF01) ─────────
    pol_mtime = int(_POLYCARP_FILE.stat().st_mtime) if _POLYCARP_FILE.exists() else 0
    for c in _read_jsonl(_POLYCARP_FILE):
        cid = c.get("id", "")
        title_label = (c.get("title") or "").strip()
        ref = c.get("reference") or cid
        packets.append({
            "kind": "polycarp",
            "id": cid,
            "title": f"{ref} — {title_label}" if title_label else ref,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "scripture_anchors"],
            "axes": list(c.get("axes") or []),
            "summary": (c.get("text") or "")[:280],
            "permalink": f"/polycarp.html#{cid}",
            "api_path": f"/polycarp/{cid}",
            "weight": 0.90,
            "timestamp": pol_mtime,
        })

    # ── Ignatius's 7 letters + Barnabas + Martyrdom of Polycarp ────────
    for path, kind, label in [
        (_IGN_EPH_FILE,   "ignatius_eph",       "Ignatius to the Ephesians"),
        (_IGN_MAG_FILE,   "ignatius_mag",       "Ignatius to the Magnesians"),
        (_IGN_TRA_FILE,   "ignatius_tra",       "Ignatius to the Trallians"),
        (_IGN_ROM_FILE,   "ignatius_rom",       "Ignatius to the Romans"),
        (_IGN_PHILD_FILE, "ignatius_phild",     "Ignatius to the Philadelphians"),
        (_IGN_SMY_FILE,   "ignatius_smy",       "Ignatius to the Smyrnaeans"),
        (_IGN_POLYC_FILE, "ignatius_polyc",     "Ignatius to Polycarp"),
        (_BARNABAS_FILE,  "barnabas",           "Epistle of Barnabas"),
        (_MART_POL_FILE,  "martyrdom_polycarp", "Martyrdom of Polycarp"),
    ]:
        mtime = int(path.stat().st_mtime) if path.exists() else 0
        for c in _read_jsonl(path):
            cid = c.get("id", "")
            ref = c.get("reference") or cid
            title_label = (c.get("title") or "").strip()
            packets.append({
                "kind": kind,
                "id": cid,
                "title": f"{ref} — {title_label}" if title_label else ref,
                "verdict": "CONFIRMED",
                "domains": ["theology_doctrine", "scripture_anchors"],
                "axes": list(c.get("axes") or []),
                "summary": (c.get("text") or "")[:280],
                "permalink": f"/{kind}.html#{cid}",
                "api_path": f"/{kind}/{cid}",
                "weight": 0.90,
                "timestamp": mtime,
            })

    # ── Augustine Confessions (Pusey 1838) ─────────────────────────────
    aug_mtime = int(_AUG_CONF_FILE.stat().st_mtime) if _AUG_CONF_FILE.exists() else 0
    for s in _read_jsonl(_AUG_CONF_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "augustine_confessions",
            "id": sid,
            "title": s.get("reference") or sid,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "philosophy"],
            "axes": list(s.get("axes") or []),
            "summary": (s.get("text") or "")[:280],
            "permalink": f"/augustine_confessions.html#{sid}",
            "api_path": f"/augustine_confessions/{sid}",
            "weight": 0.92,
            "timestamp": aug_mtime,
        })

    # ── Imitation of Christ (Benham 1874) ──────────────────────────────
    imit_mtime = int(_IMIT_FILE.stat().st_mtime) if _IMIT_FILE.exists() else 0
    for c in _read_jsonl(_IMIT_FILE):
        cid = c.get("id", "")
        ref = c.get("reference") or cid
        title_label = (c.get("title") or "").strip()
        packets.append({
            "kind": "imitation_christ",
            "id": cid,
            "title": f"{ref} — {title_label}" if title_label else ref,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "philosophy"],
            "axes": list(c.get("axes") or []),
            "summary": (c.get("text") or "")[:280],
            "permalink": f"/imitation_christ.html#{cid}",
            "api_path": f"/imitation_christ/{cid}",
            "weight": 0.90,
            "timestamp": imit_mtime,
        })

    # ── Boethius Consolation (James 1897) ──────────────────────────────
    boe_mtime = int(_BOE_FILE.stat().st_mtime) if _BOE_FILE.exists() else 0
    for s in _read_jsonl(_BOE_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "boethius_consolation",
            "id": sid,
            "title": s.get("reference") or sid,
            "verdict": "CONFIRMED",
            "domains": ["philosophy", "rhetoric"],
            "axes": list(s.get("axes") or []),
            "summary": (s.get("text") or "")[:280],
            "permalink": f"/boethius_consolation.html#{sid}",
            "api_path": f"/boethius_consolation/{sid}",
            "weight": 0.88,
            "timestamp": boe_mtime,
        })

    # ── Pirkei Avot (Sefaria, CC-BY Joshua Kulp) ───────────────────────
    avot_mtime = int(_AVOT_FILE.stat().st_mtime) if _AVOT_FILE.exists() else 0
    for s in _read_jsonl(_AVOT_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "pirkei_avot",
            "id": sid,
            "title": s.get("reference") or sid,
            "verdict": "CONFIRMED",
            "domains": ["theology_doctrine", "philosophy"],
            "axes": list(s.get("axes") or []),
            "summary": (s.get("text") or "")[:280],
            "permalink": f"/pirkei_avot.html#{sid}",
            "api_path": f"/pirkei_avot/{sid}",
            "weight": 0.85,
            "timestamp": avot_mtime,
        })

    # ── Sermons (Matt's own writings) ──────────────────────────────────
    sermon_mtime = int(_SERMON_FILE.stat().st_mtime) if _SERMON_FILE.exists() else 0
    for s in _read_jsonl(_SERMON_FILE):
        sid = s.get("id", "")
        packets.append({
            "kind": "sermon",
            "id": sid,
            "title": s.get("title") or sid,
            "verdict": "CONFIRMED",
            "domains": [],
            "axes": [],
            "summary": (s.get("body") or "")[:280],
            "permalink": f"/daily.html?sermon={sid}",
            "api_path": f"/daily?sermon={sid}",
            "weight": 0.85,
            "timestamp": sermon_mtime,
        })

    # ── Receipts ───────────────────────────────────────────────────────
    for r in _read_jsonl(_RECEIPTS_FILE):
        iid = r.get("intake_id", "")
        aid = r.get("almanac_entry_id", "")
        packets.append({
            "kind": "receipt",
            "id": iid,
            "title": f"Receipt → {r.get('almanac_entry_title') or aid}",
            "verdict": "CONFIRMED",
            "domains": [],
            "axes": [],
            "summary": f"Promotion receipt from {r.get('contributor_handle') or 'anon'} to {aid}",
            "permalink": f"/receipts/{iid}",
            "api_path": f"/receipts/{iid}",
            "weight": 0.5,
            "timestamp": r.get("promoted_at") or 0,
        })

    # ── Seeds — auto-crafted from search misses ─────────────────────────
    for s in _read_jsonl(_SEEDS_FILE):
        packets.append({
            "kind": "seed",
            "id": s.get("id", ""),
            "title": s.get("title", ""),
            "verdict": s.get("verdict"),
            "domains": list(s.get("domains") or []),
            "axes": list(s.get("axes") or []),
            "summary": (s.get("summary") or "")[:280],
            "permalink": s.get("permalink") or f"/?q={s.get('query', '')}",
            "api_path": s.get("api_path") or f"/seed/{s.get('id', '')}",
            "weight": s.get("weight", 0.85),
            "timestamp": s.get("timestamp", 0),
        })

    return packets


def load_all() -> List[Dict[str, Any]]:
    """mtime-cached load of every packet across every store."""
    mtime = _all_mtimes()
    if _CACHE["packets"] and mtime <= _CACHE["mtime"]:
        return _CACHE["packets"]
    packets = _normalize_packet_records()
    _CACHE["mtime"] = mtime
    _CACHE["packets"] = packets
    return packets


# The WISDOM subset — the kinds the well draws from (Scripture, psalms, protocols,
# parables, patristics...). Lives HERE so packets is the single source of truth for
# "what is wisdom"; well_retriever consumes load_all_wisdom() instead of re-filtering.
# Drops Easton dictionary / geography / genealogy / build-queue noise.
WISDOM_KINDS = {
    "scripture", "psalm", "proverbs", "ecclesiastes", "almanac", "protocol",
    "parable", "fieldkit_card", "sermon", "pilgrim", "imitation_christ",
    "pirkei_avot", "augustine_confessions", "boethius_consolation", "aurelius",
    "polycarp", "clement1", "didache", "barnabas", "james", "ignatius_eph",
    "ignatius_mag", "ignatius_rom", "ignatius_tra", "ignatius_smy", "ignatius_phild",
    "ignatius_polyc", "martyrdom_polycarp",
}


def load_all_wisdom() -> List[Dict[str, Any]]:
    """Only the WISDOM-kind packets (the well's corpus) — the same filter the well
    applied inline, now centralized. Exact equivalent of
    [p for p in load_all() if (p.get('kind') or '') in WISDOM_KINDS]."""
    return [p for p in load_all() if (p.get("kind") or "") in WISDOM_KINDS]


def by_domain(domain: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Return every packet that names this verifier domain."""
    d = (domain or "").strip().lower()
    if not d:
        return []
    out = [p for p in load_all() if d in [x.lower() for x in (p.get("domains") or [])]]
    out.sort(key=lambda p: p.get("weight", 0), reverse=True)
    return out[:limit]


def by_axis(axis: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Return every packet that touches this 7-scaffold axis."""
    a = (axis or "").strip().lower()
    if not a:
        return []
    out = [p for p in load_all() if a in [x.lower() for x in (p.get("axes") or [])]]
    out.sort(key=lambda p: p.get("weight", 0), reverse=True)
    return out[:limit]


def by_kind(kind: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Return every packet of a given kind (almanac, protocol, etc.)."""
    k = (kind or "").strip().lower()
    if not k:
        return []
    out = [p for p in load_all() if (p.get("kind") or "").lower() == k]
    out.sort(key=lambda p: p.get("weight", 0), reverse=True)
    return out[:limit]


def chronological(
    *, limit: int = 500, kinds: Optional[List[str]] = None, newest_first: bool = True
) -> List[Dict[str, Any]]:
    """Return every packet sorted by timestamp.

    The temporal lens. Drops packets with timestamp == 0 (unknown).
    """
    packets = load_all()
    if kinds:
        allowed = {k.strip().lower() for k in kinds if k.strip()}
        packets = [p for p in packets if (p.get("kind") or "").lower() in allowed]
    # Drop packets without a usable timestamp so the timeline reads cleanly
    packets = [p for p in packets if (p.get("timestamp") or 0) > 0]
    packets.sort(key=lambda p: p.get("timestamp", 0), reverse=newest_first)
    return packets[:limit]


def _parse_field_filters(qstr: str) -> tuple:
    """Pull `field:value` tokens out of the query. Returns (text_tokens, filters).

    Supported field prefixes:
      kind:X        — restrict to kind=X (multiple allowed → OR)
      verdict:X     — restrict to verdict=X (CONFIRMED|MISMATCH|MIXED|OBSOLETE|...)
      domain:X      — packet must list this domain
      axis:X        — packet must list this axis

    Multiple of the same field are OR'd; different fields are AND'd.
    Plain tokens (no colon) become text search tokens as before.
    """
    text_tokens: list = []
    filters: Dict[str, Set[str]] = {}
    for tok in qstr.split():
        if ":" in tok and len(tok) > 2:
            field, _, val = tok.partition(":")
            field = field.strip()
            val = val.strip().lower()
            if field in ("kind", "verdict", "domain", "axis") and val:
                filters.setdefault(field, set()).add(val)
                continue
        text_tokens.append(tok)
    return text_tokens, filters


def search(
    q: str,
    *,
    limit: int = 60,
    kinds: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Cross-lens text search over the unified packet substrate.

    All-tokens-must-match (AND). Each token is scored by where it
    appears in the packet record:
      title:    +5  per token
      verdict:  +2
      domains:  +2  per matched domain
      axes:     +2  per matched axis
      summary:  +1
      id:       +0.5 (so people can search by partial id)

    Field-prefixed tokens are filters, not scored:
      kind:almanac forgive       — only almanac packets, scored on "forgive"
      verdict:CONFIRMED ginger   — only CONFIRMED packets, scored on "ginger"
      domain:medicine            — only packets tagged with medicine domain
      axis:metabolism            — only packets on the metabolism axis
      kind:almanac kind:protocol — almanac OR protocol

    Tie-break by packet weight (descending). Result is the standard
    normalized packet dict + a `score` and a `match_in` list
    describing which fields matched.
    """
    qstr = (q or "").strip().lower()
    if not qstr:
        return []
    tokens, field_filters = _parse_field_filters(qstr)

    # If the user gave kind:X filters, they override the kinds= param
    if "kind" in field_filters:
        allowed_kinds: Optional[Set[str]] = field_filters["kind"]
    elif kinds:
        allowed_kinds = {k.strip().lower() for k in kinds if k.strip()}
        if not allowed_kinds:
            allowed_kinds = None
    else:
        allowed_kinds = None

    required_verdicts = field_filters.get("verdict")
    required_domains  = field_filters.get("domain")
    required_axes     = field_filters.get("axis")

    # If user only supplied filters (no text tokens), keep all matching
    # packets ranked by weight. This makes `verdict:MISMATCH` (alone) work.
    text_only_mode = not tokens

    out: List[Dict[str, Any]] = []
    for p in load_all():
        if allowed_kinds and (p.get("kind") or "").lower() not in allowed_kinds:
            continue
        verdict_l = (p.get("verdict") or "").lower()
        if required_verdicts and verdict_l not in required_verdicts:
            continue
        domains = [d.lower() for d in (p.get("domains") or [])]
        axes    = [a.lower() for a in (p.get("axes")    or [])]
        if required_domains and not required_domains.issubset(set(domains)):
            continue
        if required_axes and not required_axes.issubset(set(axes)):
            continue

        title   = (p.get("title")   or "").lower()
        summary = (p.get("summary") or "").lower()
        pid     = (p.get("id")      or "").lower()
        domains_str = " ".join(domains)
        axes_str    = " ".join(axes)

        score = 0.0
        match_in: List[str] = []
        all_matched = True
        for tok in tokens:
            hit = False
            if tok in title:        score += 5.0; hit = True; match_in.append("title")
            if tok in verdict_l:    score += 2.0; hit = True; match_in.append("verdict")
            if tok in domains_str:  score += 2.0; hit = True; match_in.append("domain")
            if tok in axes_str:     score += 2.0; hit = True; match_in.append("axis")
            if tok in summary:      score += 1.0; hit = True; match_in.append("summary")
            if tok in pid:          score += 0.5; hit = True; match_in.append("id")
            if not hit:
                all_matched = False
                break
        if not text_only_mode and (not all_matched or score <= 0):
            continue

        rec = dict(p)
        # When filtering-only, score is just the weight so the ranker
        # still surfaces higher-quality packets first.
        if text_only_mode:
            score = float(p.get("weight") or 0)
            match_in.append("filter")
        rec["score"] = round(score, 2)
        rec["match_in"] = sorted(set(match_in))
        out.append(rec)

    out.sort(key=lambda r: (r["score"], r.get("weight", 0)), reverse=True)
    return out[: max(1, min(500, int(limit)))]


def index_summary() -> Dict[str, Any]:
    """Per-kind counts + per-domain counts + per-axis counts + per-verdict counts.
    Surfaces the shape of the whole packet universe at a glance."""
    packets = load_all()
    by_k: Dict[str, int] = {}
    by_d: Dict[str, int] = {}
    by_a: Dict[str, int] = {}
    by_v: Dict[str, int] = {}
    weighted_total = 0.0
    newest_ts = 0
    for p in packets:
        by_k[p.get("kind", "?")] = by_k.get(p.get("kind", "?"), 0) + 1
        for d in (p.get("domains") or []):
            by_d[d] = by_d.get(d, 0) + 1
        for ax in (p.get("axes") or []):
            by_a[ax] = by_a.get(ax, 0) + 1
        v = (p.get("verdict") or "").strip().upper()
        if v:
            by_v[v] = by_v.get(v, 0) + 1
        try:
            weighted_total += float(p.get("weight") or 0)
            ts = int(p.get("timestamp") or 0)
            if ts > newest_ts:
                newest_ts = ts
        except (TypeError, ValueError):
            pass
    return {
        "total_packets": len(packets),
        "kinds_count":   len(by_k),
        "domains_count": len(by_d),
        "axes_count":    len(by_a),
        "avg_weight":    round(weighted_total / max(1, len(packets)), 3),
        "newest_timestamp": newest_ts,
        "by_kind":    dict(sorted(by_k.items(), key=lambda kv: -kv[1])),
        "by_domain":  dict(sorted(by_d.items(), key=lambda kv: -kv[1])),
        "by_axis":    dict(sorted(by_a.items(), key=lambda kv: -kv[1])),
        "by_verdict": dict(sorted(by_v.items(), key=lambda kv: -kv[1])),
        "generated_at": int(time.time()),
    }
