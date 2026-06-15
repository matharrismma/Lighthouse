#!/usr/bin/env python3
"""Build the DrugCentral drug-target Layer-0 index (offline, reproducible).

Source: DrugCentral drug.target.interaction.tsv (the curated drug -> molecular
target bioactivity set), from https://drugcentral.org/download
(file: unmtid-dbs.net/download/DrugCentral/2021_09_01/drug.target.interaction.tsv.gz).
License: CC BY-SA 4.0, (c) DrugCentral / Univ. of New Mexico.

Each row = a measured drug->target interaction: the protein/gene the drug acts
on, the pharmacological action (INHIBITOR / AGONIST / ANTAGONIST ...), and a
mechanism-of-action (MOA) flag. This is the MECHANISM layer of the Apothecary
("how does drug X work / what does it act on"). 2,587 drugs.

EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored. REFERENCE, not
medical advice. Coverage is partial (drugs with measured target data).

Output: lw/00_source/drugcentral/drug_targets.db  (SQLite, query-by-name)
  targets (drug_name, drug_lc, target_name, target_class, gene, swissprot,
           act_type, act_value, moa, action_type, organism)  -- idx drug_lc
  meta    (k, v)

Usage:
  python tools/build_drugcentral_index.py --src <dir-with drug.target.interaction.tsv>
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE targets (drug_name TEXT, drug_lc TEXT, "
                "target_name TEXT, target_class TEXT, gene TEXT, swissprot TEXT, "
                "act_type TEXT, act_value TEXT, moa TEXT, action_type TEXT, "
                "organism TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    n = 0
    drugs = set()
    rows = []
    with (src / "drug.target.interaction.tsv").open(encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t", quotechar='"')
        for row in r:
            dn = (row.get("DRUG_NAME") or "").strip()
            if not dn:
                continue
            drugs.add(dn.lower())
            rows.append((
                dn, dn.lower(),
                (row.get("TARGET_NAME") or "").strip(),
                (row.get("TARGET_CLASS") or "").strip(),
                (row.get("GENE") or "").strip(),
                (row.get("SWISSPROT") or "").strip(),
                (row.get("ACT_TYPE") or "").strip(),
                (row.get("ACT_VALUE") or "").strip(),
                (row.get("MOA") or "").strip(),
                (row.get("ACTION_TYPE") or "").strip(),
                (row.get("ORGANISM") or "").strip(),
            ))
            if len(rows) >= 5000:
                cur.executemany(
                    "INSERT INTO targets VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
                n += len(rows)
                rows = []
    if rows:
        cur.executemany("INSERT INTO targets VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        n += len(rows)

    cur.execute("CREATE INDEX idx_drug ON targets(drug_lc)")
    meta = {
        "source": "DrugCentral drug-target interactions",
        "license": "CC BY-SA 4.0",
        "url": "https://drugcentral.org/download",
        "attribution": "Drug-target data from DrugCentral (Univ. of New Mexico), "
                       "CC BY-SA 4.0.",
        "disclaimer": "REFERENCE ONLY -- not medical advice. Measured bioactivity "
                      "/ mechanism data; coverage is partial.",
        "interactions": str(n), "drugs": str(len(drugs)),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"interactions": n, "drugs": len(drugs), "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True,
                    help="dir containing drug.target.interaction.tsv")
    ap.add_argument("--out", default="lw/00_source/drugcentral/drug_targets.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("drug_targets.db built: %s" % out)
    print("  interactions=%d drugs=%d  (%.1f MB)" % (
        r["interactions"], r["drugs"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
