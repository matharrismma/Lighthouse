#!/usr/bin/env python3
"""Build the nuclides (nuclear-physics) Layer-0 index -- half-lives + decay.

Source: the nuclides dataset bundled in posit-dev/great-tables
(great_tables/data/16-nuclides.csv), compiled from NUBASE2020 + AME2020 (the
evaluated nuclear data). 3,383 nuclides with half-life (seconds), stability, decay
modes + branching, atomic mass, natural abundance. EXTERNAL Layer-0, attributed,
never engine-authored. Grounds nuclear_physics (the half-life VALUES the formula needs).

Output: lw/00_source/nuclides/nuclides.db  (SQLite)
  nuclides (nuclide TEXT, element TEXT, z INT, n INT, a INT, half_life_s REAL,
            is_stable INT, decay_1 TEXT, decay_1_pct TEXT, abundance TEXT,
            atomic_mass TEXT)   -- idx (nuclide), (element,a)
  meta     (k, v)

Usage:  python tools/build_nuclides_index.py --src <dir with nuclides.csv>
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
    rows = []
    with (src / "nuclides.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                z, n = int(r["z"]), int(r["n"])
            except (ValueError, KeyError):
                continue
            el = (r.get("element") or "").strip()
            if not el:
                continue
            a = z + n
            hl = r.get("half_life") or ""
            try:
                hl_s = float(hl) if hl not in ("", "NA") else None
            except ValueError:
                hl_s = None
            rows.append((
                "%s-%d" % (el, a), el, z, n, a, hl_s,
                1 if (r.get("is_stable") or "").upper() == "TRUE" else 0,
                (r.get("decay_1") or "").strip() or None,
                (r.get("decay_1_pct") or "").strip() or None,
                (r.get("abundance") or "").strip() or None,
                (r.get("atomic_mass") or "").strip() or None,
            ))
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE nuclides (nuclide TEXT, element TEXT, z INT, n INT, a INT, "
                "half_life_s REAL, is_stable INT, decay_1 TEXT, decay_1_pct TEXT, "
                "abundance TEXT, atomic_mass TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO nuclides VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_nuc ON nuclides(nuclide)")
    cur.execute("CREATE INDEX idx_ea ON nuclides(element, a)")
    nstable = sum(1 for r in rows if r[6])
    meta = {
        "source": "NUBASE2020 + AME2020 nuclide data (via posit-dev/great-tables nuclides dataset)",
        "url": "https://github.com/posit-dev/great-tables (great_tables/data/16-nuclides.csv)",
        "license": "Evaluated nuclear data (NUBASE/AME, public); dataset MIT (great-tables)",
        "attribution": "NUBASE2020 + AME2020 (evaluated nuclear data); via great-tables",
        "n_nuclides": str(len(rows)), "n_stable": str(nstable),
        "note": "half_life_s in SECONDS (stable -> null + is_stable=1). Grounds nuclear_physics: the "
                "evaluated half-life VALUES the decay formula N=N0*exp(-ln2*t/T) needs. Reference data.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"nuclides": len(rows), "stable": nstable}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with nuclides.csv")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "nuclides" / "nuclides.db")
    print(build(Path(a.src), out))
    print("wrote", out)
