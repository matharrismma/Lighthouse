"""placeholders.py — placeholders to truth.

A placeholder is a provisional structure we integrate into the map of reality to
SCAFFOLD and PREDICT — honestly marked as not-yet-confirmed, held open to being
confirmed, refined, or replaced as truth is approached. It is "to truth", not
truth: it points toward, in service of, the real arrangement we don't yet fully
hold.

This is the project's spine made explicit (map-never-launder; graded verdicts;
the grid's "discovery, not design"; the apex left reserved). Most of a developing
map is provisional — a placeholder is the honest way to hold that, usefully,
without claiming finality. Agents reason WITH placeholders knowing they are
provisional; the symmetry/structure they encode can predict gaps even before it
is confirmed.

This is a SEARCH, not a creed. Holding placeholders and navigating the map toward
truth is a search over hypothesis space: the best-fitting theory is the greedy
start (exploitation); the engine's "eliminate what is not the answer" is pruning.
But a search that only expands CONFIRMING nodes converges prematurely — a local
optimum, an echo chamber. So every placeholder carries its own DISCONFIRMERS:
  falsifiers     — what observation would refute it (it must be refutable at all);
  unlikely_tests — the non-examples to hunt and the improbable cases to try first.
A placeholder ADVANCES BY SURVIVING these, never by piling up confirmations. This
is the search's exploration term — the deliberate spend on disconfirmation that
keeps the map honest instead of self-reinforcing. (Most of science is unsettled;
we use the best fit as a start AND attack it.)

Grades (rate of descent from confirmed source — low to high standing):
  coincidence < resonance < plausible < candidate < confirmed
A placeholder lives at resonance/plausible/candidate. It rises only by SURVIVING
its falsifiers and unlikely tests — not by accumulating agreeing evidence. When a
better model arrives, it is superseded (retired, never deleted — the record of
the approach is kept). A placeholder with NO falsifiers is the weakest kind: it
cannot be wrong, so it cannot be trusted.

Store: append-only JSONL at data/placeholders/placeholders.jsonl (the ledger
pattern). Seeded with the inaugural placeholder: supersymmetry as a map
ARRANGEMENT lens. Never sealed as final — that belongs to the reserved apex.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "placeholders"
_PATH = _DIR / "placeholders.jsonl"
_GRADES = ("coincidence", "resonance", "plausible", "candidate", "confirmed", "retired")
_ID_RE = re.compile(r"^[a-z0-9_]{3,64}$")

# The inaugural placeholder — supersymmetry as how the map is arranged. Honest:
# SUSY is elegant but experimentally UNCONFIRMED; we borrow only its STRUCTURE
# (pairing -> prediction of the missing partner) as a provisional arrangement lens.
_SEED: List[Dict[str, Any]] = [
    {
        "id": "supersymmetry_pairing_arrangement",
        "name": "Supersymmetry — pairing as the map's arrangement",
        "status": "placeholder",
        "grade": "resonance",
        "kind": "arrangement_principle",
        "claim": ("Arrange the map so each axis/node has a dual; the symmetry then "
                  "PREDICTS the missing partner — a broken pair is a gap that tells us "
                  "what to look for, the way SUSY predicts a superpartner."),
        "organizes": ("the dimensional scaffold — how domains pair across a symmetry. "
                      "The breath is already palindromic (1-3-3-4-3-1), symmetric about "
                      "the quadratic center."),
        "predicts": [
            "order <-> uncertainty  (both present — a confirmed pair)",
            "conservation_balance <-> metabolism  (kept vs transformed)",
            "discreteness -> continuity  (partner MISSING — a predicted axis)",
            "physical_substance -> the abstract/spirit  (the two trees)",
        ],
        "provenance": ("Supersymmetry is an elegant but EXPERIMENTALLY UNCONFIRMED "
                       "physics hypothesis (no superpartners observed at the LHC; the "
                       "expected scale is increasingly disfavored). Borrowed here ONLY as "
                       "a provisional arrangement lens, never as a validated law."),
        "caveat": ("Held as a PLACEHOLDER TO TRUTH. Our current arrangement may be "
                   "better, or a more accurate model may replace this. Elegance is a "
                   "witness, not a proof; symmetry PROPOSES the missing partner, real "
                   "data CONFIRMS it. Discovery, not design — never force a pair."),
        "falsifiers": [
            "A fundamental, well-attested domain that fits NO dual — a genuinely unpaired "
            "axis the symmetry cannot place.",
            "A predicted partner (e.g. continuity) that, when sought, corresponds to no real "
            "domain — the pairing predicts ghosts.",
            "A non-symmetric arrangement that explains adjacency / depth / coherence BETTER, "
            "with fewer assumptions.",
        ],
        "unlikely_tests": [
            "Hunt the domains that BREAK the pairing, not the ones that confirm it (this is "
            "the exploration term — skip it and the map becomes an echo chamber).",
            "Test the WEAKEST predicted partner first, not the strongest.",
            "Arrange the map with NO symmetry and measure whether it loses explanatory power; "
            "if it doesn't, the symmetry was decoration, not structure.",
        ],
        "advances_by": "surviving the falsifiers and unlikely_tests above — not by confirmations.",
        "refutable": True,
        "lifecycle": "held",
        "supersedes": None,
        "superseded_by": None,
        "held_since": "2026-06-18",
        "seed_v": 2,
    },
]


def _load() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        if _PATH.exists():
            for line in _PATH.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        pass
    except Exception:
        pass
    return out


def _append(rec: Dict[str, Any]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    with open(_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _ensure_seeded() -> None:
    # Append a seed when it's missing OR when its seed_v is newer than the stored
    # one (listing/get use last-wins, so a re-appended seed supersedes the old).
    stored_v: Dict[str, int] = {}
    for r in _load():
        if r.get("id"):
            stored_v[r["id"]] = max(stored_v.get(r["id"], 0), int(r.get("seed_v", 0) or 0))
    for r in _SEED:
        if stored_v.get(r["id"], -1) < int(r.get("seed_v", 0) or 0):
            _append(r)


_ensure_seeded()


def listing() -> Dict[str, Any]:
    """All placeholders, newest first by held_since, deduped by id (last wins —
    so a refine/retire append supersedes the earlier record)."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in _load():
        if r.get("id"):
            by_id[r["id"]] = r
    items = [r for r in by_id.values() if r.get("lifecycle") != "retired"]
    items.sort(key=lambda r: r.get("held_since", ""), reverse=True)
    return {
        "placeholders": items,
        "count": len(items),
        "grades": list(_GRADES),
        "what_is_this": ("Placeholders to truth: provisional structures integrated into "
                         "the map to scaffold and predict, honestly marked as not-yet-"
                         "confirmed, held open to confirm / refine / replace. Not truth — "
                         "toward it. The final truth is never sealed (the apex is reserved)."),
        "the_method": ("This is a SEARCH, and it must explore, not just exploit. Each "
                       "placeholder carries falsifiers (what would refute it) and "
                       "unlikely_tests (the non-examples to hunt) — it ADVANCES BY SURVIVING "
                       "them, never by confirmations. Skip the disconfirming probes and the "
                       "map becomes an echo chamber. A placeholder with no falsifiers "
                       "(refutable=false) is the weakest kind."),
    }


def get(pid: str) -> Optional[Dict[str, Any]]:
    rec = None
    for r in _load():
        if r.get("id") == pid:
            rec = r  # last wins
    return rec


def propose(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Add or update a placeholder. Honest by default: grade is clamped to the
    provisional band (never 'confirmed' here — confirmation is earned by data,
    elsewhere). Returns the stored record."""
    pid = str(rec.get("id") or "").strip().lower().replace(" ", "_")
    if not _ID_RE.match(pid):
        return {"error": "id must be 3-64 chars of [a-z0-9_]"}
    grade = str(rec.get("grade") or "resonance").lower()
    if grade not in ("coincidence", "resonance", "plausible", "candidate", "retired"):
        grade = "resonance"  # cannot self-declare 'confirmed'
    stored = {
        "id": pid,
        "name": str(rec.get("name") or pid)[:160],
        "status": "placeholder",
        "grade": grade,
        "kind": str(rec.get("kind") or "concept")[:60],
        "claim": str(rec.get("claim") or "")[:1200],
        "organizes": str(rec.get("organizes") or "")[:600],
        "predicts": [str(x)[:200] for x in (rec.get("predicts") or [])][:12],
        "provenance": str(rec.get("provenance") or "")[:800],
        "caveat": str(rec.get("caveat") or
                      "Held as a placeholder to truth — provisional, open to revision.")[:600],
        # Disconfirmers are first-class: a placeholder must be refutable, and it
        # advances by SURVIVING these (not by confirmations). Empty falsifiers is a
        # weakness, flagged in the record.
        "falsifiers": [str(x)[:300] for x in (rec.get("falsifiers") or [])][:8],
        "unlikely_tests": [str(x)[:300] for x in (rec.get("unlikely_tests") or [])][:8],
        "advances_by": "surviving its falsifiers and unlikely_tests — not by confirmations.",
        "refutable": bool(rec.get("falsifiers")),
        "lifecycle": str(rec.get("lifecycle") or "held")[:20],
        "supersedes": rec.get("supersedes"),
        "superseded_by": rec.get("superseded_by"),
        "held_since": time.strftime("%Y-%m-%d", time.gmtime()),
    }
    _append(stored)
    return stored
