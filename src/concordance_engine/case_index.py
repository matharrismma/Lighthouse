"""Closest-case distance computation and overlay builder.

Pure module — no I/O. Takes axis coordinates and anchor sets, returns
distance scores and ClosestCase objects.  The case store (api/case_store.py)
handles persistence; this module handles the math.

Distance metric (0 = identical, 1 = completely unlike):

    axis_overlap  × 0.50   — primary structural signal
    anchor_overlap × 0.35  — doctrinal / scripture alignment
    domain_match  × 0.15   — same domain is a bonus, not a requirement

The three weights express a design principle: the engine is axis-native.
A theology packet and a governance packet that share authority_trust +
time_sequence + Matt 18:15-17 are structurally closer than two theology
packets that share nothing but their domain label.

As the ledger fills, the partition refines. New verdicts cost less —
most of the reasoning is already in the closest precedent; the verifiers
only close the remaining gap. This is the convergence property.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from .witness_record import ClosestCase


# ── Distance ───────────────────────────────────────────────────────────

def jaccard(a: FrozenSet[str], b: FrozenSet[str]) -> float:
    """Jaccard similarity for two frozensets.  Returns 0 when both empty."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def axis_distance(
    domain_a: str,
    dims_a: FrozenSet[str],
    anchors_a: Tuple[str, ...],
    domain_b: str,
    dims_b: FrozenSet[str],
    anchors_b: Tuple[str, ...],
) -> float:
    """Weighted distance in axis × anchor × domain space.

    Returns a float in [0.0, 1.0].
      0.0 — structurally identical
      1.0 — completely unlike
    """
    axis_sim   = jaccard(dims_a, dims_b)
    anchor_sim = jaccard(frozenset(anchors_a), frozenset(anchors_b))
    domain_sim = 1.0 if domain_a == domain_b else 0.0

    similarity = axis_sim * 0.50 + anchor_sim * 0.35 + domain_sim * 0.15
    return round(1.0 - similarity, 4)


# ── Candidate scoring ──────────────────────────────────────────────────

def score_candidates(
    domain: str,
    dims: FrozenSet[str],
    anchors: Tuple[str, ...],
    candidates: List[Dict[str, Any]],
    top_k: int = 3,
    exclude_hash: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Score a list of candidate records against the query coordinates.

    Each candidate dict is expected to have:
      "domain"    : str
      "dimensions": list[str]
      "anchors"   : list[str]
      "verdict"   : str
      "content_hash": str
      ... (other stored fields passed through)

    Returns the top-k candidates sorted by ascending distance, each
    augmented with a "distance" key.
    """
    scored: List[Dict[str, Any]] = []
    for c in candidates:
        if exclude_hash and c.get("content_hash") == exclude_hash:
            continue
        dist = axis_distance(
            domain, dims, anchors,
            c.get("domain", ""),
            frozenset(c.get("dimensions") or []),
            tuple(c.get("anchors") or []),
        )
        scored.append({**c, "distance": dist})

    scored.sort(key=lambda x: x["distance"])
    return scored[:top_k]


# ── ClosestCase builder ────────────────────────────────────────────────

def build_closest_case(
    best: Dict[str, Any],
    dims: FrozenSet[str],
    anchors: Tuple[str, ...],
) -> ClosestCase:
    """Build a WitnessRecord-compatible ClosestCase from a scored candidate."""
    past_dims    = frozenset(best.get("dimensions") or [])
    past_anchors = set(best.get("anchors") or [])

    shared_dims    = dims & past_dims
    shared_anchors = frozenset(anchors) & past_anchors

    return ClosestCase(
        precedent_id=best.get("content_hash"),
        shared_dimensions=shared_dims,
        shared_anchors=tuple(sorted(shared_anchors)),
        distance=best.get("distance"),
        reasoning_overlay={
            "verdict":          best.get("verdict"),
            "domain":           best.get("domain"),
            "ledger_seq":       best.get("ledger_seq"),
            "nostr_event_id":   best.get("nostr_event_id"),
            "verifier_summary": best.get("verifier_summary") or [],
            "timestamp":        best.get("timestamp"),
        },
    )


def find_closest(
    domain: str,
    dims: FrozenSet[str],
    anchors: Tuple[str, ...],
    candidates: List[Dict[str, Any]],
    top_k: int = 1,
    exclude_hash: Optional[str] = None,
) -> List[ClosestCase]:
    """Score candidates and return ClosestCase objects, best first.

    Returns an empty list if no candidates exist or all are excluded.
    """
    scored = score_candidates(domain, dims, anchors, candidates,
                              top_k=top_k, exclude_hash=exclude_hash)
    return [build_closest_case(c, dims, anchors) for c in scored]
