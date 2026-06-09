"""witness_authorship.py — the authorship witness path (Matt's-lens ruling, 2026-06-09).

A card at authority_tier "matt" is ORIGINAL writing. It cannot be witnessed by the
source-gate (no >=2 external sources exist — the author IS the source), and it must
NOT be self-attested ("government cannot witness itself", Deut 19:15). Matt's ruling:

    Original authorship is witnessed when it ANCHORS to >=2 of the authorities ABOVE
    it — Scripture references and/or church-elder sources it rests on.

The writing is corroborated by what it submits to, never by itself. This is faithful
both to Deut 19:15 (corroboration by others) and to the hierarchy (Matt's writing sits
below Scripture + the elders, above the engine's).

Deterministic + evidence-based — NO oracle. The anchors counted are:
  - Scripture references in the card title/body (api.walk._extract_scripture_refs)
  - connections to Scripture-kind cards (scripture / psalm / proverb / ...)
  - connections to elder/father/apostolic authority-tier cards
Distinct count >= MIN_ANCHORS  -> "passed" (witnessed by its anchors)
                  < MIN_ANCHORS -> "insufficient" (honest — not yet anchored)

This module is READ-ONLY by default (evaluate / a dry-run report). `apply_gate(...)`
writes witness_status onto the qualifying cards; it is OPERATOR-GATED and must never
be auto-run (no timer, no steward call) — the operator runs `--apply` deliberately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"

MATT_TIER = "matt"
MIN_ANCHORS = 2  # Deut 19:15 — "two or three witnesses"
_SCRIPTURE_KINDS = {"scripture", "psalm", "proverb", "proverbs", "ecclesiastes",
                    "james", "sermon_on_mount"}
_ELDER_TIERS = {"father", "elder", "apostolic"}


def _read(cid: str) -> Optional[dict]:
    p = CARDS_DIR / f"{cid}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def count_anchors(card: dict, reader=_read) -> Dict[str, Any]:
    """Count the distinct Scripture/elder anchors a card rests on. `reader` resolves
    a connected card_id -> card dict (injectable for testing). Returns the anchor
    breakdown + a `witnesses` list shaped like the rest of the witness schema."""
    from api import walk as _walk
    witnesses: List[Dict[str, str]] = []
    seen: Set[str] = set()

    # 1) Scripture references in the writing itself.
    body = (card.get("title") or "") + " " + (card.get("body") or "")
    for ref in sorted(_walk._extract_scripture_refs(body)):
        key = "scripture:" + ref
        if key not in seen:
            seen.add(key)
            witnesses.append({"class": "scripture", "ref": ref, "via": "body"})

    # 2) Connections to Scripture-kind / elder-tier cards.
    for x in (card.get("connections") or []):
        tid = x.get("to_card_id")
        if not tid:
            continue
        cc = reader(tid)
        if not cc:
            continue
        kind = cc.get("kind")
        tier = (cc.get("source") or {}).get("authority_tier")
        if kind in _SCRIPTURE_KINDS:
            key = "scripture-card:" + tid
            if key not in seen:
                seen.add(key)
                witnesses.append({"class": "scripture", "ref": cc.get("title") or tid,
                                  "via": "connection", "card_id": tid})
        elif tier in _ELDER_TIERS:
            key = "elder:" + tid
            if key not in seen:
                seen.add(key)
                witnesses.append({"class": "elder", "ref": cc.get("title") or tid,
                                  "via": "connection", "card_id": tid})

    return {"count": len(witnesses), "witnesses": witnesses}


def evaluate(card: dict, reader=_read) -> Dict[str, Any]:
    """Apply Matt's authorship-witness rule to ONE matt-tier card. Returns the
    proposed witness_status + witnesses + reason (does NOT write)."""
    a = count_anchors(card, reader=reader)
    n = a["count"]
    if n >= MIN_ANCHORS:
        status, reason = "passed", f"authored work anchored to {n} Scripture/elder authorities (Deut 19:15)"
    else:
        status, reason = "insufficient", f"needs >={MIN_ANCHORS} Scripture/elder anchors; has {n}"
    return {"witness_status": status, "witnesses": a["witnesses"],
            "witness_status_reason": reason, "anchor_count": n}


def survey() -> Dict[str, Any]:
    """Read-only: evaluate every unwitnessed matt-tier card. Returns a report —
    no card is modified."""
    out = {"matt_tier_unwitnessed": 0, "would_pass": 0, "insufficient": 0, "cards": []}
    if not CARDS_DIR.exists():
        return out
    for f in CARDS_DIR.glob("card_n_*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (c.get("source") or {}).get("authority_tier") != MATT_TIER:
            continue
        if c.get("witness_status") == "passed":
            continue
        out["matt_tier_unwitnessed"] += 1
        ev = evaluate(c)
        out["would_pass" if ev["witness_status"] == "passed" else "insufficient"] += 1
        out["cards"].append({"id": c.get("id"), "title": (c.get("title") or "")[:80],
                             "anchor_count": ev["anchor_count"],
                             "status": ev["witness_status"]})
    return out


def apply_gate() -> Dict[str, Any]:
    """OPERATOR-GATED. Write witness_status onto qualifying matt-tier cards. Only
    promotes cards that clear the >=2-anchor bar; never demotes, never self-attests.
    Must be invoked deliberately (`--apply`), never by a timer or the steward."""
    report = {"promoted": [], "left_insufficient": 0}
    if not CARDS_DIR.exists():
        return report
    for f in CARDS_DIR.glob("card_n_*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if (c.get("source") or {}).get("authority_tier") != MATT_TIER:
            continue
        if c.get("witness_status") == "passed":
            continue
        ev = evaluate(c)
        if ev["witness_status"] != "passed":
            report["left_insufficient"] += 1
            continue
        c["witness_status"] = "passed"
        c["witnesses"] = ev["witnesses"]
        c["witness_status_reason"] = ev["witness_status_reason"]
        f.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
        report["promoted"].append(c.get("id"))
    return report


if __name__ == "__main__":  # python -m api.witness_authorship [--apply]
    if "--apply" in sys.argv[1:]:
        print(json.dumps(apply_gate(), indent=2))
    else:
        r = survey()
        print(json.dumps({k: v for k, v in r.items() if k != "cards"}, indent=2))
        for c in r["cards"]:
            print(f"  {c['id']}  anchors={c['anchor_count']}  {c['status']}  | {c['title']}")
