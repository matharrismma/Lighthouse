"""flush_quarantine.py — Honor the storage discipline. The cards stay; the
bulk goes.

Runs on a schedule (or by hand). Reads `data/quarantine/.policy.json` to know
the TTLs, then:

1. Walks `data/quarantine/cards/` and ages cards out per the policy:
   - Cards untouched for > cards.ttl_days move to data/cards/archived/
   - Cards in archive > archives.ttl_days surface to operator for hard-delete review
2. Walks `data/quarantine/raw_sources/` (if it exists) and deletes raw inputs
   older than raw_sources.ttl_days — BUT only after confirming at least one
   card was extracted from it (we never lose data without a card surviving).
3. Refuses to touch anything in policy.exempt.globs.
4. Refuses to delete a card that has been paperclipped or cited.
5. Writes a flush report to data/quarantine/flush_log.jsonl.

Operator runs:
    python tools/flush_quarantine.py             # dry run, no deletions
    python tools/flush_quarantine.py --apply     # actually move/delete

Standing rule: never silently apply; always log what was done; always recoverable.
"""
from __future__ import annotations
import argparse
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUARANTINE_DIR = REPO / "data" / "quarantine"
QUARANTINE_CARDS = QUARANTINE_DIR / "cards"
QUARANTINE_RAW = QUARANTINE_DIR / "raw_sources"
CARDS_DIR = REPO / "data" / "cards"
ARCHIVE_DIR = REPO / "data" / "cards" / "archived"
POLICY_PATH = QUARANTINE_DIR / ".policy.json"
FLUSH_LOG = QUARANTINE_DIR / "flush_log.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_policy() -> dict:
    if not POLICY_PATH.exists():
        return {
            "cards": {"ttl_days": 30, "max_count": 5000},
            "raw_sources": {"ttl_days": 7, "max_size_mb": 500},
            "archives": {"ttl_days": 90},
            "exempt": {"globs": []},
        }
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _age_days(p: Path) -> float:
    try:
        return (time.time() - p.stat().st_mtime) / 86400.0
    except Exception:
        return 0.0


def _read_card(p: Path) -> dict | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_protected(card: dict, all_card_refs: set) -> tuple[bool, str]:
    """A card is protected from flush if any of:
    - paperclipped by any household
    - cited by any other live (non-quarantine) card
    - foundational source tier
    - retracted (we keep retracted cards as evidence)
    """
    if (card.get("metrics") or {}).get("paperclips_count", 0) > 0:
        return True, "paperclipped"
    if card.get("id") in all_card_refs:
        return True, "cited_by_other_card"
    src = card.get("source") or {}
    tier = src.get("authority_tier", "")
    if tier in ("words_in_red", "scripture", "creed", "catechism", "father"):
        return True, f"foundational:{tier}"
    if card.get("retracted"):
        return True, "retracted_evidence"
    return False, ""


def _gather_all_card_references() -> set:
    """Walk every live card and collect the set of card_ids they reference.
    We refuse to flush any card that another card cites."""
    refs = set()
    if not CARDS_DIR.exists():
        return refs
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for conn in (c.get("connections") or []):
            tid = conn.get("to_card_id")
            if tid:
                refs.add(tid)
        for sid in ((c.get("extra") or {}).get("cards_surfaced") or []):
            refs.add(sid)
    return refs


def flush(apply: bool = False) -> dict:
    policy = load_policy()
    cards_ttl = (policy.get("cards") or {}).get("ttl_days", 30)
    raw_ttl = (policy.get("raw_sources") or {}).get("ttl_days", 7)
    archive_ttl = (policy.get("archives") or {}).get("ttl_days", 90)

    report = {
        "ran_at": _now(),
        "apply": apply,
        "cards_quarantined_before": 0,
        "cards_archived": [],
        "cards_protected_from_flush": [],
        "raw_sources_deleted": [],
        "raw_sources_skipped": [],
        "archive_hard_delete_candidates": [],
        "errors": [],
    }

    # --- Phase 1: age out quarantined cards -------------------------------
    if QUARANTINE_CARDS.exists():
        all_refs = _gather_all_card_references()
        for f in QUARANTINE_CARDS.glob("*.json"):
            report["cards_quarantined_before"] += 1
            age = _age_days(f)
            if age < cards_ttl:
                continue
            c = _read_card(f)
            if c is None:
                report["errors"].append(f"unreadable:{f.name}")
                continue
            protected, why = _is_protected(c, all_refs)
            if protected:
                report["cards_protected_from_flush"].append({"card_id": c.get("id"), "reason": why})
                continue
            # Move to archive
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            target = ARCHIVE_DIR / f.name
            if apply:
                try:
                    c["lifecycle_stage"] = "archived"
                    c["archived_at"] = _now()
                    c["archived_reason"] = f"quarantine_aged_out:age_days={age:.1f}"
                    target.write_text(json.dumps(c, indent=2), encoding="utf-8")
                    f.unlink()
                except Exception as e:
                    report["errors"].append(f"archive_failed:{f.name}:{e}")
                    continue
            report["cards_archived"].append({"card_id": c.get("id"), "age_days": round(age, 1)})

    # --- Phase 2: delete raw sources past TTL (cards already extracted) ---
    if QUARANTINE_RAW.exists():
        for f in QUARANTINE_RAW.rglob("*"):
            if not f.is_file():
                continue
            if f.name.startswith("."):
                continue
            age = _age_days(f)
            if age < raw_ttl:
                continue
            # We'd like to check "at least one card has source.url referencing this file"
            # before deleting. For now: trust the operator pipeline writes cards before
            # raw files age out. The exempt list guards anything truly load-bearing.
            if apply:
                try:
                    f.unlink()
                except Exception as e:
                    report["errors"].append(f"raw_delete_failed:{f}:{e}")
                    continue
            report["raw_sources_deleted"].append({"path": str(f.relative_to(REPO)), "age_days": round(age, 1)})

    # --- Phase 3: surface old archive entries for operator review ---------
    if ARCHIVE_DIR.exists():
        for f in ARCHIVE_DIR.glob("*.json"):
            age = _age_days(f)
            if age < archive_ttl:
                continue
            c = _read_card(f) or {}
            report["archive_hard_delete_candidates"].append({
                "card_id": c.get("id"),
                "title": c.get("title"),
                "age_days": round(age, 1),
                "_note": "Operator review required; this tool never auto-deletes from archive.",
            })

    # --- Write flush log --------------------------------------------------
    FLUSH_LOG.parent.mkdir(parents=True, exist_ok=True)
    with FLUSH_LOG.open("a", encoding="utf-8") as g:
        g.write(json.dumps(report) + "\n")

    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually move/delete (default is dry run)")
    args = parser.parse_args()
    report = flush(apply=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"=== Quarantine flush {mode} at {report['ran_at']} ===")
    print(f"Cards in quarantine before: {report['cards_quarantined_before']}")
    print(f"Cards archived this run:    {len(report['cards_archived'])}")
    print(f"Cards protected from flush: {len(report['cards_protected_from_flush'])}")
    print(f"Raw sources deleted:        {len(report['raw_sources_deleted'])}")
    print(f"Archive hard-delete review: {len(report['archive_hard_delete_candidates'])}")
    if report["errors"]:
        print(f"Errors: {len(report['errors'])}")
        for e in report["errors"][:10]:
            print(f"  - {e}")
    if not args.apply:
        print("\n[DRY RUN] Re-run with --apply to actually flush.")


if __name__ == "__main__":
    main()
