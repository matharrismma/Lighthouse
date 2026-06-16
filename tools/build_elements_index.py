#!/usr/bin/env python3
"""Build the chemical-elements (chemistry) Layer-0 index -- the periodic table.

Source: Bowserinator/Periodic-Table-JSON (https://github.com/Bowserinator/Periodic-Table-JSON),
a clean JSON of all 118 elements with IUPAC standard atomic weights, plus symbol, name,
number, category, block, group, period, phase, density, melt/boil, electronegativity,
and electron configuration. Atomic weights are the IUPAC evaluated values. EXTERNAL
Layer-0, attributed, never engine-authored. Grounds chemistry -- the atomic-weight VALUES
that molar-mass computation needs.

Output: lw/00_source/elements/elements.db  (SQLite)
  elements (number INT, symbol TEXT, name TEXT, atomic_mass REAL, category TEXT,
            block TEXT, grp INT, period INT, phase TEXT, density REAL, melt_k REAL,
            boil_k REAL, electronegativity REAL, electron_config TEXT)  -- idx (symbol),(name)
  meta     (k, v)

Usage:  python tools/build_elements_index.py --src <dir with pt.json>
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def _f(x):
    try:
        return float(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def _i(x):
    try:
        return int(x) if x is not None else None
    except (TypeError, ValueError):
        return None


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    data = json.loads((src / "pt.json").read_text(encoding="utf-8"))
    els = data.get("elements") if isinstance(data, dict) else data
    rows = []
    for e in els:
        sym = (e.get("symbol") or "").strip()
        am = _f(e.get("atomic_mass"))
        if not sym or am is None:
            continue
        rows.append((
            _i(e.get("number")), sym, (e.get("name") or "").strip(), am,
            (e.get("category") or "").strip() or None, (e.get("block") or "").strip() or None,
            _i(e.get("group")), _i(e.get("period")), (e.get("phase") or "").strip() or None,
            _f(e.get("density")), _f(e.get("melt")), _f(e.get("boil")),
            _f(e.get("electronegativity_pauling")),
            (e.get("electron_configuration") or "").strip() or None,
        ))
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE elements (number INT, symbol TEXT, name TEXT, atomic_mass REAL, "
                "category TEXT, block TEXT, grp INT, period INT, phase TEXT, density REAL, "
                "melt_k REAL, boil_k REAL, electronegativity REAL, electron_config TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO elements VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_sym ON elements(symbol)")
    cur.execute("CREATE INDEX idx_name ON elements(name)")
    meta = {
        "source": "Periodic table with IUPAC standard atomic weights (Bowserinator/Periodic-Table-JSON)",
        "url": "https://github.com/Bowserinator/Periodic-Table-JSON",
        "license": "CC-BY-SA-3.0 (Periodic-Table-JSON); atomic weights are IUPAC evaluated values",
        "attribution": "Periodic-Table-JSON (Bowserinator), CC BY-SA; atomic weights per IUPAC",
        "n_elements": str(len(rows)),
        "note": "IUPAC standard atomic weights + element properties. Grounds chemistry: the atomic-"
                "weight VALUES molar-mass computation needs (molar_mass + element_data tools).",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"elements": len(rows)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with pt.json")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "elements" / "elements.db")
    print(build(Path(a.src), out))
    print("wrote", out)
