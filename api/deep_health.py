"""deep_health.py — /health/deep — single-URL summary of every subsystem.

The standard /health is a liveness probe (does the engine respond?). This
one is a readiness/operational probe: does the engine ALSO have all its
substrate, all its caches primed, all its broadcast surfaces live, all its
witnesses passing, no operator queue backed up.

Returns a single JSON with one OVERALL status (ok / degraded / down) plus a
per-component breakdown. Useful for:
  - operator command: `curl https://narrowhighway.com/health/deep`
  - uptime monitors (Pingdom, BetterUptime, UptimeRobot)
  - the homepage status badge (small JS widget that polls every minute)

Each component reports {status: ok|warn|fail, detail: "...", duration_ms: N}.
Overall status:
  ok      — every component "ok"
  warn    — any component "warn", no "fail"
  fail    — any component "fail" (e.g., engine import broken, no witnesses)

Cached for 60 seconds.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import APIRouter
except Exception:
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"
CHANNEL_DIR = REPO / "site" / "channels" / "narrow-highway"

_CACHE: dict = {"snapshot": None, "checked_at": 0.0}
_CACHE_TTL = 60.0
_LOCK = threading.Lock()


def _check_substrate() -> Dict[str, Any]:
    t = time.perf_counter()
    if not CARDS_DIR.exists():
        return {"status": "fail", "detail": "cards directory missing", "duration_ms": 0}
    try:
        count = sum(1 for _ in CARDS_DIR.glob("*.json"))
    except Exception as e:
        return {"status": "fail", "detail": f"glob failed: {e}", "duration_ms": 0}
    dur = (time.perf_counter() - t) * 1000
    if count == 0:
        return {"status": "fail", "detail": "no cards on disk", "duration_ms": dur}
    if count < 1000:
        return {"status": "warn", "detail": f"only {count} cards", "duration_ms": dur}
    return {"status": "ok", "detail": f"{count:,} cards", "duration_ms": dur}


def _check_witness_gate() -> Dict[str, Any]:
    t = time.perf_counter()
    try:
        from api import witnesses
        snap = witnesses._get_snapshot()
        total = snap.get("total_cards", 0)
        by_status = snap.get("by_status", {})
        passed = by_status.get("passed", 0)
        missing = snap.get("missing_count", 0)
        dur = (time.perf_counter() - t) * 1000
        if total == 0:
            return {"status": "fail", "detail": "no cards evaluated", "duration_ms": dur}
        pass_rate = passed / total if total else 0
        if pass_rate >= 0.95:
            return {"status": "ok",
                    "detail": f"{passed:,}/{total:,} passed ({pass_rate:.1%}), {missing} need attention",
                    "duration_ms": dur}
        if pass_rate >= 0.80:
            return {"status": "warn",
                    "detail": f"{passed:,}/{total:,} passed ({pass_rate:.1%})",
                    "duration_ms": dur}
        return {"status": "fail",
                "detail": f"only {pass_rate:.1%} cards witnessed",
                "duration_ms": dur}
    except Exception as e:
        return {"status": "fail", "detail": f"witness gate error: {e}", "duration_ms": (time.perf_counter()-t)*1000}


def _check_caches() -> Dict[str, Any]:
    t = time.perf_counter()
    results = {}
    for mod_name in ("atlas", "daily_card", "promotion", "witnesses", "agent_daily", "feed_walks"):
        try:
            mod = __import__(f"api.{mod_name}", fromlist=[mod_name])
            if hasattr(mod, "warm_cache"):
                # Don't actually trigger warm — just probe state
                if mod_name == "atlas":
                    cache = getattr(mod, "_WALK_CACHE", None)
                    ready = bool(cache and cache.get("walks") is not None)
                elif mod_name == "daily_card":
                    cache = getattr(mod, "_POOL_CACHE", None)
                    ready = bool(cache and cache.get("pool") is not None)
                elif mod_name == "promotion":
                    cache = getattr(mod, "_HEALTH_CACHE", None)
                    ready = bool(cache and cache.get("snapshot") is not None)
                elif mod_name == "witnesses":
                    cache = getattr(mod, "_CACHE", None)
                    ready = bool(cache and cache.get("snapshot") is not None)
                elif mod_name == "agent_daily":
                    cache = getattr(mod, "_CACHE", None)
                    ready = bool(cache and cache.get("snapshot") is not None)
                elif mod_name == "feed_walks":
                    cache = getattr(mod, "_CACHE", None)
                    ready = bool(cache and cache.get("xml") is not None)
                else:
                    ready = False
                results[mod_name] = "ready" if ready else "cold"
        except Exception as e:
            results[mod_name] = f"err: {e}"
    dur = (time.perf_counter() - t) * 1000
    cold = [k for k, v in results.items() if v == "cold"]
    errs = [k for k, v in results.items() if str(v).startswith("err")]
    if errs:
        return {"status": "fail", "detail": f"cache import errors: {errs}", "results": results, "duration_ms": dur}
    if len(cold) == len(results):
        return {"status": "warn", "detail": "all caches cold (warmer hasn't run)", "results": results, "duration_ms": dur}
    if cold:
        return {"status": "warn", "detail": f"{len(cold)} caches cold: {cold}", "results": results, "duration_ms": dur}
    return {"status": "ok", "detail": f"all {len(results)} caches primed", "results": results, "duration_ms": dur}


def _check_channel() -> Dict[str, Any]:
    t = time.perf_counter()
    checks = {
        "hls_playlist": CHANNEL_DIR / "hls" / "day.m3u8",
        "epg":          CHANNEL_DIR / "epg.xml",
        "mrss":         CHANNEL_DIR / "mrss.xml",
        "roku_feed":    CHANNEL_DIR / "roku_feed.json",
        "now":          CHANNEL_DIR / "now.json",
    }
    missing = []
    sizes = {}
    for name, p in checks.items():
        if not p.exists() or p.stat().st_size == 0:
            missing.append(name)
        else:
            sizes[name] = p.stat().st_size
    dur = (time.perf_counter() - t) * 1000
    if missing:
        return {"status": "warn" if len(missing) < len(checks) else "fail",
                "detail": f"channel files missing: {missing}",
                "sizes": sizes, "duration_ms": dur}
    return {"status": "ok",
            "detail": f"all {len(checks)} channel files present",
            "sizes": sizes, "duration_ms": dur}


def _check_segments() -> Dict[str, Any]:
    t = time.perf_counter()
    seg_dir = CHANNEL_DIR / "hls"
    if not seg_dir.exists():
        return {"status": "fail", "detail": "HLS dir missing", "duration_ms": 0}
    try:
        seg_count = sum(1 for _ in seg_dir.glob("seg_*.ts"))
    except Exception as e:
        return {"status": "fail", "detail": f"glob err: {e}", "duration_ms": 0}
    dur = (time.perf_counter() - t) * 1000
    if seg_count == 0:
        return {"status": "fail", "detail": "no HLS segments", "duration_ms": dur}
    if seg_count < 100:
        return {"status": "warn", "detail": f"only {seg_count} segments (~10 min)", "duration_ms": dur}
    return {"status": "ok", "detail": f"{seg_count:,} segments (~{seg_count*6/3600:.1f} hours loop)", "duration_ms": dur}


def _check_audit_log() -> Dict[str, Any]:
    t = time.perf_counter()
    log = REPO / "data" / "steward" / "audit.jsonl"
    if not log.exists():
        return {"status": "warn", "detail": "audit log not created yet", "duration_ms": 0}
    try:
        lines = sum(1 for _ in log.open("rb"))
    except Exception as e:
        return {"status": "fail", "detail": f"could not read audit: {e}", "duration_ms": 0}
    dur = (time.perf_counter() - t) * 1000
    return {"status": "ok", "detail": f"{lines} audit events", "duration_ms": dur}


def _build_snapshot() -> Dict[str, Any]:
    started = time.time()
    components = {
        "substrate":     _check_substrate(),
        "witness_gate":  _check_witness_gate(),
        "caches":        _check_caches(),
        "channel_files": _check_channel(),
        "hls_segments":  _check_segments(),
        "audit_log":     _check_audit_log(),
    }
    statuses = [c["status"] for c in components.values()]
    if "fail" in statuses:
        overall = "fail"
    elif "warn" in statuses:
        overall = "warn"
    else:
        overall = "ok"
    return {
        "status": overall,
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(started)),
        "duration_ms": int((time.time() - started) * 1000),
        "components": components,
    }


def _get_snapshot() -> Dict[str, Any]:
    now = time.time()
    if _CACHE["snapshot"] is not None and (now - _CACHE["checked_at"]) < _CACHE_TTL:
        return _CACHE["snapshot"]
    with _LOCK:
        now2 = time.time()
        if _CACHE["snapshot"] is not None and (now2 - _CACHE["checked_at"]) < _CACHE_TTL:
            return _CACHE["snapshot"]
        _CACHE["snapshot"] = _build_snapshot()
        _CACHE["checked_at"] = time.time()
    return _CACHE["snapshot"]


def warm_cache():
    try:
        s = _get_snapshot()
        return {"warmed": True, "status": s.get("status")}
    except Exception as e:
        return {"warmed": False, "error": str(e)}


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/health/deep")
    def deep_health():
        return _get_snapshot()

    return router
