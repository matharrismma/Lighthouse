"""Food database verifier (USDA FoodData Central).

Loads nutritional facts for common foods from a curated public-domain
seed plus an optional operator-fetched expansion to the full USDA
FoodData Central catalog (~480K foods).

The USDA database is fully public domain (US government works are not
copyrightable). The shipped seed at data/nutrition/foods_seed.jsonl
covers ~80 common foods; the operator can run scripts/fetch_usda.py
to expand to the full SR Legacy / FNDDS dataset.

Checks:
  * food.kcal_match      — claimed kcal per stated amount
  * food.protein_match   — claimed protein grams
  * food.carbs_match     — claimed carbohydrate grams
  * food.fat_match       — claimed fat grams
  * food.fiber_match     — claimed fiber grams

FOOD_VERIFY shape (any subset):
    {
      "food": "brown rice",
      "amount_g": 200,                # optional, default 100
      "claimed_kcal": 224,
      "claimed_protein_g": 5.2,
      "claimed_carbs_g": 47.0,
      "claimed_fat_g": 1.8,
      "claimed_fiber_g": 3.6,
      "rel_tol": 0.1,                 # optional; values vary by source ~10%
    }

Note on tolerance: USDA values are population averages; published
values from different sources differ by ~5-15% routinely. Default
relative tolerance is 10%; checks within that band are CONFIRMED.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


_DATA_DIR = Path(__file__).resolve().parents[2].parent / "data" / "nutrition"
_SOURCES = [
    _DATA_DIR / "foods_full.jsonl",   # operator-fetched (preferred)
    _DATA_DIR / "foods_seed.jsonl",   # shipped seed
]

_CACHE: Dict[str, Any] = {"mtime": 0.0, "by_name": {}, "total": 0}


def _latest_mtime() -> float:
    latest = 0.0
    for p in _SOURCES:
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _load() -> Tuple[Dict[str, Dict[str, Any]], int]:
    mtime = _latest_mtime()
    if _CACHE["by_name"] and mtime <= _CACHE["mtime"]:
        return _CACHE["by_name"], _CACHE["total"]
    by_name: Dict[str, Dict[str, Any]] = {}
    total = 0
    for path in _SOURCES:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    canonical = rec.get("food")
                    if not canonical:
                        continue
                    key = _norm_name(canonical)
                    if key not in by_name:
                        by_name[key] = rec
                        total += 1
                    for alias in rec.get("aliases", []) or []:
                        a_key = _norm_name(alias)
                        if a_key and a_key not in by_name:
                            by_name[a_key] = rec
        except OSError:
            continue
    _CACHE["mtime"] = mtime
    _CACHE["by_name"] = by_name
    _CACHE["total"] = total
    return by_name, total


def total_foods() -> int:
    _, total = _load()
    return total


def lookup(food: str) -> Optional[Dict[str, Any]]:
    """Find a food entry by name or alias. Best-match only — no fuzzy
    ranking (a fuzzy lookup belongs in a separate retrieval layer)."""
    by_name, _ = _load()
    key = _norm_name(food)
    if key in by_name:
        return by_name[key]
    # Last-resort: substring match against canonical names
    for k, v in by_name.items():
        if key and (key in k or k in key):
            return v
    return None


# ── Per-nutrient checks ────────────────────────────────────────────────

_NUTRIENT_KEYS = {
    "kcal":      "kcal_per_100g",
    "protein_g": "protein_g_per_100g",
    "carbs_g":   "carbs_g_per_100g",
    "fat_g":     "fat_g_per_100g",
    "fiber_g":   "fiber_g_per_100g",
}


def _check_nutrient(food_rec: Dict[str, Any], amount_g: float, kind: str,
                    claimed: float, rel_tol: float) -> Tuple[bool, Dict[str, Any]]:
    per_100g_key = _NUTRIENT_KEYS[kind]
    per_100g = food_rec.get(per_100g_key)
    if per_100g is None:
        return True, {"kind": kind, "skipped": "no data for nutrient"}
    actual = float(per_100g) * (amount_g / 100.0)
    threshold = max(0.5, abs(actual) * rel_tol)  # 0.5 absolute floor avoids
                                                  # false MISMATCH near zero
    diff = abs(actual - float(claimed))
    return diff <= threshold, {
        "kind": kind,
        "per_100g": per_100g,
        "amount_g": amount_g,
        "actual": round(actual, 3),
        "claimed": float(claimed),
        "diff": round(diff, 3),
        "tol_abs": round(threshold, 3),
    }


def verify_food_nutrients(spec: Dict[str, Any]) -> VerifierResult:
    name = "food.nutrients"
    food_name = spec.get("food")
    if not food_name:
        return na(name)
    rec = lookup(str(food_name))
    if not rec:
        return mismatch(
            name,
            f"food '{food_name}' not found in seed; consider scripts/fetch_usda.py for full corpus",
            {"food": food_name, "looked_up": False},
        )
    amount_g = float(spec.get("amount_g") or 100)
    rel_tol = float(spec.get("rel_tol") or 0.10)
    if amount_g <= 0:
        return error(name, f"amount_g must be positive, got {amount_g}")

    checks: List[Dict[str, Any]] = []
    any_claimed = False
    mismatches: List[str] = []
    for kind in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g"):
        claimed = spec.get(f"claimed_{kind}")
        if claimed is None:
            continue
        any_claimed = True
        try:
            cl = float(claimed)
        except (TypeError, ValueError):
            return error(name, f"claimed_{kind} must be numeric")
        ok, detail = _check_nutrient(rec, amount_g, kind, cl, rel_tol)
        checks.append({"ok": ok, **detail})
        if not ok:
            mismatches.append(f"{kind}: actual {detail['actual']}, claimed {cl}")
    if not any_claimed:
        return na(name)
    data = {
        "food": rec.get("food"),
        "amount_g": amount_g,
        "rel_tol": rel_tol,
        "checks": checks,
        "source": "USDA FoodData Central (seed); public domain",
    }
    if mismatches:
        return mismatch(name, "; ".join(mismatches), data)
    return confirm(
        name,
        f"{rec.get('food')} @ {amount_g}g: all claimed nutrients match (rel_tol {rel_tol})",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    fv = packet.get("FOOD_VERIFY") or {}
    if fv.get("food") and any(
        f"claimed_{k}" in fv for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g")
    ):
        results.append(verify_food_nutrients(fv))
    if not results:
        results.append(na("food_database"))
    return results
