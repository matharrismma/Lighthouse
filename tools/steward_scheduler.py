#!/usr/bin/env python3
"""steward_scheduler.py — the Steward's resource governor.

Runs frequently (every ~15 min). Each tick it reads two signals — current
LOAD (are real users/agents here now?) and BUDGET (what's left of the cap) —
and decides how much background work to dispatch, faithfully:

  BUSY (live demand)      -> pause background; reserve everything for use
  MODERATE               -> only FREE background work (connections, sorting)
  IDLE + budget headroom -> full background work, within a daily reserve

Background workers:
  - Scribe  : creates cards when not in use (connection discovery [free];
              gated card generation on uncovered topics [metered, gate-filtered])
  - Steward : surfaces tool/skill gaps to build (capacity proposals [free])

Reserve discipline (the "conserve plenty for use" rule):
  - NH_BG_DAILY_USD      daily ceiling for background spend         (default 10)
  - NH_RESERVE_FLOOR_USD keep this much of the monthly cap for live (default 100)
  - load-gating          live traffic always wins; background yields

Every decision is logged as a Steward training pair (data/training_corpus/
offices/steward.jsonl) — the body mints the data for its own resource-manager
model as it runs.

Usage:
    python tools/steward_scheduler.py            # one governed tick
    python tools/steward_scheduler.py --dry-run  # decide + log, no work, no spend
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
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
PYTHON = sys.executable
SPEND_DIR = REPO_ROOT / "data" / "spend"
VISITS_DIR = REPO_ROOT / "data" / "visits"
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
SCHED_LOG = SPEND_DIR / "steward_log.jsonl"

BG_DAILY_USD = float(os.environ.get("NH_BG_DAILY_USD", "10") or 10)
RESERVE_FLOOR_USD = float(os.environ.get("NH_RESERVE_FLOOR_USD", "100") or 100)
MONTH_CAP_USD = float(os.environ.get("NH_MONTHLY_BUDGET_USD", "500") or 500)
# load thresholds: requests in the last 15 min (operator + dashboard already excluded)
IDLE_MAX = int(os.environ.get("NH_LOAD_IDLE_MAX", "20") or 20)
BUSY_MIN = int(os.environ.get("NH_LOAD_BUSY_MIN", "80") or 80)


def _now():
    return datetime.now(timezone.utc)


def measure_load() -> tuple:
    """(label, count) — requests in the last 15 minutes from the visit log."""
    import time as _t
    cutoff = _t.time() - 15 * 60
    n = 0
    f = VISITS_DIR / f"access-{_now().strftime('%Y%m%d')}.jsonl"
    if f.exists():
        for ln in f.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
            except Exception:
                continue
            if (o.get("ts", 0) or 0) >= cutoff:
                n += 1
    label = "idle" if n <= IDLE_MAX else ("busy" if n >= BUSY_MIN else "moderate")
    return label, n


def _spend(month_only=True, source_prefix="") -> float:
    led = SPEND_DIR / "ledger.jsonl"
    if not led.exists():
        return 0.0
    month = _now().strftime("%Y-%m")
    day = _now().strftime("%Y-%m-%d")
    total = 0.0
    for ln in led.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        if o.get("month") != month:
            continue
        if source_prefix and not str(o.get("source", "")).startswith(source_prefix):
            continue
        if not month_only and not (o.get("ts", "")[:10] == day):
            continue
        total += float(o.get("usd", 0) or 0)
    return round(total, 6)


def _today_bg_spent() -> float:
    return _spend(month_only=False, source_prefix="bg_")


def _record(source: str, usd: float) -> None:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    with (SPEND_DIR / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": _now().isoformat(), "month": _now().strftime("%Y-%m"),
                            "source": source, "usd": round(float(usd), 6)}) + "\n")


def _log_steward(decision: dict) -> None:
    SPEND_DIR.mkdir(parents=True, exist_ok=True)
    decision = {"ts": _now().isoformat(), **decision}
    with SCHED_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(decision, ensure_ascii=False) + "\n")
    # also a Steward training pair: state -> resource decision
    try:
        OFFICE_DIR.mkdir(parents=True, exist_ok=True)
        pair = {
            "schema": "narrowhighway.office_pair/1", "office": "steward",
            "prompt": json.dumps({"load": decision.get("load"), "load_n": decision.get("load_n"),
                                  "month_remaining": decision.get("month_remaining"),
                                  "bg_today": decision.get("bg_today")}, ensure_ascii=False),
            "completion": json.dumps({"action": decision.get("action"),
                                      "ran": decision.get("ran", []),
                                      "reason": decision.get("reason")}, ensure_ascii=False),
            "at": _now().isoformat(),
        }
        with (OFFICE_DIR / "steward.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(pair, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _run(argv, est=0.0):
    """Run a background tool; return (ok, tail)."""
    try:
        p = subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True,
                           text=True, timeout=600)
        tail = (p.stdout or "").strip().splitlines()[-1:] or [""]
        return (p.returncode == 0, tail[0][:160])
    except Exception as e:
        return (False, str(e)[:160])


def main() -> int:
    ap = argparse.ArgumentParser(description="One governed Steward tick")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load, load_n = measure_load()
    month_spent = _spend()
    month_remaining = round(MONTH_CAP_USD - month_spent, 2)
    bg_today = _today_bg_spent()

    decision = {"load": load, "load_n": load_n, "month_remaining": month_remaining,
                "bg_today": round(bg_today, 4), "ran": []}

    # ── The faithful decision ──
    if load == "busy":
        decision.update(action="yield", reason="live demand — reserving everything for use")
    elif month_remaining <= RESERVE_FLOOR_USD:
        decision.update(action="yield", reason=f"protecting ${RESERVE_FLOOR_USD} live reserve floor")
    else:
        # Always-free work (connections + capacity) when not busy:
        free_ok = True
        # Metered card-gen only when truly idle AND under the daily background budget:
        metered_ok = (load == "idle") and (bg_today < BG_DAILY_USD) and not args.dry_run
        decision["action"] = "work"
        decision["reason"] = f"{load}: free work" + (" + a fresh card" if metered_ok else " only")

        if not args.dry_run:
            # Steward (free): tend the airlock — triage what's held in quarantine,
            # recover what a rule now matches, hint the rest. Verification gate.
            ok, t = _run([PYTHON, "tools/steward_airlock.py"])
            decision["ran"].append({"worker": "steward", "task": "tend_airlock", "ok": ok})
            # Steward (free): find connections across domains
            ok, t = _run([PYTHON, "tools/suggest_connections.py", "--apply",
                          "--limit-cards", "400", "--k", "4"])
            decision["ran"].append({"worker": "steward", "task": "find_connections", "ok": ok})
            # Steward (free): keep the Codex in step with the connections just
            # written. Debounced by this cadence — rebuilds the four indexes
            # only when a source is newer than the compiled output, else no-op.
            ok, t = _run([PYTHON, "-m", "api.codex", "--if-stale"])
            decision["ran"].append({"worker": "steward", "task": "codex_refresh", "ok": ok, "detail": t})
            # Steward (free): craft tools — surface skill/tool gaps from real demand
            ok, t = _run([PYTHON, "tools/skill_capacity.py"])
            decision["ran"].append({"worker": "steward", "task": "craft_tools", "ok": ok})
            # Scribe's reach to the outside world (metered, cheap Haiku): her
            # scouts find seeds of knowledge across the domains. Seeds land in
            # the journal; the Steward's airlock then verifies them through the
            # gates — only what survives is kept. Scribe reaches out; Steward keeps.
            if metered_ok:
                ok, t = _run([PYTHON, "tools/seed_generator.py", "--all",
                              "--count", "1", "--delay", "0.2"])
                est = 0.06
                _record("bg_scout", est)
                decision["ran"].append({"worker": "scribe", "task": "scout_seeds",
                                        "ok": ok, "spent_est": est})

    _log_steward(decision)
    print(f"[steward] load={load}({load_n}/15min) month_left=${month_remaining} "
          f"bg_today=${decision['bg_today']} -> {decision['action']}: {decision['reason']}")
    for r in decision["ran"]:
        print(f"   · {r['worker']}/{r['task']} ok={r['ok']}" +
              (f" ~${r.get('spent_est')}" if r.get('spent_est') else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
