"""Fetch USDA FoodData Central → foods_full.jsonl.

USDA FoodData Central (https://fdc.nal.usda.gov/) publishes the full
SR Legacy and Foundation Foods datasets as bulk CSV/JSON downloads.
US government works are not copyrightable, so this data is fully
public domain.

This script:
  1. Downloads the FoodData Central SR Legacy CSV bundle (~30 MB zip).
  2. Joins foods.csv with nutrients.csv to compute per-100g values.
  3. Writes data/nutrition/foods_full.jsonl in our verifier's schema.

The engine's food_database verifier auto-prefers foods_full.jsonl over
foods_seed.jsonl when present.

Usage:
    python scripts/fetch_usda.py             # full SR Legacy (~7,800 foods)
    python scripts/fetch_usda.py --limit 500 # cap rows for testing
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

# SR Legacy is the historical standard reference dataset; smaller than
# FNDDS and well-curated for whole foods. URL is the bulk-download link
# from FoodData Central. If they relocate it, the operator updates this.
URL = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip"

OUT = Path(__file__).resolve().parent.parent / "data" / "nutrition" / "foods_full.jsonl"


# USDA nutrient IDs we want. From the SR nutrient catalog.
_NUTRIENT_IDS = {
    "208": "kcal_per_100g",        # Energy, kcal
    "203": "protein_g_per_100g",   # Protein
    "204": "fat_g_per_100g",        # Total lipid (fat)
    "205": "carbs_g_per_100g",     # Carbohydrate, by difference
    "291": "fiber_g_per_100g",     # Fiber, total dietary
}


def fetch_zip(url: str) -> bytes:
    print(f"fetching {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "concordance-engine/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return r.read()


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch USDA FoodData Central SR Legacy.")
    p.add_argument("--limit", type=int, default=0, help="cap rows written (0 = no cap)")
    args = p.parse_args()

    try:
        zip_bytes = fetch_zip(URL)
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        print("falling back: leave foods_full.jsonl untouched; engine uses seed", file=sys.stderr)
        return 1

    foods: Dict[str, Dict[str, Optional[str]]] = {}
    food_nutrients: List[Dict[str, str]] = []

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            for name in zf.namelist():
                if name.endswith("food.csv"):
                    with zf.open(name) as fh:
                        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))
                        for row in reader:
                            fdc_id = row.get("fdc_id")
                            description = row.get("description")
                            if fdc_id and description:
                                foods[fdc_id] = {"food": description}
                elif name.endswith("food_nutrient.csv"):
                    with zf.open(name) as fh:
                        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"))
                        for row in reader:
                            nid = row.get("nutrient_id")
                            if nid in _NUTRIENT_IDS:
                                food_nutrients.append(row)
    except Exception as exc:
        print(f"unzip/parse failed: {exc}", file=sys.stderr)
        return 2

    # Attach nutrient values
    for fn in food_nutrients:
        fdc_id = fn.get("fdc_id")
        nid = fn.get("nutrient_id")
        amount = fn.get("amount")
        if fdc_id and nid in _NUTRIENT_IDS and amount:
            try:
                foods.setdefault(fdc_id, {})[_NUTRIENT_IDS[nid]] = float(amount)
            except ValueError:
                continue

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with OUT.open("w", encoding="utf-8") as out:
        out.write('# source: USDA FoodData Central SR Legacy 2018-04 (public domain)\n')
        for fdc_id, data in foods.items():
            if "food" not in data:
                continue
            entry = {"food": data["food"], "fdc_id": fdc_id}
            for k in _NUTRIENT_IDS.values():
                entry[k] = data.get(k)
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            n += 1
            if args.limit and n >= args.limit:
                break
    print(f"wrote {n} foods to {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
