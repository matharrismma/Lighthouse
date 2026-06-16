#!/usr/bin/env python3
"""Build the METs (exercise-science) Layer-0 index.

Source: the 2011 Compendium of Physical Activities (Ainsworth et al., a second update
of activity codes and MET intensities), via tfardella/compendium_of_physical_activiy_
mysql_format (https://github.com/tfardella/compendium_of_physical_activiy_mysql_format).
821 activities, each with a 5-digit code, a MET value (metabolic equivalent =
activity energy expenditure / resting), and a category. The Compendium is a public
reference; EXTERNAL Layer-0, attributed, never engine-authored. Grounds exercise_science.

Output: lw/00_source/mets/mets.db  (SQLite)
  activities (code TEXT, met REAL, category TEXT, description TEXT)  -- idx (description)
  meta       (k, v)

Usage:  python tools/build_mets_index.py --src <dir with comp.sql>
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


def _parse_values(s: str):
    """Parse a MySQL `VALUES (...),(...)` body into a list of field-lists,
    respecting single-quoted strings with \\ and '' escapes."""
    rows, i, n = [], 0, len(s)
    while i < n:
        if s[i] != "(":
            i += 1
            continue
        i += 1
        fields, cur, in_str = [], "", False
        while i < n:
            c = s[i]
            if in_str:
                if c == "\\" and i + 1 < n:
                    cur += s[i + 1]; i += 2; continue
                if c == "'":
                    if i + 1 < n and s[i + 1] == "'":
                        cur += "'"; i += 2; continue
                    in_str = False; i += 1; continue
                cur += c; i += 1; continue
            if c == "'":
                in_str = True; i += 1; continue
            if c == ",":
                fields.append(cur.strip()); cur = ""; i += 1; continue
            if c == ")":
                fields.append(cur.strip()); i += 1; break
            cur += c; i += 1
        rows.append(fields)
    return rows


def _insert_body(sql: str, table: str) -> str:
    m = re.search(r"INSERT INTO `%s` VALUES\s*(.*?);" % table, sql, re.S | re.I)
    return m.group(1) if m else ""


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    sql = (src / "comp.sql").read_text(encoding="utf-8", errors="replace")
    cats = {int(r[0]): r[1] for r in _parse_values(_insert_body(sql, "category")) if len(r) >= 2}
    rows = []
    for r in _parse_values(_insert_body(sql, "mets")):
        if len(r) < 4:
            continue
        code = r[0]
        met = None if r[1].upper() in ("NULL", "") else float(r[1])
        cat = cats.get(int(r[2])) if r[2].upper() not in ("NULL", "") else None
        desc = r[3]
        rows.append((code, met, cat, desc))
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE activities (code TEXT, met REAL, category TEXT, description TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO activities VALUES (?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_a ON activities(description)")
    meta = {
        "source": "2011 Compendium of Physical Activities (Ainsworth et al.) -- codes + MET intensities",
        "url": "https://github.com/tfardella/compendium_of_physical_activiy_mysql_format",
        "license": "Public reference (the Compendium of Physical Activities); compiled by U. Arizona",
        "attribution": "2011 Compendium of Physical Activities, Ainsworth BE et al. (Med Sci Sports Exerc)",
        "n_activities": str(len(rows)), "n_categories": str(len(cats)),
        "note": "MET = metabolic equivalent (activity energy expenditure / resting; 1 MET ~ 1 kcal/kg/hr). "
                "Reference data -- not medical or exercise-prescription advice.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"activities": len(rows), "categories": len(cats)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with comp.sql")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "mets" / "mets.db")
    print(build(Path(a.src), out))
    print("wrote", out)
