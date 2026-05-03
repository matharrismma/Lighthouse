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
from typing import Any, Dict, List, Optional, Tuple

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


def _anchor_to_ref(raw: Any) -> Optional[str]:
    """Normalize an anchor in either bare-string or dict form to its
    bare reference. Mirrors `scripture._anchor_to_ref` so the ledger
    can read the same packet anchors the scripture verifier reads."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        ref = raw.get("ref")
        if isinstance(ref, str):
            return ref
    return None


def _packet_anchor_refs(packet: Dict[str, Any]) -> List[str]:
    """Pull bare anchor refs out of a packet from any of the canonical
    fields (`scripture_anchors`, `DECISION_PACKET.scripture_anchors`,
    `refs`). Empty list if none present."""
    raw_anchors: List[Any] = []
    raw_anchors.extend(packet.get("scripture_anchors") or [])
    dp = packet.get("DECISION_PACKET")
    if isinstance(dp, dict):
        raw_anchors.extend(dp.get("scripture_anchors") or [])
    raw_anchors.extend(packet.get("refs") or [])
    out: List[str] = []
    for a in raw_anchors:
        ref = _anchor_to_ref(a)
        if ref:
            out.append(ref)
    return out


def _precedent_anchor_refs(precedent: Dict[str, Any]) -> List[str]:
    refs: List[str] = []
    for a in precedent.get("anchors") or []:
        r = _anchor_to_ref(a)
        if r:
            refs.append(r)
    return refs


# Weight assigned to anchor overlap when both packet and precedent
# carry anchors. The dimension-based distance contributes (1 - W); the
# anchor-overlap signal contributes W. Picked so anchor overlap can
# shift the ranking but not dominate it: a precedent with full anchor
# match but only one shared dimension shouldn't beat one with three
# shared dimensions and zero anchor match.
_ANCHOR_WEIGHT = 0.35


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
      3. Dimension distance = 1 − Jaccard similarity on dimensions.
      4. If both packet AND precedent carry anchors, compute Jaccard
         similarity on bare anchor refs ("Mt 18:15-17", etc.) and
         blend: `distance = (1 - W) * dim_dist + W * (1 - anchor_sim)`,
         with W = 0.35. When either side has no anchors, falls back to
         pure dimension distance.
      5. Pick the precedent with the smallest distance, ties broken by
         exact-axis match.

    Returns:
      * `ClosestCase(precedent_id=None)` if the ledger has no precedents
        for this packet's axis at all (explicit "novel claim" signal).
      * `ClosestCase(precedent_id=..., shared_dimensions=...,
                      shared_anchors=..., distance=...)`
        for the closest match, with `reasoning_overlay` if the precedent
        carries one.
      * `None` only if the input packet has no resolvable axis (caller
        should treat as "not applicable" — no lookup was made).

    The threshold for "comparable" is at least one shared dimension OR
    one shared anchor. If nothing shares either, returns explicit-novel.
    """
    domain = (packet.get("domain") or "").lower()
    if not domain or domain not in grid.AXIS_DIMENSIONS:
        # Unknown axis — we can't do scaffold-based lookup. Caller can
        # decide whether to treat that as "skip lookup" (we return None)
        # or as "novel claim" (caller wraps in ClosestCase explicitly).
        return None

    packet_dims = grid.AXIS_DIMENSIONS[domain]
    packet_anchors = set(_packet_anchor_refs(packet))
    precedents = _load_precedents(ledger_dir)

    if not precedents:
        # Ledger is empty: explicit novel-claim, not silent absence.
        return ClosestCase(precedent_id=None)

    best = None
    best_distance = float("inf")
    best_shared_dims = frozenset()
    best_shared_anchors: Tuple[str, ...] = ()
    for p in precedents:
        p_dims = frozenset(p.get("dimensions", []))
        if not p_dims:
            continue
        shared_dims = packet_dims & p_dims
        union_dims = packet_dims | p_dims
        if not union_dims:
            continue
        dim_distance = 1.0 - (len(shared_dims) / len(union_dims))

        # Anchor overlap (only when both sides carry anchors).
        p_anchors = set(_precedent_anchor_refs(p))
        shared_anchors_set = packet_anchors & p_anchors
        if packet_anchors and p_anchors:
            anchor_sim = (
                len(shared_anchors_set) / len(packet_anchors | p_anchors)
            )
            distance = (
                (1.0 - _ANCHOR_WEIGHT) * dim_distance
                + _ANCHOR_WEIGHT * (1.0 - anchor_sim)
            )
        else:
            distance = dim_distance

        # Tie-breaks: exact-axis match wins over otherwise-equal scores.
        same_axis_bonus = 0 if p.get("axis") == domain else 0.001
        effective = distance + same_axis_bonus
        if effective < best_distance:
            best_distance = effective
            best = p
            best_shared_dims = shared_dims
            best_shared_anchors = tuple(sorted(shared_anchors_set))

    if best is None or (not best_shared_dims and not best_shared_anchors):
        # Nothing in the ledger shared even one dimension or anchor with
        # this packet — honest-novel response.
        return ClosestCase(precedent_id=None)

    return ClosestCase(
        precedent_id=best["precedent_id"],
        shared_dimensions=best_shared_dims,
        shared_anchors=best_shared_anchors,
        distance=round(best_distance, 4),
        reasoning_overlay=best.get("reasoning_overlay"),
    )


def _slugify(value: str) -> str:
    """Filesystem-safe slug for precedent file names."""
    out = []
    for c in value.lower():
        if c.isalnum():
            out.append(c)
        elif c in (" ", "-", "_", ".", "/", ":"):
            out.append("-")
        # drop everything else
    slug = "".join(out)
    # collapse runs of dashes and trim
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-") or "untitled"


def seal_to_ledger(
    record,
    *,
    summary: str,
    precedent_id: Optional[str] = None,
    ledger_dir: Optional[Path] = None,
    overwrite: bool = False,
) -> Path:
    """Append a sealed WitnessRecord to the Evidence Ledger as a new
    precedent.

    Only PASS records are accepted. The ledger is a record of *resolved*
    decisions; rejected or quarantined packets aren't precedents to
    overlay onto future situations.

    `summary` is a one-line human description (required — no auto-
    generation, because the ledger's value is the human framing).
    `precedent_id` defaults to `ledger://<axis>/<auto-slug>` if not
    supplied. The function returns the path to the written file.

    The reasoning_overlay is auto-generated from gate verdicts and
    confirmed verifier rules. Future hand-edits of the file are
    welcome and supported.

    Raises:
      * ValueError if `record.overall != "PASS"` (REJECT/QUARANTINE
        can't be sealed).
      * FileExistsError if a precedent file already exists at the
        target path and `overwrite=False`.
    """
    if record.overall != "PASS":
        raise ValueError(
            f"Only PASS records can be sealed to the ledger; got {record.overall}. "
            "REJECTED or QUARANTINED packets are not precedents."
        )
    if not summary or not summary.strip():
        raise ValueError("`summary` is required (one-line human description)")

    axis = record.axis_coords.axis if record.axis_coords else "unknown"
    dimensions = (
        sorted(record.axis_coords.dimensions)
        if record.axis_coords else []
    )

    # Auto-derive a precedent_id if none supplied.
    if precedent_id is None:
        slug_base = record.packet_id or _slugify(summary)[:60]
        slug_clean = _slugify(slug_base)
        precedent_id = f"ledger://{axis}/{slug_clean}"

    # Derive reasoning_overlay from gate verdicts + confirmed verifiers.
    overlay: Dict[str, str] = {}
    step = 1
    for gr in record.gate_results:
        if gr.status == "PASS":
            details_msg = ""
            if gr.details and isinstance(gr.details, dict):
                verified = gr.details.get("verified") or []
                if verified:
                    details_msg = "; ".join(str(v) for v in verified[:3])
            overlay[f"step_{step}_{gr.gate.lower()}"] = (
                details_msg or f"{gr.gate} gate confirmed"
            )
            step += 1

    # Anchors carry their layer (from the WitnessRecord) into the
    # precedent file so future lookups can re-use the same form.
    anchor_dicts = [a.to_dict() for a in record.anchors]

    precedent_payload = {
        "precedent_id": precedent_id,
        "axis": axis,
        "dimensions": dimensions,
        "summary": summary.strip(),
        "anchors": anchor_dicts,
        "reasoning_overlay": overlay,
    }

    # Determine the target file path.
    d = ledger_dir or _default_ledger_dir()
    d.mkdir(parents=True, exist_ok=True)
    file_slug = _slugify(precedent_id.replace("ledger://", ""))
    target = d / f"{file_slug}.json"
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"precedent file already exists at {target}. "
            "Pass overwrite=True to replace it."
        )
    with open(target, "w", encoding="utf-8") as f:
        json.dump(precedent_payload, f, indent=2)
        f.write("\n")
    return target


__all__ = ["find_closest", "list_precedents", "seal_to_ledger"]
