#!/usr/bin/env python3
"""Build the openFDA NDC drug-directory Layer-0 index (offline, reproducible).

Source: the openFDA National Drug Code (NDC) Directory bulk export
https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip
(manifest: https://api.fda.gov/download.json). License: PUBLIC DOMAIN (U.S. FDA);
openFDA data carries no usage restriction.

Each record is a marketed drug PRODUCT: brand + generic name, active ingredients
(name + strength), dosage form, route, product type (Rx/OTC), DEA schedule, and
pharmacologic class. EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored.

This grounds the medicine verifier and the SERVE mission (the Apothecary -- heal
the sick). IT IS A REFERENCE, NOT MEDICAL ADVICE -- the tool that reads it says so.

Output: lw/00_source/openfda_ndc/drugs.db  (SQLite, query-by-name, low memory)
  drugs (product_ndc, brand_name, generic_name, brand_lc, generic_lc,
         dosage_form, route, product_type, dea_schedule, active_ingredients,
         pharm_class, labeler_name)   -- indexed by brand_lc and generic_lc
  meta  (k, v)

Usage:
  python tools/build_openfda_ndc_index.py --src _tmp_ndc/drug-ndc-0001-of-0001.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with src.open(encoding="utf-8", errors="replace") as f:
        doc = json.load(f)
    results = doc.get("results", [])
    meta_export = doc.get("meta", {}).get("last_updated", "")

    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE drugs (product_ndc TEXT, brand_name TEXT, "
                "generic_name TEXT, brand_lc TEXT, generic_lc TEXT, "
                "dosage_form TEXT, route TEXT, product_type TEXT, "
                "dea_schedule TEXT, active_ingredients TEXT, pharm_class TEXT, "
                "labeler_name TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    rows = []
    n = 0
    for r in results:
        brand = (r.get("brand_name") or "").strip()
        generic = (r.get("generic_name") or "").strip()
        ai = r.get("active_ingredients") or []
        ai_json = json.dumps([{"name": a.get("name"), "strength": a.get("strength")}
                              for a in ai], ensure_ascii=False)
        route = ", ".join(r.get("route") or [])
        pharm = "; ".join(r.get("pharm_class") or [])
        rows.append((
            r.get("product_ndc", ""), brand, generic,
            brand.lower(), generic.lower(),
            (r.get("dosage_form") or "").strip(), route,
            (r.get("product_type") or "").strip(),
            r.get("dea_schedule") or "", ai_json, pharm,
            (r.get("labeler_name") or "").strip(),
        ))
        if len(rows) >= 5000:
            cur.executemany(
                "INSERT INTO drugs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            n += len(rows)
            rows = []
    if rows:
        cur.executemany("INSERT INTO drugs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
        n += len(rows)

    cur.execute("CREATE INDEX idx_brand ON drugs(brand_lc)")
    cur.execute("CREATE INDEX idx_generic ON drugs(generic_lc)")
    meta = {
        "source": "openFDA National Drug Code (NDC) Directory",
        "license": "Public Domain (U.S. FDA / openFDA)",
        "url": "https://open.fda.gov/apis/drug/ndc/",
        "attribution": "Drug product data from openFDA (U.S. FDA NDC Directory), "
                       "public domain.",
        "export": str(meta_export),
        "disclaimer": "REFERENCE ONLY -- not medical advice, not a prescription. "
                      "Drug products as registered with the FDA.",
        "products": str(n),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"products": n, "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="the unzipped drug-ndc JSON")
    ap.add_argument("--out", default="lw/00_source/openfda_ndc/drugs.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("drugs.db built: %s" % out)
    print("  products=%d  (%.1f MB)" % (r["products"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
