#!/usr/bin/env python3
"""geo_enrich.py — batch-process pending IPs into the country cache.

The access middleware does a CACHE-ONLY IP -> country lookup at request time
(never blocks). On a cache miss, it appends the raw IP to a pending file. This
tool reads the pending file, batches the unique IPs through ip-api.com (free
tier, 100/batch, ~45/min), updates the cache file, and clears the pending file.

Run via systemd timer (every ~10 min is plenty), then restart the engine to
pick up the new cache. Raw IPs are NEVER stored in visit records — only the
resolved country code is, by the middleware on subsequent requests.

Usage:
    python tools/geo_enrich.py
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
from urllib.request import Request, urlopen

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
GEO_DIR = REPO_ROOT / "data" / "geo"
CACHE_PATH = GEO_DIR / "ip_cache.json"
PENDING_PATH = GEO_DIR / "pending.jsonl"
BATCH = 100


def load_cache():
    try:
        return json.loads(CACHE_PATH.read_text("utf-8"))
    except Exception:
        return {}


def save_cache(cache):
    GEO_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(CACHE_PATH)


def read_pending():
    if not PENDING_PATH.exists():
        return []
    ips = []
    for ln in PENDING_PATH.read_text("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
            ip = (o.get("ip") or "").strip()
            if ip:
                ips.append(ip)
        except Exception:
            continue
    return ips


def lookup_batch(ips):
    """Return {ip: {cc, city, lat, lon}} for ips via ip-api.com batch.
    Pin-grade detail — city + coords so the keep map can show points."""
    out = {}
    body = json.dumps(ips).encode("utf-8")
    try:
        req = Request(
            "http://ip-api.com/batch?fields=countryCode,city,lat,lon,query",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for entry in data:
            ip = (entry.get("query") or "").strip()
            cc = (entry.get("countryCode") or "").strip() or "??"
            if not ip:
                continue
            out[ip] = {
                "cc": cc,
                "city": (entry.get("city") or "").strip(),
                "lat": entry.get("lat"),
                "lon": entry.get("lon"),
            }
    except Exception as e:
        print(f"[geo] batch error: {str(e)[:120]}", file=sys.stderr)
    return out


def main():
    pending = read_pending()
    if not pending:
        print("[geo] nothing pending.")
        return 0
    cache = load_cache()
    unique_new = [ip for ip in set(pending) if ip not in cache]
    print(f"[geo] pending {len(pending)} ({len(unique_new)} unique uncached).")
    if not unique_new:
        # Already cached — just clear the pending file
        try:
            PENDING_PATH.unlink()
        except Exception:
            pass
        return 0
    resolved = 0
    for i in range(0, len(unique_new), BATCH):
        chunk = unique_new[i:i + BATCH]
        result = lookup_batch(chunk)
        cache.update(result)
        resolved += len(result)
        # Respect free-tier rate limit (~45/min for batch endpoint)
        if i + BATCH < len(unique_new):
            time.sleep(1.5)
    save_cache(cache)
    try:
        PENDING_PATH.unlink()
    except Exception:
        pass
    print(f"[geo] resolved {resolved} new IPs; cache now {len(cache)} entries.")
    print("[geo] restart nh-engine to load the new cache into the middleware.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
