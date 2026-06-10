#!/usr/bin/env python3
"""steward_airlock.py — the Steward tends the airlock.

Part of the Steward's office: manage the airlock/quarantine. Reads the
quarantined claims (decomposed but unverifiable — "not wrong, not confirmed"),
runs them through the Quarantine Keeper's ultra-low-power triage
(rule recovery + nearest-domain hints + clustering — deterministic, no LLM,
free), and records the manifest for operator review / re-dispatch.

The keeper organizes the airlock; it does not force resolution. Claims that
recover (a dispatch rule now matches) are flagged for admission; the rest
stay held with a nearest-domain hint until a rule is added or a human triages.

Free + deterministic — safe for the Steward to run every working tick.

Usage:
    python tools/steward_airlock.py            # tend the airlock, write manifest
    python tools/steward_airlock.py --dry-run  # report only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
sys.path.insert(0, str(REPO_ROOT / "src"))

QUARANTINE_FILE = REPO_ROOT / "data" / "quarantine" / "flushed.jsonl"
MANIFEST_OUT = REPO_ROOT / "data" / "quarantine" / "airlock_manifest.json"


def _load_claims() -> list:
    """Extract claim strings from the quarantine, whatever the entry shape."""
    claims = []
    if not QUARANTINE_FILE.exists():
        return claims
    for ln in QUARANTINE_FILE.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            # a bare string line
            claims.append(ln)
            continue
        if isinstance(o, str):
            claims.append(o)
        elif isinstance(o, dict):
            c = (o.get("claim") or o.get("text") or o.get("query")
                 or o.get("situation") or "")
            if c:
                claims.append(c)
    return claims


def main() -> int:
    ap = argparse.ArgumentParser(description="Steward tends the airlock")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    claims = _load_claims()
    if not claims:
        print("[airlock] empty — nothing held in quarantine.")
        return 0

    try:
        from concordance_engine.agent.quarantine_keeper import tend_quarantine
    except Exception as e:
        print(f"[airlock] keeper unavailable: {str(e)[:120]}")
        return 0

    manifest = tend_quarantine(claims)
    # QuarantineManifest -> a summary dict (defensive about its shape)
    def _attr(o, *names, default=None):
        for n in names:
            if hasattr(o, n):
                return getattr(o, n)
            if isinstance(o, dict) and n in o:
                return o[n]
        return default

    recovered = _attr(manifest, "recovered", "recovered_claims", default=[]) or []
    hints = _attr(manifest, "hints", "domain_hints", default={}) or {}
    clusters = _attr(manifest, "clusters", default=[]) or []
    rec_count = _attr(manifest, "recovery_count", default=len(recovered))

    summary = {
        "schema": "narrowhighway.airlock_manifest/1",
        "tended_at": datetime.now(timezone.utc).isoformat(),
        "held": len(claims),
        "recovered": rec_count if isinstance(rec_count, int) else len(recovered),
        "still_held": len(claims) - (rec_count if isinstance(rec_count, int) else len(recovered)),
        "domain_hints": len(hints) if hasattr(hints, "__len__") else 0,
        "clusters": len(clusters) if hasattr(clusters, "__len__") else 0,
    }

    print(f"[airlock] held={summary['held']} recovered={summary['recovered']} "
          f"still_held={summary['still_held']} clusters={summary['clusters']}")

    if not args.dry_run:
        MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                encoding="utf-8")
        print(f"[airlock] manifest -> {MANIFEST_OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
