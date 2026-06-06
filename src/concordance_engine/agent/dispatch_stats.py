"""dispatch_stats.py — the oracle-dependence scoreboard.

Records, per dispatched claim, whether the engine routed it DETERMINISTICALLY
(a runtime NL->domain rule matched — no LLM/oracle call) or via the ORACLE
(the LLM classifier extracted the domain + spec).

The oracle-dependence ratio = oracle-served / total dispatches. As runtime
rules accumulate from closed build-queue gaps, this ratio FALLS — the
measurable proof of the project's computing thesis: the engine's dependence on
the statistical model shrinks with use, the inverse of the scaling paradigm.

This counts per verifier-DISPATCH (one per claim that reaches a verifier), not
per raw oracle API call — an honest "how much of what we verify still needs the
model" signal. Append-only daily JSONL: cheap, concurrency-safe, and lets the
endpoint show a trend. Recording is best-effort and never raises into the hot
dispatch path.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

_DIR = Path(os.environ.get(
    "DISPATCH_STATS_DIR",
    str(Path(__file__).resolve().parents[3] / "data" / "agent" / "dispatch"),
))
_LOCK = threading.Lock()


def record(domain: str, origin: str) -> None:
    """Append one dispatch event. Best-effort; never raises."""
    try:
        norm = "deterministic" if origin in ("rule", "deterministic") else "oracle"
        now = datetime.now(timezone.utc)
        line = json.dumps({
            "ts": now.isoformat(),
            "domain": (domain or "")[:40],
            "origin": norm,
        })
        _DIR.mkdir(parents=True, exist_ok=True)
        fp = _DIR / f"dispatch-{now.strftime('%Y%m%d')}.jsonl"
        with _LOCK:
            with fp.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        pass


def _empty() -> dict:
    return {"total": 0, "oracle": 0, "deterministic": 0,
            "oracle_dependence_ratio": None, "deterministic_ratio": None,
            "by_day": {}, "by_domain": {}, "days": 0}


def summary(days: int = 30) -> dict:
    """Aggregate the most recent `days` of dispatch events into the ratio."""
    total = oracle = deterministic = 0
    by_day: dict = {}
    by_domain: dict = {}
    try:
        if not _DIR.exists():
            return _empty()
        files = sorted(_DIR.glob("dispatch-*.jsonl"))[-days:]
        for fp in files:
            day = fp.stem.replace("dispatch-", "")
            d = by_day.setdefault(day, {"total": 0, "oracle": 0, "deterministic": 0})
            for ln in fp.read_text(encoding="utf-8", errors="replace").splitlines():
                ln = ln.strip()
                if not ln:
                    continue
                try:
                    ev = json.loads(ln)
                except Exception:
                    continue
                origin = ev.get("origin")
                dom = ev.get("domain") or "?"
                bd = by_domain.setdefault(dom, {"total": 0, "oracle": 0, "deterministic": 0})
                total += 1
                d["total"] += 1
                bd["total"] += 1
                if origin == "deterministic":
                    deterministic += 1
                    d["deterministic"] += 1
                    bd["deterministic"] += 1
                else:
                    oracle += 1
                    d["oracle"] += 1
                    bd["oracle"] += 1
    except Exception:
        return _empty()
    ratio = (oracle / total) if total else None
    det = (deterministic / total) if total else None
    return {
        "total": total,
        "oracle": oracle,
        "deterministic": deterministic,
        "oracle_dependence_ratio": round(ratio, 4) if ratio is not None else None,
        "deterministic_ratio": round(det, 4) if det is not None else None,
        "by_day": dict(sorted(by_day.items())),
        "by_domain": by_domain,
        "days": days,
    }
