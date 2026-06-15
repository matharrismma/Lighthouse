#!/usr/bin/env python3
"""Build the USDA FoodData Central Layer-0 index (offline, reproducible).

Source: USDA FoodData Central, SR Legacy food dataset (the classic standard
reference, 7,793 foods), CSV bulk download from
https://fdc.nal.usda.gov/download-datasets .
License: PUBLIC DOMAIN (U.S. Government work).

Relational model: food.csv (fdc_id, description) JOIN food_nutrient.csv
(fdc_id, nutrient_id, amount) JOIN nutrient.csv (id, name, unit_name). All
nutrient amounts are PER 100 g of the food as analyzed.

EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored. Grounds the
nutrition verifier and the SERVE mission (the Table -- feed the hungry):
"how many kcal / how much protein in 100 g of X".

Output: lw/00_source/usda/usda.db  (SQLite, query-by-key, low memory)
  foods          (fdc_id INTEGER PRIMARY KEY, description, desc_lc, category)
  nutrients      (id INTEGER PRIMARY KEY, name, unit)
  food_nutrients (fdc_id INTEGER, nutrient_id INTEGER, amount REAL)  idx fdc_id
  meta           (k, v)

Usage:
  python tools/build_usda_index.py --src _tmp_usda/FoodData_Central_sr_legacy_food_csv_2018-04
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _i(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE foods (fdc_id INTEGER PRIMARY KEY, description "
                "TEXT, desc_lc TEXT, category INTEGER)")
    cur.execute("CREATE TABLE nutrients (id INTEGER PRIMARY KEY, name TEXT, unit TEXT)")
    cur.execute("CREATE TABLE food_nutrients (fdc_id INTEGER, nutrient_id "
                "INTEGER, amount REAL)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    # foods
    n_food = 0
    with (src / "food.csv").open(encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        rows = []
        for row in r:
            fid = _i(row.get("fdc_id"))
            if fid is None:
                continue
            desc = (row.get("description") or "").strip()
            rows.append((fid, desc, desc.lower(), _i(row.get("food_category_id"))))
        cur.executemany("INSERT OR REPLACE INTO foods VALUES (?,?,?,?)", rows)
        n_food = len(rows)

    # nutrients
    n_nut = 0
    with (src / "nutrient.csv").open(encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        rows = []
        for row in r:
            nid = _i(row.get("id"))
            if nid is None:
                continue
            rows.append((nid, (row.get("name") or "").strip(),
                         (row.get("unit_name") or "").strip()))
        cur.executemany("INSERT OR REPLACE INTO nutrients VALUES (?,?,?)", rows)
        n_nut = len(rows)

    # food_nutrients
    n_fn = 0
    with (src / "food_nutrient.csv").open(encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f)
        batch = []
        for row in r:
            fid = _i(row.get("fdc_id"))
            nid = _i(row.get("nutrient_id"))
            amt = _f(row.get("amount"))
            if fid is None or nid is None or amt is None:
                continue
            batch.append((fid, nid, amt))
            if len(batch) >= 10000:
                cur.executemany("INSERT INTO food_nutrients VALUES (?,?,?)", batch)
                n_fn += len(batch)
                batch = []
        if batch:
            cur.executemany("INSERT INTO food_nutrients VALUES (?,?,?)", batch)
            n_fn += len(batch)

    cur.execute("CREATE INDEX idx_desc ON foods(desc_lc)")
    cur.execute("CREATE INDEX idx_fn ON food_nutrients(fdc_id)")
    meta = {
        "source": "USDA FoodData Central -- SR Legacy (Standard Reference)",
        "license": "Public Domain (U.S. Government)",
        "url": "https://fdc.nal.usda.gov/download-datasets",
        "attribution": "Nutrient data from USDA FoodData Central, SR Legacy; "
                       "public domain.",
        "basis": "all amounts are per 100 g of the food, as analyzed",
        "foods": str(n_food), "nutrients": str(n_nut),
        "food_nutrients": str(n_fn),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"foods": n_food, "nutrients": n_nut, "food_nutrients": n_fn,
            "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True,
                    help="the unzipped SR Legacy csv dir (has food.csv etc.)")
    ap.add_argument("--out", default="lw/00_source/usda/usda.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("usda.db built: %s" % out)
    print("  foods=%d nutrients=%d food_nutrients=%d  (%.1f MB)" % (
        r["foods"], r["nutrients"], r["food_nutrients"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
