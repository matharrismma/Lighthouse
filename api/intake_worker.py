"""Intake worker — provisional packet processor.

Walks data/intake/queue.jsonl. For each unprocessed item:
  1. Run polymathic synthesis on the text (claim decomposition →
     verifier fan-out → composite verdict).
  2. Run archetype recognition for pattern combination.
  3. Compose a "projection": projected verdict, axis overlaps,
     closest precedent (if any), archetype combination, suggested path.
  4. Write the projection back into the intake record so the Console
     can surface it next to the item.

The worker never moves items between lanes. The operator decides
whether to flush, accept (publish), or leave for re-processing.
Idempotent: items with polymathic_attempted = true are skipped unless
force=True.
"""

from __future__ import annotations

import json
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api import archetypes as _archetypes

_INTAKE_FILE = Path(__file__).parent.parent / "data" / "intake" / "queue.jsonl"


def _read_all() -> List[Dict[str, Any]]:
    if not _INTAKE_FILE.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with _INTAKE_FILE.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _write_all(rows: List[Dict[str, Any]]) -> None:
    tmp = _INTAKE_FILE.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(_INTAKE_FILE)


def _project_path(poly_dict: Dict[str, Any], archetype_rec: Dict[str, Any]) -> Dict[str, Any]:
    """Compose a projected path from polymathic + archetype output.

    Engine surfaces. No prescriptive verdict here — just the projection
    of where this is likely to land if it goes through the gates."""
    composite = (poly_dict or {}).get("composite_verdict") or "OUT_OF_SCOPE"
    overlaps = (poly_dict or {}).get("axis_overlaps") or []
    closest = (poly_dict or {}).get("closest_precedent") or None
    domain_results = (poly_dict or {}).get("domain_results") or []
    quarantined = (poly_dict or {}).get("quarantined_claims") or []

    confirmed = [d for d in domain_results if (d or {}).get("verdict") == "CONCORDANT"]
    mismatched = [d for d in domain_results if (d or {}).get("verdict") == "DISCORDANT"]

    combo = (archetype_rec or {}).get("combination") or {}
    cands = (archetype_rec or {}).get("candidates") or []

    # Suggested path is structural — based on composite + archetype
    # category. Pure lookup, no generation.
    suggestion = None
    if composite == "CONCORDANT":
        suggestion = "Path is clear; verifiers agree. Operator may publish as Almanac entry."
    elif composite == "DISCORDANT":
        suggestion = "All verifiers mismatch. Recommend flush unless the operator sees something the engine missed."
    elif composite == "MIXED":
        suggestion = "Verifiers split. Surface the discordant domains to the operator for closer reading."
    elif composite == "OUT_OF_SCOPE":
        suggestion = "No domain matched. Check whether a missing verifier should exist; otherwise flush."
    elif composite == "QUARANTINE":
        # All atomic claims failed to land on any verifier. Either the
        # text is non-claim-bearing (a question, a quote, a fragment)
        # or it sits in a gap the verifier catalog doesn't cover yet.
        # The archetype combination may still be informative.
        if (archetype_rec or {}).get("candidates"):
            suggestion = "No verifier accepted any atomic claim, but an archetype pattern is present. The item may be situational rather than propositional — operator decides whether to preserve as a sample or flush."
        else:
            suggestion = "No verifier accepted any atomic claim, and no archetype pattern matched. Recommend flush unless the text reveals a structural gap worth a new verifier."
    elif composite == "ERROR":
        suggestion = "Engine error during processing. Retry, or investigate the failing verifier."
    else:
        # Unknown verdict shape — surface it without prescribing.
        suggestion = f"Composite verdict '{composite}' is not in the operator playbook; manual review recommended."

    return {
        "composite_verdict": composite,
        "domains_fired": len(domain_results),
        "domains_confirmed": len(confirmed),
        "domains_mismatched": len(mismatched),
        "axis_overlaps": overlaps[:8],  # cap for storage
        "closest_precedent": closest,
        "quarantined_claims": len(quarantined),
        "archetype_combination": {
            "summary": combo.get("summary"),
            "signature": combo.get("signature"),
            "is_blend": combo.get("is_blend"),
            "top_three": [
                {"name": c.get("name"), "category": c.get("category"), "weight": c.get("weight")}
                for c in cands[:3]
            ],
        } if combo else None,
        "suggestion": suggestion,
    }


def _process_one(record: Dict[str, Any], model: str = "claude-haiku-4-5-20251001") -> Tuple[bool, Optional[str]]:
    """Mutate the record in place with a projection. Returns (ok, error)."""
    text = (record.get("text") or "").strip()
    if not text:
        record["projection_error"] = "empty text"
        record["polymathic_attempted"] = True
        return False, "empty text"

    poly_dict: Dict[str, Any] = {}
    poly_error: Optional[str] = None
    try:
        # Imported lazily because poly_agent pulls in many things.
        from concordance_engine.agent.poly_agent import run_polymathic
        rec = run_polymathic(
            situation=text,
            model=model,
            max_domains=10,
            split_threshold=5,
            stop_on_discordant=False,
        )
        poly_dict = rec.to_dict() if hasattr(rec, "to_dict") else (rec or {})
    except Exception as exc:
        poly_error = str(exc)[:300]

    # Archetype recognition is local and cheap; always run.
    archetype_rec: Dict[str, Any] = {}
    arch_error: Optional[str] = None
    try:
        archetype_rec = _archetypes.recognize(text, top_k=3)
    except Exception as exc:
        arch_error = str(exc)[:200]

    projection = _project_path(poly_dict, archetype_rec)
    if poly_error:
        projection["polymathic_error"] = poly_error
    if arch_error:
        projection["archetype_error"] = arch_error

    record["projection"] = projection
    record["polymathic_attempted"] = True
    record["processed_at"] = int(time.time())
    record["processed_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return (poly_error is None), poly_error


def process_pending(max_items: int = 25, force: bool = False,
                    model: str = "claude-haiku-4-5-20251001",
                    only_id: Optional[str] = None) -> Dict[str, Any]:
    """Walk intake, process unprocessed items.

    max_items: cap per invocation so a runaway queue can't lock the server.
    force: re-process items already processed (refresh projection).
    only_id: process a single item by id; ignores max_items.
    """
    rows = _read_all()
    if not rows:
        return {"processed": 0, "skipped": 0, "errors": 0, "total": 0}

    processed = 0
    skipped = 0
    errors = 0
    errs: List[Dict[str, Any]] = []

    for rec in rows:
        if only_id is not None and rec.get("id") != only_id:
            skipped += 1
            continue
        if (not only_id) and processed >= max_items:
            skipped += 1
            continue
        if rec.get("polymathic_attempted") and not force and not only_id:
            skipped += 1
            continue
        ok, err = _process_one(rec, model=model)
        processed += 1
        if not ok:
            errors += 1
            errs.append({"id": rec.get("id"), "error": err})

    # Persist mutations atomically.
    _write_all(rows)

    return {
        "processed": processed,
        "skipped": skipped,
        "errors": errors,
        "total": len(rows),
        "error_details": errs[:5],
    }


def get_one(item_id: str) -> Optional[Dict[str, Any]]:
    for rec in _read_all():
        if rec.get("id") == item_id:
            return rec
    return None
