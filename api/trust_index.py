"""Trust index — maps spec_hash to independent instance confirmations.

When multiple Concordance nodes independently verify the same input and reach
the same result, that convergence is trust without authority. No institution
vouched for it; the math is the voucher.

spec_hash = SHA256(canonical_json_bytes(spec)) — stable across instances
because verifiers are deterministic and canonical_json_bytes produces a
reproducible byte string.

Storage: data/trust_index/{domain}.json
    {
      "<spec_hash>": {
        "count": 3,
        "instance_ids": ["XqZklyi4o6tntmYM", "AbCdEfGhIjKlMnOp", ...],
        "first_seen": <epoch>,
        "last_seen": <epoch>,
        "summary": "CONFIRMED"
      }
    }

Override storage root via TRUST_INDEX_DIR env var.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _index_dir() -> Path:
    return Path(os.environ.get("TRUST_INDEX_DIR", "data/trust_index"))


_domain_locks: Dict[str, threading.Lock] = {}
_meta_lock = threading.Lock()


def _lock_for(domain: str) -> threading.Lock:
    with _meta_lock:
        if domain not in _domain_locks:
            _domain_locks[domain] = threading.Lock()
        return _domain_locks[domain]


def _index_path(domain: str) -> Path:
    safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in domain)
    return _index_dir() / f"{safe}.json"


def _read_index(domain: str) -> Dict[str, Any]:
    path = _index_path(domain)
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_index(domain: str, index: Dict[str, Any]) -> None:
    path = _index_path(domain)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, default=str)
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass


def spec_hash(spec: Dict[str, Any]) -> str:
    """Return SHA-256 hex digest of the canonical JSON representation of spec."""
    try:
        from concordance_engine.validate import canonical_json_bytes
        raw = canonical_json_bytes(spec)
    except Exception:
        raw = json.dumps(spec, sort_keys=True, separators=(",", ":"),
                         default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def record_confirmation(
    domain: str,
    spec: Dict[str, Any],
    instance_id: str,
    summary: str = "CONFIRMED",
) -> Dict[str, Any]:
    """Record that `instance_id` confirmed a verification of `spec` in `domain`.

    Returns the updated trust record for this spec_hash.
    """
    h = spec_hash(spec)
    now = int(time.time())
    lock = _lock_for(domain)
    with lock:
        index = _read_index(domain)
        if h not in index:
            index[h] = {
                "count": 0,
                "instance_ids": [],
                "first_seen": now,
                "last_seen": now,
                "summary": summary,
            }
        record = index[h]
        if instance_id and instance_id not in record["instance_ids"]:
            record["instance_ids"].append(instance_id)
            record["count"] = len(record["instance_ids"])
        record["last_seen"] = now
        record["summary"] = summary
        _write_index(domain, index)
        return dict(record)


def get_trust(domain: str, spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Return the trust record for this spec in domain, or None."""
    h = spec_hash(spec)
    lock = _lock_for(domain)
    with lock:
        index = _read_index(domain)
        return dict(index[h]) if h in index else None


def get_trust_by_hash(domain: str, h: str) -> Optional[Dict[str, Any]]:
    """Return trust record by pre-computed hash, or None."""
    lock = _lock_for(domain)
    with lock:
        index = _read_index(domain)
        return dict(index[h]) if h in index else None


def list_trusted(domain: str, min_count: int = 1) -> List[Dict[str, Any]]:
    """Return all trust records for domain with count >= min_count."""
    lock = _lock_for(domain)
    with lock:
        index = _read_index(domain)
        return [
            {"spec_hash": h, **v}
            for h, v in index.items()
            if v.get("count", 0) >= min_count
        ]


def trust_stats() -> Dict[str, Any]:
    """Summary counts across all domains in the trust index."""
    idx_dir = _index_dir()
    if not idx_dir.exists():
        return {}
    result: Dict[str, Any] = {}
    for path in sorted(idx_dir.glob("*.json")):
        domain = path.stem
        try:
            with path.open("r", encoding="utf-8") as f:
                index = json.load(f)
            total = len(index)
            multi = sum(1 for v in index.values() if v.get("count", 0) > 1)
            result[domain] = {"total_hashes": total, "multi_confirmed": multi}
        except Exception:
            pass
    return result
