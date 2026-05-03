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
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .witness_record import ClosestCase
from .validate import canonical_json_bytes, sha256_bytes
from . import grid


# Sentinel value for the first precedent's prev_hash. Genesis link.
GENESIS_HASH = "GENESIS"

# Fields managed by the chain layer — excluded from content_hash
# computation so the hash is over the *content* of the precedent, not
# over the chain metadata wrapping it.
_CHAIN_FIELDS = ("content_hash", "prev_hash")


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


# ── Hash chain ─────────────────────────────────────────────────────────

def compute_content_hash(precedent: Dict[str, Any]) -> str:
    """Compute the content_hash for a precedent — SHA-256 of its
    canonical JSON, excluding the chain fields themselves so the hash
    is stable across re-sealing."""
    payload = {k: v for k, v in precedent.items() if k not in _CHAIN_FIELDS}
    return sha256_bytes(canonical_json_bytes(payload))


def _ledger_chain_files(ledger_dir: Optional[Path] = None) -> List[Path]:
    """Files in chain order — by `sealed_at` timestamp ascending, with
    filename as tiebreaker for files written in the same second.

    Using sealed_at (rather than alphabetical filename order) means
    inserting a file later doesn't change the chain position of
    earlier files. Amendments and out-of-order additions both keep
    the chain intact.

    Files without `sealed_at` (pre-chain or hand-edited) fall back to
    filesystem mtime so legacy precedents still order coherently.
    """
    d = ledger_dir or _default_ledger_dir()
    if not d.exists() or not d.is_dir():
        return []
    files = list(d.glob("*.json"))

    def _sort_key(f: Path):
        data = _read_precedent_file(f)
        if data and isinstance(data.get("sealed_at"), (int, float)):
            return (data["sealed_at"], f.name)
        # Fallback: file mtime, plus filename as final tiebreaker.
        try:
            return (f.stat().st_mtime, f.name)
        except OSError:
            return (0.0, f.name)

    return sorted(files, key=_sort_key)


def _read_precedent_file(p: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(p, encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def verify_chain(
    ledger_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Walk the ledger in chain order and verify integrity.

    Two checks per file:
      1. Recompute content_hash and compare to stored value.
      2. Confirm prev_hash matches the prior file's content_hash
         (or GENESIS for the first file).

    Files written before the chain layer existed (no `content_hash`
    field) are reported as `unsigned` — a degraded state, not a
    failure. The chain is only enforced on files that opt in. Future
    seals will write the chain fields automatically.

    Returns a structured report:
      {
        "ok": bool,
        "total": int,
        "verified": int,
        "unsigned": [filename, ...],
        "tampered": [{file, error}],
        "broken_links": [{file, expected_prev, got_prev}],
      }
    """
    files = _ledger_chain_files(ledger_dir)
    report: Dict[str, Any] = {
        "ok": True,
        "total": len(files),
        "verified": 0,
        "unsigned": [],
        "tampered": [],
        "broken_links": [],
    }
    expected_prev = GENESIS_HASH
    for f in files:
        precedent = _read_precedent_file(f)
        if precedent is None:
            report["tampered"].append(
                {"file": f.name, "error": "could not parse JSON"}
            )
            report["ok"] = False
            continue

        stored_hash = precedent.get("content_hash")
        if stored_hash is None:
            # Pre-chain precedent. Recompute what its hash would be
            # so the next file in chain can still link to it.
            report["unsigned"].append(f.name)
            expected_prev = compute_content_hash(precedent)
            continue

        # Verify content_hash.
        recomputed = compute_content_hash(precedent)
        if recomputed != stored_hash:
            report["tampered"].append({
                "file": f.name,
                "error": f"content_hash mismatch: stored {stored_hash[:12]}..., "
                         f"recomputed {recomputed[:12]}...",
            })
            report["ok"] = False
            expected_prev = stored_hash  # advance regardless
            continue

        # Verify prev_hash link.
        stored_prev = precedent.get("prev_hash", GENESIS_HASH)
        if stored_prev != expected_prev:
            report["broken_links"].append({
                "file": f.name,
                "expected_prev": expected_prev[:12] + "..." if expected_prev != GENESIS_HASH else GENESIS_HASH,
                "got_prev": stored_prev[:12] + "..." if stored_prev != GENESIS_HASH else GENESIS_HASH,
            })
            report["ok"] = False
            expected_prev = stored_hash
            continue

        report["verified"] += 1
        expected_prev = stored_hash
    return report


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

    # If the matched precedent has been amended, surface the latest
    # version. Older versions remain in the ledger for audit, but the
    # closest-case overlay should reflect the community's current
    # framing of the decision.
    matched_id = best["precedent_id"]
    latest_id = latest_in_amendment_chain(matched_id, ledger_dir=ledger_dir)
    if latest_id != matched_id:
        # Walk forward to the latest precedent's record.
        for p in precedents:
            if p.get("precedent_id") == latest_id:
                best = p
                break

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
        "sealed_at": time.time(),
    }

    # Determine the target file path BEFORE chain link computation.
    # Chain order is by `sealed_at` timestamp, so this new file slots
    # at the end of the chain (it has the latest sealed_at).
    d = ledger_dir or _default_ledger_dir()
    d.mkdir(parents=True, exist_ok=True)
    file_slug = _slugify(precedent_id.replace("ledger://", ""))
    target = d / f"{file_slug}.json"
    if target.exists() and not overwrite:
        raise FileExistsError(
            f"precedent file already exists at {target}. "
            "Pass overwrite=True to replace it."
        )

    # Compute the chain link: this precedent's prev_hash is the
    # content_hash of the LATEST file in the chain (highest sealed_at).
    # Because the new file's sealed_at is `now`, it's strictly later
    # than every existing file, so it always appends at the end.
    existing = [f for f in _ledger_chain_files(d) if f != target]
    if not existing:
        prev_hash = GENESIS_HASH
    else:
        last = existing[-1]
        last_data = _read_precedent_file(last)
        if last_data and "content_hash" in last_data:
            prev_hash = last_data["content_hash"]
        elif last_data:
            prev_hash = compute_content_hash(last_data)
        else:
            prev_hash = GENESIS_HASH

    precedent_payload["prev_hash"] = prev_hash
    precedent_payload["content_hash"] = compute_content_hash(precedent_payload)

    with open(target, "w", encoding="utf-8") as f:
        json.dump(precedent_payload, f, indent=2)
        f.write("\n")
    return target


def _find_precedent_by_id(
    precedent_id: str, ledger_dir: Optional[Path] = None,
) -> Optional[Tuple[Path, Dict[str, Any]]]:
    """Locate a precedent file by its precedent_id. Returns
    (path, payload) or None."""
    for f in _ledger_chain_files(ledger_dir):
        data = _read_precedent_file(f)
        if data and data.get("precedent_id") == precedent_id:
            return f, data
    return None


def amend_precedent(
    prior_precedent_id: str,
    *,
    summary: str,
    new_precedent_id: Optional[str] = None,
    reasoning_overlay: Optional[Dict[str, Any]] = None,
    anchors: Optional[List[Dict[str, Any]]] = None,
    ledger_dir: Optional[Path] = None,
) -> Path:
    """Append an amendment to an existing precedent.

    Amendments are *append-only* — the prior precedent stays in the
    ledger unmodified. The new file carries an `amends` field pointing
    at the prior precedent_id, so the chain of refinement is visible.

    `find_closest` prefers the *latest* version in an amendment chain
    (it walks back through `amends` links and uses the head). Older
    versions remain visible to anyone listing the ledger or auditing
    the history of how a community refined its understanding.

    Args:
      prior_precedent_id: the precedent being refined.
      summary: one-line description of the new framing (required).
      new_precedent_id: stable id for the amendment (auto-generated
        from prior id + timestamp slug if omitted).
      reasoning_overlay: replacement overlay (defaults to the prior's).
      anchors: replacement anchors (defaults to the prior's).

    Raises:
      ValueError if `summary` is missing or the prior precedent isn't
      found.
    """
    if not summary or not summary.strip():
        raise ValueError("`summary` is required for an amendment")

    located = _find_precedent_by_id(prior_precedent_id, ledger_dir)
    if located is None:
        raise ValueError(
            f"prior precedent not found: {prior_precedent_id!r}. "
            "Cannot amend a precedent that isn't in the ledger."
        )
    _prior_path, prior_payload = located

    if new_precedent_id is None:
        # Auto-generate: prior_id with an "-amended-N" suffix where N
        # is the next available amendment count.
        existing_amendments = [
            p for p in _load_precedents(ledger_dir)
            if p.get("amends") == prior_precedent_id
        ]
        n = len(existing_amendments) + 1
        new_precedent_id = f"{prior_precedent_id}-amended-{n}"

    # Inherit fields from the prior unless the caller overrides.
    new_payload = {
        "precedent_id": new_precedent_id,
        "axis": prior_payload.get("axis", "unknown"),
        "dimensions": prior_payload.get("dimensions", []),
        "summary": summary.strip(),
        "anchors": anchors if anchors is not None
                   else prior_payload.get("anchors", []),
        "reasoning_overlay": (
            reasoning_overlay if reasoning_overlay is not None
            else prior_payload.get("reasoning_overlay", {})
        ),
        "amends": prior_precedent_id,
        "sealed_at": time.time(),
    }

    # Determine target path and chain-link this file.
    d = ledger_dir or _default_ledger_dir()
    d.mkdir(parents=True, exist_ok=True)
    file_slug = _slugify(new_precedent_id.replace("ledger://", ""))
    target = d / f"{file_slug}.json"
    if target.exists():
        raise FileExistsError(
            f"amendment file already exists at {target}. "
            "Pass a different new_precedent_id."
        )

    # Chain link: this amendment's prev_hash is the latest file in
    # the chain (highest sealed_at). The new sealed_at = now, so this
    # file always appends at the end.
    existing = [f for f in _ledger_chain_files(d) if f != target]
    if not existing:
        prev_hash = GENESIS_HASH
    else:
        last = existing[-1]
        last_data = _read_precedent_file(last)
        if last_data and "content_hash" in last_data:
            prev_hash = last_data["content_hash"]
        elif last_data:
            prev_hash = compute_content_hash(last_data)
        else:
            prev_hash = GENESIS_HASH

    new_payload["prev_hash"] = prev_hash
    new_payload["content_hash"] = compute_content_hash(new_payload)

    with open(target, "w", encoding="utf-8") as f:
        json.dump(new_payload, f, indent=2)
        f.write("\n")
    return target


def latest_in_amendment_chain(
    precedent_id: str, ledger_dir: Optional[Path] = None,
) -> str:
    """Walk forward through `amends` links to find the most recent
    version of a precedent. Returns the latest precedent_id (which may
    be the input itself if no amendments exist)."""
    precedents = _load_precedents(ledger_dir)
    by_amends: Dict[str, str] = {}
    for p in precedents:
        amend_target = p.get("amends")
        if amend_target:
            by_amends[amend_target] = p["precedent_id"]
    current = precedent_id
    seen = {current}
    while current in by_amends:
        next_id = by_amends[current]
        if next_id in seen:
            break  # cycle protection
        seen.add(next_id)
        current = next_id
    return current


__all__ = [
    "find_closest", "list_precedents", "seal_to_ledger",
    "verify_chain", "compute_content_hash", "GENESIS_HASH",
    "amend_precedent", "latest_in_amendment_chain",
]
