"""Molecular-geometry verifier — VSEPR shape + bond angle from electron domains.

The bridge from the atom (electron configuration -> valence -> bonding domains)
to spatial structure: VSEPR predicts a molecule's geometry and ideal bond angle
from its steric number (bonding domains + lone pairs). This is chemistry's
SPATIAL face — and it co-confirms with pure GEOMETRY (the regular-tetrahedron
central angle is arccos(-1/3) = 109.47°, independent of any chemistry). Two
independent domains, one structure: the SYMMETRY axis (Matt's geometry:chemistry
"Cat:Dog" pair, 2026-06-10).

  * molecular_geometry.vsepr — given bonding_domains + lone_pairs, the predicted
    geometry and ideal bond angle. Deterministic VSEPR table.

VSEPR_VERIFY shape:
    {"bonding_domains": 4, "lone_pairs": 0,
     "claimed_geometry": "tetrahedral", "claimed_bond_angle_deg": 109.47}
"""
from __future__ import annotations

import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error

# (steric_number, lone_pairs) -> (geometry, ideal_bond_angle_deg | None if multi-angle).
# Angles for 0-lone-pair cases are exact ideals; lone-pair cases are nominal
# (electron repulsion compresses them slightly) — checked with a wider tolerance.
_VSEPR: Dict[tuple, tuple] = {
    (2, 0): ("linear", 180.0),
    (3, 0): ("trigonal_planar", 120.0),
    (3, 1): ("bent", 119.0),
    (4, 0): ("tetrahedral", math.degrees(math.acos(-1.0 / 3.0))),  # 109.4712
    (4, 1): ("trigonal_pyramidal", 107.0),
    (4, 2): ("bent", 104.5),
    (5, 0): ("trigonal_bipyramidal", None),   # 90° and 120°
    (5, 1): ("seesaw", None),
    (5, 2): ("t_shaped", None),
    (6, 0): ("octahedral", 90.0),
    (6, 1): ("square_pyramidal", None),
    (6, 2): ("square_planar", 90.0),
}


def verify_vsepr(spec: Dict[str, Any]) -> VerifierResult:
    name = "molecular_geometry.vsepr"
    bd = spec.get("bonding_domains")
    lp = spec.get("lone_pairs", 0)
    claimed_geo = spec.get("claimed_geometry")
    claimed_angle = spec.get("claimed_bond_angle_deg")
    if bd is None or (claimed_geo is None and claimed_angle is None):
        return na(name)
    try:
        bd = int(bd)
        lp = int(lp)
    except (TypeError, ValueError):
        return error(name, "bonding_domains and lone_pairs must be integers")
    if bd < 1 or lp < 0:
        return error(name, "bonding_domains >= 1 and lone_pairs >= 0")
    steric = bd + lp
    entry = _VSEPR.get((steric, lp))
    if entry is None:
        return na(name, f"VSEPR geometry not tabulated for steric={steric}, lone_pairs={lp}")
    geo, angle = entry
    reasons: List[str] = []
    if claimed_geo is not None:
        if str(claimed_geo).strip().lower().replace(" ", "_").replace("-", "_") != geo:
            reasons.append(f"geometry is {geo}, not {claimed_geo!r}")
    if claimed_angle is not None:
        if angle is None:
            reasons.append(f"{geo} has more than one bond angle; no single value")
        else:
            try:
                if abs(float(claimed_angle) - angle) > 1.0:  # 1° tol (rounding + lone-pair nominal)
                    reasons.append(f"ideal bond angle is {angle:.2f} deg, not {claimed_angle}")
            except (TypeError, ValueError):
                reasons.append("claimed_bond_angle_deg not numeric")
    data = {"geometry": geo, "ideal_bond_angle_deg": angle, "steric_number": steric,
            "bonding_domains": bd, "lone_pairs": lp}
    if reasons:
        return mismatch(name, "; ".join(reasons), data)
    detail = f"steric {steric} ({bd} bonding + {lp} lone) -> {geo}"
    if angle is not None:
        detail += f", bond angle {angle:.2f} deg"
    return confirm(name, detail, data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    mv = packet.get("VSEPR_VERIFY") or {}
    results: List[VerifierResult] = []
    if "bonding_domains" in mv and ("claimed_geometry" in mv or "claimed_bond_angle_deg" in mv):
        results.append(verify_vsepr(mv))
    if not results:
        results.append(na("molecular_geometry", "no VSEPR_VERIFY artifacts present"))
    return results
