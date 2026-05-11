"""Misalignment review module.

When the engine returns a non-CONCORDANT verdict, that information is
captured here. The operator reviews each entry and decides whether it
is:

  1. ARCHIVE — the user's claim was actually wrong; the engine
     correctly didn't confirm. Nothing to do.
  2. PROMOTE — the engine couldn't verify because there's a gap in
     coverage. The entry is promoted to data/build_queue/queue.jsonl
     with the operator's stated math chain.
  3. BUG — the engine SHOULD have been able to verify but a verifier
     misbehaved. Flagged for fix.

Substrate:
  data/misalignments/log.jsonl    — append-only stream of every
                                    non-CONCORDANT verdict
  data/misalignments/state.json   — per-id review status
  data/build_queue/queue.jsonl    — operator-promoted gaps
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_DATA_DIR  = Path(__file__).parent.parent / "data" / "misalignments"
_BUILD_DIR = Path(__file__).parent.parent / "data" / "build_queue"
_DATA_DIR.mkdir(parents=True, exist_ok=True)
_BUILD_DIR.mkdir(parents=True, exist_ok=True)

_LOG_FILE   = _DATA_DIR / "log.jsonl"
_STATE_FILE = _DATA_DIR / "state.json"
_QUEUE_FILE = _BUILD_DIR / "queue.jsonl"


# ── Logging ─────────────────────────────────────────────────────────────

_LOG_VERDICTS = {"DISCORDANT", "MIXED", "OUT_OF_SCOPE", "QUARANTINE", "ERROR"}


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def _normalize_domain_results(results: List[Any]) -> List[Dict[str, Any]]:
    """Strip the heavy fields from each domain result so the log stays
    compact. Keep the verdict, detail, and spec keys (no payloads)."""
    out: List[Dict[str, Any]] = []
    for r in results or []:
        if not isinstance(r, dict):
            continue
        out.append({
            "domain":      r.get("domain", ""),
            "verdict":     r.get("verdict", ""),
            "detail":      (r.get("detail") or "")[:200],
            "spec_keys":   sorted(list((r.get("spec") or {}).keys()))[:20],
        })
    return out


def log_misalignment(
    *,
    claim: str,
    composite_verdict: str,
    domain_results: Optional[List[Any]] = None,
    atomic_claims: Optional[List[str]] = None,
    quarantined_claims: Optional[List[str]] = None,
    source: str = "polymathic",
    ip_prefix: str = "",
) -> Optional[str]:
    """Append one non-CONCORDANT verdict to the misalignment log.
    Returns the id of the logged entry, or None if the verdict didn't
    warrant logging (i.e. CONCORDANT or unknown)."""
    verdict = (composite_verdict or "").upper()
    if verdict not in _LOG_VERDICTS:
        return None
    text = (claim or "").strip()
    if not text:
        return None
    now = int(time.time())
    record = {
        "id": "mis-" + _short_hash(text + str(now)),
        "logged_at": now,
        "logged_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "source": source,
        "ip_prefix": ip_prefix or "",
        "claim": text[:4000],
        "composite_verdict": verdict,
        "domain_results": _normalize_domain_results(domain_results or []),
        "atomic_claims": [c for c in (atomic_claims or []) if c][:20],
        "quarantined_claims": [c for c in (quarantined_claims or []) if c][:20],
        "review_status": "pending",
    }
    try:
        with _LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        return None
    return record["id"]


# ── Read / state ────────────────────────────────────────────────────────

def _load_state() -> Dict[str, Any]:
    try:
        if _STATE_FILE.exists():
            s = json.loads(_STATE_FILE.read_text("utf-8"))
            s.setdefault("decisions", {})
            return s
    except Exception:
        pass
    return {"decisions": {}}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        _STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass


def _read_log(limit: int = 200) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not _LOG_FILE.exists():
        return out
    try:
        for line in _LOG_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return out
    out.sort(key=lambda r: r.get("logged_at", 0), reverse=True)
    if limit:
        out = out[:limit]
    return out


def list_misalignments(limit: int = 200) -> Dict[str, Any]:
    """Operator-facing list with merged decision state."""
    items = _read_log(limit=limit)
    state = _load_state()
    decisions = state.get("decisions", {}) or {}
    pending = 0
    archived = 0
    promoted = 0
    bugs = 0
    for it in items:
        d = decisions.get(it.get("id"))
        if d:
            it["review_status"] = d.get("status", "pending")
            it["review_note"] = d.get("note", "")
            it["reviewed_at_iso"] = d.get("reviewed_at_iso", "")
        if it["review_status"] == "pending":
            pending += 1
        elif it["review_status"] == "archived":
            archived += 1
        elif it["review_status"] == "promoted":
            promoted += 1
        elif it["review_status"] == "bug":
            bugs += 1
    return {
        "total": len(items),
        "pending": pending,
        "archived": archived,
        "promoted": promoted,
        "bugs": bugs,
        "items": items,
    }


# ── Review actions ──────────────────────────────────────────────────────

def _get_misalignment(item_id: str) -> Optional[Dict[str, Any]]:
    for rec in _read_log(limit=10000):
        if rec.get("id") == item_id:
            return rec
    return None


def _append_to_build_queue(*, item_id: str, claim_pattern: str,
                           example_claim: str, needed_math: str,
                           needed_substrate: str, why_not_now: str) -> Dict[str, Any]:
    """Add an entry to the build queue, derived from a misalignment."""
    now_iso = time.strftime("%Y-%m-%d", time.gmtime())
    entry = {
        "id": "bq-" + _short_hash(example_claim + str(int(time.time()))),
        "claim_pattern": claim_pattern,
        "example_claim": example_claim,
        "needed_math": needed_math,
        "needed_substrate": needed_substrate,
        "why_not_now": why_not_now,
        "status": "open",
        "added_at": now_iso,
        "promoted_from_misalignment": item_id,
    }
    try:
        with _QUEUE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise RuntimeError(f"could not append to build queue: {exc}")
    return entry


def review(
    *,
    item_id: str,
    status: str,
    note: str = "",
    claim_pattern: str = "",
    needed_math: str = "",
    needed_substrate: str = "",
) -> Dict[str, Any]:
    """Operator decision on a misalignment.

    status:
      - 'archive'  — the user was wrong; engine correctly didn't confirm
      - 'promote'  — gap in the tool; append to build queue
                     (claim_pattern + needed_math are required)
      - 'bug'      — engine should have confirmed but a verifier misbehaved
      - 'pending'  — restore to unreviewed (undo)
    """
    iid = (item_id or "").strip()
    s = (status or "").strip().lower()
    if not iid:
        raise ValueError("item_id required")
    if s not in ("archive", "promote", "bug", "pending"):
        raise ValueError("status must be archive|promote|bug|pending")
    rec = _get_misalignment(iid)
    if not rec:
        raise LookupError("misalignment not found")

    now = int(time.time())
    state = _load_state()
    decisions = state.setdefault("decisions", {})

    result: Dict[str, Any] = {"id": iid, "status": s}

    if s == "promote":
        if not claim_pattern.strip() or not needed_math.strip():
            raise ValueError("claim_pattern and needed_math required for promote")
        bq = _append_to_build_queue(
            item_id=iid,
            claim_pattern=claim_pattern.strip()[:500],
            example_claim=rec.get("claim", "")[:500],
            needed_math=needed_math.strip()[:2000],
            needed_substrate=needed_substrate.strip()[:500],
            why_not_now=(note.strip() or "Promoted from misalignment review.")[:500],
        )
        result["build_queue_id"] = bq["id"]

    if s == "pending":
        # Undo: remove the decision entirely
        decisions.pop(iid, None)
    else:
        decisions[iid] = {
            "status": "archived" if s == "archive"
                      else "promoted" if s == "promote"
                      else "bug",
            "note": note.strip()[:1000],
            "reviewed_at": now,
            "reviewed_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        }
    state["decisions"] = decisions
    _save_state(state)
    return result
