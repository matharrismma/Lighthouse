#!/usr/bin/env python3
"""gather_cycle.py — one pass of the substrate-gathering pipeline,
spend-guarded by tools/spend_guard.py (hard monthly cap).

This is what runs on a timer to keep the substrate growing automatically.
Each generator is a small entry with a conservative cost estimate. Before
running one, we ask the spend guard whether the estimate fits inside the
month's remaining budget. If not, we skip it (and log why). After a run,
we record the spend.

The estimates are intentionally conservative (max plausible cost), so the
hard cap is never breached — at worst we stop a little early.

Generators run here are LIGHT + API-based (text). Heavy PD media
acquisition stays on the storage box (Windows), not here.

Enable/disable generators with env flags (default shown):
    NH_GATHER_DEVOTIONAL=1     daily devotion (zero-input, alignment-gated)
    NH_GATHER_ALMANAC=0        almanac propose-only (needs topics; off by default)

Usage:
    python tools/gather_cycle.py              # run a real pass
    python tools/gather_cycle.py --dry-run    # show what it WOULD do, no spend
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent)
)).resolve()
PYTHON = sys.executable
SPEND_DIR = REPO_ROOT / "data" / "spend"
GATHER_LOG = SPEND_DIR / "gather_log.jsonl"

sys.path.insert(0, str(REPO_ROOT / "tools"))
import spend_guard  # noqa: E402


def _env_on(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


# Each generator: (key, env-flag, conservative cost estimate USD, argv)
# estimate=0.0 means free (deterministic, no API) — always runs when enabled.
GENERATORS = [
    {
        "key": "connections",
        "flag": "NH_GATHER_CONNECTIONS",
        "default": "1",
        "estimate": 0.0,   # deterministic — token overlap + authority tiers, no API
        "argv": [PYTHON, "tools/suggest_connections.py", "--apply",
                 "--limit-cards", "800", "--k", "4"],
        "note": "cross-domain connection discovery -> review queue (free)",
    },
    {
        "key": "capacity",
        "flag": "NH_GATHER_CAPACITY",
        "default": "1",
        "estimate": 0.0,   # deterministic — demand vs supply analysis, no API
        "argv": [PYTHON, "tools/skill_capacity.py"],
        "note": "build-capacity-on-need: proposes skills where demand is uncovered (free)",
    },
    {
        "key": "devotional",
        "flag": "NH_GATHER_DEVOTIONAL",
        "default": "1",
        "estimate": 0.05,   # Sonnet 4.6, ~1500 out tokens; real ~$0.025
        "argv": [PYTHON, "tools/generate_devotional.py"],
        "note": "daily devotion (zero-input, alignment-gated)",
    },
    {
        "key": "almanac",
        "flag": "NH_GATHER_ALMANAC",
        "default": "0",      # off by default — needs topics + operator review
        "estimate": 0.08,
        "argv": [PYTHON, "tools/generate_almanac.py", "--propose-only"],
        "note": "almanac propose-only (operator confirms in /keep)",
    },
]


def _log(entry: dict) -> None:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **entry}
    with GATHER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  [{entry.get('result','?')}] {entry.get('generator','?')}: {entry.get('detail','')}")


def run_generator(gen: dict, dry_run: bool) -> None:
    key, est = gen["key"], gen["estimate"]
    if not _env_on(gen["flag"], gen["default"]):
        _log({"generator": key, "result": "disabled", "detail": f"{gen['flag']} not set"})
        return
    if not spend_guard.can_spend(est):
        _log({"generator": key, "result": "skipped_budget",
              "detail": f"est ${est} would exceed cap; "
                        f"month-to-date ${spend_guard.month_to_date()} / ${spend_guard.cap()}"})
        return
    if dry_run:
        _log({"generator": key, "result": "would_run",
              "detail": f"{' '.join(gen['argv'])} (est ${est})"})
        return

    # Run it
    try:
        proc = subprocess.run(
            gen["argv"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        _log({"generator": key, "result": "timeout", "detail": "exceeded 600s"})
        return
    except Exception as e:
        _log({"generator": key, "result": "error", "detail": str(e)[:200]})
        return

    if proc.returncode == 0:
        # Record the conservative estimate as spend (scripts don't return
        # actual cost yet; estimate keeps us safely under the hard cap).
        spend_guard.record(key, est)
        tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
        _log({"generator": key, "result": "ran", "spent_est_usd": est,
              "detail": tail[0][:200]})
    else:
        err = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or [""]
        _log({"generator": key, "result": "failed", "rc": proc.returncode,
              "detail": err[0][:200]})


def main() -> int:
    ap = argparse.ArgumentParser(description="One spend-guarded gathering pass")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would run; no spend, no API calls")
    args = ap.parse_args()

    st = spend_guard._status_dict()
    print(f"[gather] month={st['month']} spent=${st['spent_usd']} "
          f"cap=${st['cap_usd']} remaining=${st['remaining_usd']} "
          f"{'(DRY RUN)' if args.dry_run else ''}")

    if spend_guard.remaining() <= 0:
        _log({"generator": "(all)", "result": "halted_budget",
              "detail": f"cap ${st['cap_usd']} reached for {st['month']}"})
        print("[gather] monthly cap reached — nothing run.")
        return 0

    for gen in GENERATORS:
        run_generator(gen, args.dry_run)

    st2 = spend_guard._status_dict()
    print(f"[gather] done. month-to-date now ${st2['spent_usd']} / ${st2['cap_usd']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
