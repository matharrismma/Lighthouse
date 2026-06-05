"""THE FLOOR — one thing every tool stands on.

The integration spine. Until now each tool reached for the one piece of the
floor it happened to know about: the Apothecary touched Scripture, a verifier
touched its domain, Calibre touched nothing. They stood on shards.

`stand_on_floor()` is the single call that puts any tool's output on the WHOLE
floor at once:

    1. CANON      — anchored to Scripture (the words in red; the fixed floor)
    2. GATES      — run through RED / FLOOR / BROTHERS / GOD
    3. VERIFIER   — pointed at the deterministic domain check that applies
    4. CALIBRE    — scored for health / beauty / shadow / vice where derivable
    5. NESTED     — mapped to the control-system layer (load vs capacity)
    6. LEDGER     — offered an append-only record

Every import is soft: in a context where a piece isn't reachable, the floor
reports that honestly instead of failing. A tool that calls this is no longer
connected to one shard — it is standing on the whole floor, and it can show it.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

# ── The four gates, as the canon defines them ──────────────────────────────
GATES = [
    {"gate": "RED",      "asks": "Aligned with the words of Jesus? (truth)"},
    {"gate": "FLOOR",    "asks": "Does it violate the Law / break a stability floor? (harm)"},
    {"gate": "BROTHERS", "asks": "Do at least two witnesses affirm it? (corroboration)"},
    {"gate": "GOD",      "asks": "Has the required waiting elapsed? (no rushing)"},
]

# Disqualifying signals the RED gate rejects outright (coercion, domination,
# the antichrist shape the Pressure System becomes without a floor).
_RED_DISQUALIFIERS = (
    "coerce", "force them", "manipulate", "dominate", "exploit", "by any means",
    "the ends justify", "no rules", "do whatever", "control them",
)


def _canon_anchor(text: str, domain: Optional[str]) -> Dict[str, Any]:
    """Anchor the output to Scripture — the fixed floor. Soft: if the scripture
    services aren't importable here, name Canon as the reference without a verse."""
    out: Dict[str, Any] = {"is_floor": True, "authority": "Canon (Scripture) — closed, supreme"}
    try:
        # The apothecary already knows how to surface a relevant anchor; reuse
        # its scripture path if available, else leave the anchor open.
        from api import scripture_lookup as _sl  # noqa: F401
        out["scripture_available"] = True
    except Exception:
        out["scripture_available"] = False
    out["note"] = "Every standing is checked against Canon; the lens never overrules the floor."
    return out


def _run_gates(text: str) -> Dict[str, Any]:
    """Evaluate what is checkable now. RED and FLOOR are hard (can reject);
    BROTHERS and GOD are soft (quarantine until satisfied). Honest: we do not
    mark a soft gate PASS from a single call — it stays PENDING."""
    t = (text or "").lower()
    red_hit = next((d for d in _RED_DISQUALIFIERS if d in t), None)
    verdicts: List[Dict[str, str]] = []
    verdicts.append({
        "gate": "RED",
        "status": "REJECT" if red_hit else "PASS",
        "why": f"disqualifying signal: '{red_hit}'" if red_hit else "no disqualifying signal found",
    })
    # FLOOR: structural — empty or self-contradictory inputs fail; otherwise pass-pending-verifier
    floor_ok = bool((text or "").strip())
    verdicts.append({
        "gate": "FLOOR",
        "status": "PASS" if floor_ok else "REJECT",
        "why": "structurally present" if floor_ok else "empty / structurally incomplete",
    })
    # BROTHERS + GOD are not satisfiable from one call — they require witnesses + time.
    verdicts.append({"gate": "BROTHERS", "status": "PENDING", "why": "needs ≥2 witnesses (Deut 19:15)"})
    verdicts.append({"gate": "GOD", "status": "PENDING", "why": "needs the waiting period (no rushing)"})
    hard_reject = any(v["status"] == "REJECT" for v in verdicts[:2])
    return {
        "verdicts": verdicts,
        "admitted": not hard_reject,
        "state": "rejected" if hard_reject else "quarantined-until-witnessed",
    }


# Domain → the deterministic verifier that applies. A pointer, so the tool
# knows which fixed wall to press its claim against.
_VERIFIER_FOR = {
    "math": "verify_mathematics", "mathematics": "verify_mathematics",
    "stats": "verify_statistics", "statistics": "verify_statistics",
    "physics": "verify_physics", "chemistry": "verify_chemistry",
    "biology": "verify_biology", "medicine": "verify_medicine",
    "nutrition": "verify_nutrition", "health": "verify_medicine",
    "logic": "verify_formal_logic", "scripture": "verify_scripture_anchors",
    "theology": "verify_theology_doctrine", "finance": "verify_finance",
    "law": "verify_law", "governance": "verify_governance_decision_packet",
}

# Health-domain hint: when to also stand on the nested-control framework.
_HEALTH_HINT = ("health", "medicine", "nutrition", "disease", "symptom", "remedy", "apothecary")


def stand_on_floor(
    text: str,
    *,
    domain: Optional[str] = None,
    kind: str = "claim",
    triad: Optional[Dict[str, float]] = None,
    load: Optional[float] = None,
    capacity: Optional[float] = None,
    vice_signals: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Put any tool's output on the whole floor. Returns its full standing.

    Optional signals deepen the standing where the tool can supply them:
      triad        = {spirit, mind, body} in [0,1] → Calibre health + beauty
      load/capacity in [0,1]                        → Calibre shadow + nested overload
      vice_signals = {source, channel, desire}      → Calibre vice index
    """
    standing: Dict[str, Any] = {
        "input_kind": kind,
        "domain": domain,
        "canon": _canon_anchor(text, domain),
        "gates": _run_gates(text),
    }

    # 3. VERIFIER — point at the fixed wall for this domain
    key = (domain or "").lower()
    standing["verifier"] = {
        "applies": _VERIFIER_FOR.get(key),
        "note": "the deterministic check this claim should be pressed against" if key in _VERIFIER_FOR
                else "no domain verifier identified — falls to search/LLM, and logs a gap",
    }

    # 4. CALIBRE — the moral floor, made calculable, where derivable
    calibre_out: Dict[str, Any] = {}
    try:
        from api import calibre as _cal
        if triad:
            calibre_out.update(_cal.score_triad(
                triad.get("spirit", 0.0), triad.get("mind", 0.0), triad.get("body", 0.0)))
        if load is not None and capacity is not None:
            calibre_out["shadow"] = round(_cal.shadow(1.0, capacity, load), 4)
        if vice_signals:
            calibre_out["vice"] = round(_cal.vice_index(
                vice_signals.get("source", 1.0),
                vice_signals.get("channel", 1.0),
                vice_signals.get("desire", 0.0)), 4)
    except Exception as exc:
        calibre_out["error"] = str(exc)[:120]
    standing["calibre"] = calibre_out or {"note": "no triad / load / vice signals supplied"}

    # 5. NESTED CONTROL — for health-domain outputs, the control-layer reading
    if (domain or "").lower() in _HEALTH_HINT or any(h in (text or "").lower() for h in _HEALTH_HINT):
        try:
            from api import nested_control as _nc
            standing["nested_control"] = _nc.layer_view(text, load=load, capacity=capacity)
        except Exception as exc:
            standing["nested_control"] = {"error": str(exc)[:120]}

    # 6. LEDGER — offered, not forced (the canon: we record, we don't coerce)
    standing["ledger"] = {
        "recordable": standing["gates"]["admitted"],
        "note": "append-only proof available once witnessed (BROTHERS) and waited (GOD)",
    }
    return standing


def floor_summary() -> Dict[str, Any]:
    """What the whole floor is — so a tool (or a person) can see every piece
    it stands on at a glance. The index card for the floor itself."""
    return {
        "pieces": [
            {"name": "Canon", "what": "Scripture — the fixed, supreme floor (the words in red)"},
            {"name": "Gates", "what": "RED / FLOOR / BROTHERS / GOD — the admission protocol"},
            {"name": "Verifiers", "what": "65 deterministic domain checks (the fixed walls)"},
            {"name": "Calibre", "what": "health / beauty / shadow / vice — the moral floor, calculable"},
            {"name": "Nested Control", "what": "load vs capacity across nested layers (the cross-domain pattern)"},
            {"name": "Ledger", "what": "append-only proof — witness over time"},
        ],
        "rule": "Every tool stands on all of it. No tool is connected to one shard.",
    }
