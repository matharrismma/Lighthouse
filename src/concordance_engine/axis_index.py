"""Axis-dimension index for PolymathicRecord precedent retrieval.

When a PolymathicRecord is sealed, its scaffold dimensions are indexed here.
The next time the poly agent classifies a situation with similar predicted dims,
it walks this index before dispatching workers — surfacing the closest prior
as an overlay.

Storage: data/axis_index.json  (single atomic-write JSON file)
Format: {dimension: [{hash, verdict, summary, sealed_at, dims[]}], ...}

Thread-safe: all writes are protected by a threading.Lock.
Offline-capable: no network calls; no oracle calls.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_LOCK = threading.Lock()
_MAX_PER_DIM = 500  # ring-buffer cap per dimension

_INDEX_PATH = Path(
    os.environ.get("CONCORDANCE_DATA_DIR", "data")
) / "axis_index.json"


def _load() -> Dict[str, List[Dict[str, Any]]]:
    if not _INDEX_PATH.exists():
        return {}
    try:
        with _INDEX_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save(index: Dict[str, List[Dict[str, Any]]]) -> None:
    _INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _INDEX_PATH.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(index, f, separators=(",", ":"))
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass
    tmp.replace(_INDEX_PATH)


def update_index(
    content_hash: str,
    composite_verdict: str,
    situation: str,
    axis_dims: List[str],
) -> None:
    """Register a sealed PolymathicRecord in the axis index.

    Indexes the record under every scaffold dimension it touches.
    Each entry carries the full dim list so Jaccard scoring works
    without secondary lookups.
    """
    if not axis_dims:
        return
    summary = situation[:160].strip()
    entry = {
        "hash": content_hash,
        "verdict": composite_verdict,
        "summary": summary,
        "sealed_at": int(time.time()),
        "dims": sorted(set(axis_dims)),
    }
    with _LOCK:
        index = _load()
        for dim in axis_dims:
            bucket = index.setdefault(dim, [])
            # Deduplicate: remove prior entry for same hash in this bucket
            bucket = [e for e in bucket if e.get("hash") != content_hash]
            bucket.append(entry)
            # Ring buffer: keep newest _MAX_PER_DIM
            if len(bucket) > _MAX_PER_DIM:
                bucket = bucket[-_MAX_PER_DIM:]
            index[dim] = bucket
        _save(index)


def find_closest(
    predicted_dims: List[str],
    min_score: float = 0.15,
) -> Optional[Dict[str, Any]]:
    """Walk the index and return the closest sealed record by Jaccard similarity.

    Jaccard = |predicted ∩ prior.dims| / |predicted ∪ prior.dims|

    Returns None when no sealed records share any predicted dimension,
    or when the best score is below min_score.
    """
    if not predicted_dims:
        return None

    predicted = set(predicted_dims)
    candidates: Dict[str, Dict[str, Any]] = {}  # hash → entry

    with _LOCK:
        index = _load()

    # Gather all records that share at least one predicted dim
    for dim in predicted_dims:
        for entry in index.get(dim, []):
            h = entry.get("hash", "")
            if h and h not in candidates:
                candidates[h] = entry

    if not candidates:
        return None

    best_hash: Optional[str] = None
    best_score: float = 0.0

    for h, entry in candidates.items():
        prior = set(entry.get("dims", []))
        if not prior:
            continue
        intersection = len(predicted & prior)
        union = len(predicted | prior)
        if union == 0:
            continue
        score = intersection / union
        if score > best_score:
            best_score = score
            best_hash = h

    if best_hash is None or best_score < min_score:
        return None

    best = candidates[best_hash].copy()
    best["jaccard_score"] = round(best_score, 3)
    best["shared_dims"] = sorted(predicted & set(best.get("dims", [])))
    return best


def query_index(dims: List[str]) -> List[Dict[str, Any]]:
    """Return all entries that share at least one of the given dimensions.

    Used for browsing / federation; use find_closest for single-call retrieval.
    """
    seen: Set[str] = set()
    results: List[Dict[str, Any]] = []
    with _LOCK:
        index = _load()
    for dim in dims:
        for entry in index.get(dim, []):
            h = entry.get("hash", "")
            if h and h not in seen:
                seen.add(h)
                results.append(entry)
    return results


def index_stats() -> Dict[str, Any]:
    """Return summary statistics about the axis index."""
    with _LOCK:
        index = _load()
    total = sum(len(v) for v in index.values())
    hashes: Set[str] = set()
    for bucket in index.values():
        for e in bucket:
            hashes.add(e.get("hash", ""))
    return {
        "dimension_count": len(index),
        "total_entries": total,
        "unique_records": len(hashes),
        "dimensions": sorted(index.keys()),
    }
