"""Agriculture verifier.

Deterministic checks against public-domain agricultural reference data:
USDA hardiness zones, crop pH tolerance ranges, plant-family-based crop
rotation rules, and per-acre stocking density bounds.

All embedded reference data is public-domain or freely redistributable
(USDA / NRCS / Cooperative Extension publications). No external dataset
download is required — the verifier is self-contained.

Checks performed:

  * agriculture.hardiness_zone_match
      A claimed USDA hardiness zone is within the crop's documented
      tolerance range.
  * agriculture.soil_ph_match
      A claimed soil pH is within the crop's documented preferred range.
  * agriculture.rotation_compatible
      A proposed crop rotation does not place crops from the same
      botanical family in successive years (the most common deterministic
      rule for disease/nutrient management).
  * agriculture.stocking_density
      A claimed per-acre animal stocking matches recommended bounds.

AG_VERIFY packet shape (any subset of fields):
    {
      "crop": "tomato",                        # for hardiness/ph checks
      "claimed_zone": "7b",                    # hardiness_zone_match (paired with crop)
      "soil_ph": 6.5,                          # soil_ph_match (paired with crop)
      "rotation": ["tomato", "potato"],        # rotation_compatible
      "animal": "cattle_beef",                 # stocking_density (paired with stocking_per_acre)
      "stocking_per_acre": 1.0,
      "acreage": 10.0,                         # optional context
    }
"""
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


# ── Reference data (public-domain) ─────────────────────────────────────

# USDA Plant Hardiness Zones — 1a (coldest) through 13b (warmest).
# Each zone is a 5-degree-F band; the half-zones (a/b) split each 10-degree zone.
# Source: USDA Plant Hardiness Zone Map (public domain).
_VALID_ZONE = re.compile(r"^([1-9]|1[0-3])[ab]?$")

# Crop hardiness tolerance: (min_zone_num, max_zone_num) where each is
# encoded as zone * 2 (so 7a = 14, 7b = 15) for fine-grained comparison.
# Sources: USDA Cooperative Extension publications, public domain.
def _zone_to_int(zone: str) -> Optional[int]:
    """7a -> 14, 7b -> 15, 7 -> 14 (default to 'a'). None for invalid."""
    z = zone.lower().strip()
    m = _VALID_ZONE.match(z)
    if not m:
        return None
    base = int(m.group(1))
    half = z[-1] if z[-1] in ("a", "b") else "a"
    return base * 2 + (0 if half == "a" else 1)


# Crop name -> (min_zone_int, max_zone_int).
# Conservative ranges from common Cooperative Extension sources.
_CROP_HARDINESS: Dict[str, Tuple[int, int]] = {
    "apple":          (_zone_to_int("3a") or 6,  _zone_to_int("8b") or 17),
    "blueberry":      (_zone_to_int("3a") or 6,  _zone_to_int("8b") or 17),
    "cabbage":        (_zone_to_int("3a") or 6,  _zone_to_int("9b") or 19),
    "carrot":         (_zone_to_int("3a") or 6,  _zone_to_int("10b") or 21),
    "citrus":         (_zone_to_int("9a") or 18, _zone_to_int("11b") or 23),
    "corn":           (_zone_to_int("4a") or 8,  _zone_to_int("11b") or 23),
    "cotton":         (_zone_to_int("7a") or 14, _zone_to_int("11b") or 23),
    "lettuce":        (_zone_to_int("3a") or 6,  _zone_to_int("11b") or 23),
    "olive":          (_zone_to_int("8a") or 16, _zone_to_int("11b") or 23),
    "peach":          (_zone_to_int("5a") or 10, _zone_to_int("9b") or 19),
    "pecan":          (_zone_to_int("6a") or 12, _zone_to_int("9b") or 19),
    "pepper":         (_zone_to_int("4a") or 8,  _zone_to_int("11b") or 23),
    "potato":         (_zone_to_int("3a") or 6,  _zone_to_int("10b") or 21),
    "rice":           (_zone_to_int("8a") or 16, _zone_to_int("10b") or 21),
    "soybean":        (_zone_to_int("4a") or 8,  _zone_to_int("9b") or 19),
    "strawberry":     (_zone_to_int("3a") or 6,  _zone_to_int("10b") or 21),
    "sweet_potato":   (_zone_to_int("6a") or 12, _zone_to_int("11b") or 23),
    "tomato":         (_zone_to_int("4a") or 8,  _zone_to_int("11b") or 23),
    "wheat":          (_zone_to_int("3a") or 6,  _zone_to_int("9b") or 19),
}

# Crop name -> (preferred_pH_min, preferred_pH_max).
# Source: Cooperative Extension soil-pH crop guides (public domain).
_CROP_PH: Dict[str, Tuple[float, float]] = {
    "apple":        (6.0, 7.0),
    "blueberry":    (4.5, 5.5),
    "cabbage":      (6.0, 7.5),
    "carrot":       (6.0, 6.8),
    "citrus":       (6.0, 7.5),
    "corn":         (5.8, 7.0),
    "cotton":       (5.8, 6.5),
    "lettuce":      (6.0, 7.0),
    "olive":        (6.5, 8.0),
    "peach":        (6.0, 7.0),
    "pecan":        (6.0, 7.0),
    "pepper":       (5.5, 7.0),
    "potato":       (5.0, 6.5),
    "rice":         (5.5, 6.5),
    "soybean":      (6.0, 7.0),
    "strawberry":   (5.5, 6.8),
    "sweet_potato": (5.5, 6.5),
    "tomato":       (6.0, 6.8),
    "wheat":        (6.0, 7.0),
}

# Crop -> botanical family. Rotation rule: don't follow a crop with another
# from the same family. Public-domain (basic taxonomy).
_CROP_FAMILY: Dict[str, str] = {
    "tomato":       "solanaceae",
    "potato":       "solanaceae",
    "pepper":       "solanaceae",
    "eggplant":     "solanaceae",
    "tobacco":      "solanaceae",
    "cabbage":      "brassicaceae",
    "broccoli":     "brassicaceae",
    "cauliflower":  "brassicaceae",
    "kale":         "brassicaceae",
    "radish":       "brassicaceae",
    "turnip":       "brassicaceae",
    "soybean":      "fabaceae",
    "bean":         "fabaceae",
    "pea":          "fabaceae",
    "lentil":       "fabaceae",
    "peanut":       "fabaceae",
    "clover":       "fabaceae",
    "alfalfa":      "fabaceae",
    "cucumber":     "cucurbitaceae",
    "squash":       "cucurbitaceae",
    "melon":        "cucurbitaceae",
    "watermelon":   "cucurbitaceae",
    "pumpkin":      "cucurbitaceae",
    "corn":         "poaceae",
    "wheat":        "poaceae",
    "rice":         "poaceae",
    "oat":          "poaceae",
    "barley":       "poaceae",
    "rye":          "poaceae",
    "sorghum":      "poaceae",
    "sugarcane":    "poaceae",
    "lettuce":      "asteraceae",
    "sunflower":    "asteraceae",
    "artichoke":    "asteraceae",
    "carrot":       "apiaceae",
    "celery":       "apiaceae",
    "parsley":      "apiaceae",
    "onion":        "amaryllidaceae",
    "garlic":       "amaryllidaceae",
    "leek":         "amaryllidaceae",
    "spinach":      "amaranthaceae",
    "beet":         "amaranthaceae",
    "swiss_chard":  "amaranthaceae",
    "strawberry":   "rosaceae",
    "apple":        "rosaceae",
    "peach":        "rosaceae",
    "blueberry":    "ericaceae",
    "cotton":       "malvaceae",
    "okra":         "malvaceae",
    "sweet_potato": "convolvulaceae",
}

# Animal type -> (min_per_acre, max_per_acre) recommended stocking.
# Sources: USDA NRCS / Cooperative Extension grazing guides, public domain.
# Ranges are continental-US conservative; varies widely by region/forage.
_STOCKING_BOUNDS: Dict[str, Tuple[float, float]] = {
    "cattle_beef":   (0.25, 2.0),    # cow-calf pairs/acre
    "cattle_dairy":  (0.5, 1.5),
    "sheep":         (2.0, 8.0),     # ewe/acre
    "goat":          (2.0, 10.0),
    "horse":         (0.25, 1.0),
    "swine_pasture": (5.0, 25.0),
    "chicken_pastured": (50.0, 500.0),
    "duck":          (50.0, 200.0),
    "rabbit":        (100.0, 500.0),
}


# ── Verifiers ──────────────────────────────────────────────────────────

def verify_hardiness_zone(spec: Dict[str, Any]) -> VerifierResult:
    name = "agriculture.hardiness_zone_match"
    crop = (spec.get("crop") or "").lower().strip()
    claimed_zone = spec.get("claimed_zone")
    if not crop or not claimed_zone:
        return na(name)
    z_int = _zone_to_int(str(claimed_zone))
    if z_int is None:
        return error(name,
                     f"claimed_zone {claimed_zone!r} is not a valid USDA hardiness zone "
                     f"(expected '1a' through '13b')")
    if crop not in _CROP_HARDINESS:
        return na(name, f"no hardiness data for crop {crop!r} in reference table")
    lo, hi = _CROP_HARDINESS[crop]
    if lo <= z_int <= hi:
        return confirm(name,
                       f"{crop!r} is hardy in zone {claimed_zone} (range zones "
                       f"{_int_to_zone(lo)}–{_int_to_zone(hi)})",
                       {"crop": crop, "zone": str(claimed_zone),
                        "tolerance_low": _int_to_zone(lo), "tolerance_high": _int_to_zone(hi)})
    return mismatch(name,
                    f"{crop!r} is not hardy in zone {claimed_zone} — tolerance is zones "
                    f"{_int_to_zone(lo)}–{_int_to_zone(hi)}",
                    {"crop": crop, "zone": str(claimed_zone),
                     "tolerance_low": _int_to_zone(lo), "tolerance_high": _int_to_zone(hi)})


def _int_to_zone(z: int) -> str:
    base = z // 2
    half = "a" if z % 2 == 0 else "b"
    return f"{base}{half}"


def verify_soil_ph(spec: Dict[str, Any]) -> VerifierResult:
    name = "agriculture.soil_ph_match"
    crop = (spec.get("crop") or "").lower().strip()
    claimed_ph = spec.get("soil_ph")
    if not crop or claimed_ph is None:
        return na(name)
    try:
        ph = float(claimed_ph)
    except (TypeError, ValueError):
        return error(name, f"soil_ph must be numeric, got {claimed_ph!r}")
    if not (0.0 <= ph <= 14.0):
        return error(name, f"soil_ph {ph} out of physical range [0, 14]")
    if crop not in _CROP_PH:
        return na(name, f"no soil-pH data for crop {crop!r} in reference table")
    lo, hi = _CROP_PH[crop]
    if lo <= ph <= hi:
        return confirm(name,
                       f"{crop!r} grows well at pH {ph} (preferred range {lo}–{hi})",
                       {"crop": crop, "ph": ph, "preferred_min": lo, "preferred_max": hi})
    return mismatch(name,
                    f"{crop!r} prefers pH {lo}–{hi}, claim is {ph} ({'too acidic' if ph < lo else 'too alkaline'})",
                    {"crop": crop, "ph": ph, "preferred_min": lo, "preferred_max": hi})


def verify_rotation(spec: Dict[str, Any]) -> VerifierResult:
    name = "agriculture.rotation_compatible"
    rotation = spec.get("rotation")
    if not rotation:
        return na(name)
    if not isinstance(rotation, (list, tuple)) or len(rotation) < 2:
        return na(name, "rotation must be a list of >= 2 crops")
    crops = [str(c).lower().strip() for c in rotation]
    families = []
    unknown = []
    for c in crops:
        fam = _CROP_FAMILY.get(c)
        if fam is None:
            unknown.append(c)
        families.append(fam)
    if unknown:
        return na(name, f"unknown crop families for: {unknown} — cannot evaluate rotation")
    # Adjacent same-family pairs are the failure.
    bad_pairs = []
    for i in range(len(families) - 1):
        if families[i] and families[i] == families[i + 1]:
            bad_pairs.append((crops[i], crops[i + 1], families[i]))
    if not bad_pairs:
        return confirm(name,
                       f"rotation {crops} has no adjacent same-family pairs",
                       {"rotation": crops, "families": families})
    detail = "; ".join(f"{a}→{b} (both {fam})" for a, b, fam in bad_pairs)
    return mismatch(name,
                    f"rotation contains adjacent same-family pairs: {detail}",
                    {"rotation": crops, "families": families, "bad_pairs": bad_pairs})


def verify_stocking_density(spec: Dict[str, Any]) -> VerifierResult:
    name = "agriculture.stocking_density"
    animal = (spec.get("animal") or "").lower().strip()
    per_acre = spec.get("stocking_per_acre")
    if not animal or per_acre is None:
        return na(name)
    try:
        per = float(per_acre)
    except (TypeError, ValueError):
        return error(name, f"stocking_per_acre must be numeric, got {per_acre!r}")
    if per < 0:
        return error(name, f"stocking_per_acre cannot be negative ({per})")
    if animal not in _STOCKING_BOUNDS:
        return na(name, f"no stocking-density data for animal {animal!r} in reference table")
    lo, hi = _STOCKING_BOUNDS[animal]
    if lo <= per <= hi:
        return confirm(name,
                       f"{animal!r} stocking {per}/acre within recommended range {lo}–{hi}",
                       {"animal": animal, "per_acre": per, "min": lo, "max": hi})
    side = "below" if per < lo else "above"
    return mismatch(name,
                    f"{animal!r} stocking {per}/acre is {side} recommended range {lo}–{hi}",
                    {"animal": animal, "per_acre": per, "min": lo, "max": hi})


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch every applicable agriculture check for the AG_VERIFY block."""
    results: List[VerifierResult] = []
    av = packet.get("AG_VERIFY") or {}

    if "claimed_zone" in av:
        results.append(verify_hardiness_zone(av))
    if "soil_ph" in av:
        results.append(verify_soil_ph(av))
    if "rotation" in av:
        results.append(verify_rotation(av))
    if "stocking_per_acre" in av:
        results.append(verify_stocking_density(av))

    if not results:
        results.append(na("agriculture", "no AG_VERIFY artifacts present"))
    return results
