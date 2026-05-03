"""Evidence Ledger — closest-case precedent lookup.

The ledger is a directory of JSON files, one per recorded precedent.
Each file describes a sealed decision the engine (or a human community)
has previously made: the axis it sat on, the dimensional coordinates,
and a reasoning trace that can be overlaid onto a similar incoming
packet.

Doctrinal commitments encoded here:

  * **Discovery, not design.** The lookup walks the ledger and reports
    the closest match by shared scaffold dimensions. It does *not*
    invent precedents. If the ledger is empty or no precedent shares a
    dimension with the input packet, `find_closest` returns either
    None or a `ClosestCase(precedent_id=None)` — explicit absence is
    the correct answer to "no comparable precedent."

  * **Categorize, don't answer.** The ledger lookup returns a
    `ClosestCase` with `reasoning_overlay`; it does not collapse to a
    verdict. Whether the precedent's reasoning applies to the user's
    situation is the human's call (the Socratic mechanism in the
    walkthrough surfaces that question).

Precedent file format (one JSON per file under the ledger directory):

    {
      "precedent_id": "ledger://decision/2024-11-08/admit-member-007",
      "axis": "governance",
      "dimensions": ["reasoning", "authority_trust", "time_sequence"],
      "summary": "Community admitted member after 90-day restitution.",
      "anchors": [
        {"ref": "Mt 18:15-17", "layer": "jesus_words"},
        {"ref": "Lk 17:3-4", "layer": "jesus_words"}
      ],
      "reasoning_overlay": {
        "step_1": "Confession witnessed by 2+ community members",
        "step_2": "Restitution verified active",
        "step_3": "Observation period satisfied wait window",
        "step_4": "Final vote 4/5 majority"
      }
    }

The ledger directory defaults to `lw/ledger/` at the repo root. Override
via the `CONCORDANCE_LEDGER_DIR` environment variable for tests or
alternate deployments.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .witness_record import ClosestCase
from . import grid


def _default_ledger_dir() -> Path:
    """Repo-root `lw/ledger/` by default; overridable via env var."""
    override = os.environ.get("CONCORDANCE_LEDGER_DIR")
    if override:
        return Path(override)
    # src/concordance_engine/ledger.py → repo root is two parents up
    # from concordance_engine/.
    return Path(__file__).resolve().parents[2] / "lw" / "ledger"


def _load_precedents(ledger_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read every *.json file in the ledger directory. Malformed files
    are skipped silently (the ledger is best-effort; one bad file
    shouldn't break a session)."""
    d = ledger_dir or _default_ledger_dir()
    if not d.exists() or not d.is_dir():
        return []
    out: List[Dict[str, Any]] = []
    for f in sorted(d.glob("*.json")):
        try:
            with open(f, encoding="utf-8") as fp:
                p = json.load(fp)
            if isinstance(p, dict) and "precedent_id" in p:
                out.append(p)
        except (OSError, json.JSONDecodeError):
            continue
    return out


def list_precedents(ledger_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return every precedent currently in the ledger.

    Used by `concordance ledger list` and for diagnostics. Each item is
    the raw precedent dict; consumers should not assume any field beyond
    `precedent_id` is present (formats may evolve).
    """
    return _load_precedents(ledger_dir)


def find_closest(
    packet: Dict[str, Any],
    *,
    ledger_dir: Optional[Path] = None,
) -> Optional[ClosestCase]:
    """Find the closest precedent for an input packet.

    Distance metric (V1, principled-but-simple):
      1. Compute the input packet's scaffold dimensions via
         `grid.axis_dimensions`.
      2. For each precedent, compute the shared dimensions (set
         intersection) and the union.
      3. Distance = 1 − Jaccard similarity = 1 − |shared| / |union|.
      4. Pick the precedent with the smallest distance, ties broken by
         exact-axis match first, then by precedent_id alphabetical.

    Returns:
      * `ClosestCase(precedent_id=None)` if the ledger has no precedents
        for this packet's axis at all (explicit "novel claim" signal).
      * `ClosestCase(precedent_id=..., shared_dimensions=..., distance=...)`
        for the closest match, with `reasoning_overlay` if the precedent
        carries one.
      * `None` only if the input packet has no resolvable axis (caller
        should treat as "not applicable" — no lookup was made).

    The threshold for "comparable" is at least one shared dimension. If
    nothing shares any dimension, returns the explicit-novel form.
    """
    domain = (packet.get("domain") or "").lower()
    if not domain or domain not in grid.AXIS_DIMENSIONS:
        # Unknown axis — we can't do scaffold-based lookup. Caller can
        # decide whether to treat that as "skip lookup" (we return None)
        # or as "novel claim" (caller wraps in ClosestCase explicitly).
        return None

    packet_dims = grid.AXIS_DIMENSIONS[domain]
    precedents = _load_precedents(ledger_dir)

    if not precedents:
        # Ledger is empty: explicit novel-claim, not silent absence.
        return ClosestCase(precedent_id=None)

    best = None
    best_distance = float("inf")
    best_shared = frozenset()
    for p in precedents:
        p_dims = frozenset(p.get("dimensions", []))
        if not p_dims:
            continue
        shared = packet_dims & p_dims
        union = packet_dims | p_dims
        if not union:
            continue
        distance = 1.0 - (len(shared) / len(union))
        # Tie-breaks: exact-axis match wins over distance ties.
        same_axis_bonus = 0 if p.get("axis") == domain else 0.001
        effective = distance + same_axis_bonus
        if effective < best_distance:
            best_distance = effective
            best = p
            best_shared = shared

    if best is None or not best_shared:
        # Nothing in the ledger shared even one dimension with this
        # packet — honest-novel response.
        return ClosestCase(precedent_id=None)

    return ClosestCase(
        precedent_id=best["precedent_id"],
        shared_dimensions=best_shared,
        distance=round(best_distance, 4),
        reasoning_overlay=best.get("reasoning_overlay"),
    )


__all__ = ["find_closest", "list_precedents"]
