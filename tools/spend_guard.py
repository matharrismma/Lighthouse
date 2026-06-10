#!/usr/bin/env python3
"""spend_guard.py — persistent monthly Anthropic spend ceiling.

The gathering pipeline (devotional, almanac, corpus, any future generator)
calls into this before spending, and records spend after. It enforces ONE
hard rule: total Anthropic spend in a calendar month never exceeds the cap.

Cap source (first wins):
    1. env  NH_MONTHLY_BUDGET_USD
    2. file data/spend/budget.txt  (a single number)
    3. default 500.00

Ledger:
    data/spend/ledger.jsonl   — append-only, one JSON object per spend event:
        {"ts": "...", "month": "2026-05", "source": "devotional", "usd": 0.024}

Usage (CLI):
    python tools/spend_guard.py status
        -> prints month, spent, cap, remaining; exit 0

    python tools/spend_guard.py check --estimate 0.05
        -> exit 0 if (month_to_date + estimate) <= cap, else exit 3

    python tools/spend_guard.py record --source devotional --usd 0.024
        -> append a spend event; exit 0

Used as a module:
    from spend_guard import month_to_date, remaining, can_spend, record
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent)
)).resolve()
SPEND_DIR = REPO_ROOT / "data" / "spend"
LEDGER = SPEND_DIR / "ledger.jsonl"
BUDGET_FILE = SPEND_DIR / "budget.txt"
DEFAULT_CAP = 500.00


def _now():
    return datetime.now(timezone.utc)


def current_month() -> str:
    return _now().strftime("%Y-%m")


def cap() -> float:
    env = os.environ.get("NH_MONTHLY_BUDGET_USD", "").strip()
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    if BUDGET_FILE.exists():
        try:
            return float(BUDGET_FILE.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            pass
    return DEFAULT_CAP


def month_to_date(month: str | None = None) -> float:
    month = month or current_month()
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("month") == month:
            try:
                total += float(obj.get("usd", 0) or 0)
            except (TypeError, ValueError):
                continue
    return round(total, 6)


def remaining() -> float:
    return round(cap() - month_to_date(), 6)


def can_spend(estimate: float) -> bool:
    """True if spending `estimate` more this month stays within the cap."""
    return (month_to_date() + max(0.0, estimate)) <= cap()


def record(source: str, usd: float) -> None:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": _now().isoformat(),
        "month": current_month(),
        "source": source,
        "usd": round(float(usd), 6),
    }
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _status_dict() -> dict:
    m = current_month()
    spent = month_to_date(m)
    c = cap()
    return {
        "month": m,
        "cap_usd": round(c, 2),
        "spent_usd": round(spent, 4),
        "remaining_usd": round(c - spent, 4),
        "ledger": str(LEDGER.relative_to(REPO_ROOT)).replace("\\", "/"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Monthly Anthropic spend guard")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Print current month spend status")

    chk = sub.add_parser("check", help="Exit 0 if estimate fits in budget, else 3")
    chk.add_argument("--estimate", type=float, default=0.0,
                     help="Additional USD about to be spent")

    rec = sub.add_parser("record", help="Record a spend event")
    rec.add_argument("--source", required=True, help="What spent (e.g. devotional)")
    rec.add_argument("--usd", type=float, required=True, help="USD spent")

    args = ap.parse_args()

    if args.cmd == "status":
        print(json.dumps(_status_dict(), indent=2))
        return 0

    if args.cmd == "check":
        if can_spend(args.estimate):
            st = _status_dict()
            print(f"OK · month={st['month']} spent=${st['spent_usd']} "
                  f"+est=${args.estimate} cap=${st['cap_usd']} "
                  f"remaining=${st['remaining_usd']}")
            return 0
        st = _status_dict()
        print(f"OVER BUDGET · month={st['month']} spent=${st['spent_usd']} "
              f"+est=${args.estimate} would exceed cap=${st['cap_usd']}",
              file=sys.stderr)
        return 3

    if args.cmd == "record":
        record(args.source, args.usd)
        st = _status_dict()
        print(f"recorded ${args.usd} ({args.source}) · "
              f"month-to-date=${st['spent_usd']} / ${st['cap_usd']}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
