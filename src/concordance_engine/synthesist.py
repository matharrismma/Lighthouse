"""Synthesist hummingbird — discovers multi-domain co-occurrence patterns.

Where the Connector finds 2-domain edges (pairs that share an axis), the
Synthesist finds 3+ domain clusters — the cross-domain shapes that
polymathic queries actually traverse. Each pattern records the
intersection of scaffold axes across the cluster, so future polymathic
runs can pre-warm precedent lookups even before any record has been
formally sealed.

Storage: data/synthesis_patterns.jsonl  (append-only, one event per line)
Format:
    {
        "ts": <unix>,
        "signature": ["domain_a", "domain_b", "domain_c"],   # sorted unique
        "domain_count": 3,
        "shared_axes": ["authority_trust", "time_sequence"], # axis intersection
        "axis_count": 2,
        "first_seen_entry_id": "<journal entry id>",
    }

Pure functions: no I/O, no oracle calls. Used by the Synthesist worker
in api/app.py and reusable from any other place that needs to score a
candidate cluster.
"""
from __future__ import annotations

from typing import Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .grid import AXIS_DIMENSIONS, axis_dimensions


_MIN_CLUSTER = 3


def axes_for_domain(domain: str) -> FrozenSet[str]:
    """Return the scaffold axis set for a domain, empty frozenset if unknown."""
    try:
        return frozenset(axis_dimensions(domain))
    except KeyError:
        return frozenset()


def discover_pattern(domains: Iterable[str]) -> Optional[Dict[str, object]]:
    """Score a candidate cluster and return its synthesis pattern.

    A cluster qualifies as a pattern iff:
      * it has at least 3 distinct domains known to the grid, AND
      * those domains share at least one scaffold axis in common.

    Returns the pattern dict or None when the cluster doesn't qualify.
    """
    distinct = sorted(set(d for d in domains if d))
    if len(distinct) < _MIN_CLUSTER:
        return None

    axis_sets: List[FrozenSet[str]] = [axes_for_domain(d) for d in distinct]
    axis_sets = [s for s in axis_sets if s]
    if len(axis_sets) < _MIN_CLUSTER:
        return None

    shared: FrozenSet[str] = axis_sets[0]
    for s in axis_sets[1:]:
        shared = shared & s
        if not shared:
            return None

    return {
        "signature": distinct,
        "domain_count": len(distinct),
        "shared_axes": sorted(shared),
        "axis_count": len(shared),
    }


def signature_key(domains: Iterable[str]) -> Tuple[str, ...]:
    """Stable canonical key for deduplication."""
    return tuple(sorted(set(d for d in domains if d)))


def extract_domains_from_tags(tags: Iterable[str]) -> List[str]:
    """Pick out the entries from a tag list that name a known grid domain.

    The journal accepts free-form tags. Domains are tags that resolve to
    a non-empty axis set in the grid module. Anything else is ignored.
    """
    return [t for t in tags if t in AXIS_DIMENSIONS or axes_for_domain(t)]
