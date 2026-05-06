"""Content-addressable store (CAS) — in-house permanent receipt storage.

Every sealed WitnessRecord is stored here by its SHA-256 content hash.
The hash is both the address and the integrity proof: fetch-by-hash and
you know immediately whether the content was tampered with.

This is the in-house replacement for Arweave. Same content-addressing
principle (hash = address), no external dependency, no tokens required.
Works offline, over LoRa, and on a microSD.

Storage layout:
    <base_dir>/<hash[:2]>/<hash[2:]>.json

  The 2-char prefix keeps directory listings manageable at scale —
  256 subdirectories, each holding up to ~millions of records.

API surface:
    store(record_dict)        → content_hash (str)
    fetch(content_hash)       → dict | None
    exists(content_hash)      → bool
    list_hashes()             → List[str]
    delete(content_hash)      → bool   (use sparingly — CAS is append-only by design)
    verify(content_hash)      → (ok: bool, detail: str)

Replication:
    Nodes sync their CAS over the existing federation endpoints
    (/chain/since + /chain/receive). The CAS is a peer supplement —
    detailed receipt blobs alongside the lighter ledger entries.

Environment:
    CONCORDANCE_CAS_DIR  — override default storage path
    CONCORDANCE_DATA_DIR — parent for default path (~/.concordance or data/)
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Storage path ────────────────────────────────────────────────────────

def _cas_dir() -> Path:
    env = os.environ.get("CONCORDANCE_CAS_DIR", "").strip()
    if env:
        return Path(env)
    data = os.environ.get("CONCORDANCE_DATA_DIR", "").strip()
    if data:
        return Path(data) / "cas"
    # Default: data/cas/ relative to cwd (matches ledger/journal convention)
    return Path("data") / "cas"


# ── Core hash helpers ───────────────────────────────────────────────────

def content_hash_of(record_dict: Dict[str, Any]) -> str:
    """Compute the canonical SHA-256 content hash of a record dict.

    Excludes `content_hash` and `permanent_ref` fields so the hash is
    stable regardless of whether those fields are present. This matches
    WitnessRecord.to_dict() which computes the hash the same way.
    """
    payload = {k: v for k, v in record_dict.items()
               if k not in ("content_hash", "permanent_ref")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _record_path(base: Path, h: str) -> Path:
    return base / h[:2] / f"{h[2:]}.json"


# ── Public API ──────────────────────────────────────────────────────────

def store(
    record_dict: Dict[str, Any],
    *,
    base_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> str:
    """Store a record dict in the CAS. Returns its content_hash.

    If the hash already exists and overwrite=False, the call is a no-op
    (idempotent). The CAS is append-only by design.
    """
    base = base_dir or _cas_dir()
    h = content_hash_of(record_dict)
    path = _record_path(base, h)

    if path.exists() and not overwrite:
        return h

    path.parent.mkdir(parents=True, exist_ok=True)
    # Embed content_hash in the stored file for self-describing records
    stored = dict(record_dict)
    stored["content_hash"] = h
    path.write_text(
        json.dumps(stored, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return h


def fetch(
    content_hash: str,
    *,
    base_dir: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch a record by its content hash. Returns None if not found."""
    base = base_dir or _cas_dir()
    path = _record_path(base, content_hash)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def exists(
    content_hash: str,
    *,
    base_dir: Optional[Path] = None,
) -> bool:
    base = base_dir or _cas_dir()
    return _record_path(base, content_hash).exists()


def verify(
    content_hash: str,
    *,
    base_dir: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Verify a stored record's integrity by recomputing its hash."""
    record = fetch(content_hash, base_dir=base_dir)
    if record is None:
        return False, f"not found: {content_hash}"
    actual = content_hash_of(record)
    if actual != content_hash:
        return False, f"hash mismatch: stored={content_hash} computed={actual}"
    return True, "ok"


def list_hashes(*, base_dir: Optional[Path] = None) -> List[str]:
    """Return all content hashes in the CAS, sorted."""
    base = base_dir or _cas_dir()
    hashes: List[str] = []
    if not base.exists():
        return hashes
    for prefix_dir in sorted(base.iterdir()):
        if not prefix_dir.is_dir() or len(prefix_dir.name) != 2:
            continue
        for f in sorted(prefix_dir.glob("*.json")):
            hashes.append(prefix_dir.name + f.stem)
    return hashes


def delete(
    content_hash: str,
    *,
    base_dir: Optional[Path] = None,
) -> bool:
    """Remove a record from the CAS. Returns True if it existed."""
    base = base_dir or _cas_dir()
    path = _record_path(base, content_hash)
    if not path.exists():
        return False
    path.unlink()
    return True


def stats(*, base_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Summary statistics for the CAS."""
    base = base_dir or _cas_dir()
    hashes = list_hashes(base_dir=base)
    total_bytes = 0
    for h in hashes:
        p = _record_path(base, h)
        try:
            total_bytes += p.stat().st_size
        except OSError:
            pass
    return {
        "count": len(hashes),
        "total_bytes": total_bytes,
        "base_dir": str(base.resolve()) if base.exists() else str(base),
    }


__all__ = [
    "content_hash_of",
    "store",
    "fetch",
    "exists",
    "verify",
    "list_hashes",
    "delete",
    "stats",
]
