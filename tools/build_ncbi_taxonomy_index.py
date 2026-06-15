#!/usr/bin/env python3
"""Build the NCBI Taxonomy Layer-0 index (offline, reproducible).

Source: the NCBI Taxonomy database (taxdump: names.dmp + nodes.dmp) from
https://ftp.ncbi.nlm.nih.gov/pub/taxonomy/taxdump.tar.gz . The NCBI Taxonomy is
the standard nomenclature/classification for organisms in the public sequence
databases. License: U.S. public domain (NCBI/NLM); acknowledge NCBI.

EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored. Grounds the
biology/ecology/genetics verifiers and the species-identity thread of the SERVE
mission (knowing the scientific name + lineage of a herb / food / organism --
e.g. "tomato = Solanum lycopersicum").

Output: lw/00_source/ncbi_taxonomy/taxonomy.db  (SQLite, query-by-name)
  taxa     (taxid INTEGER PRIMARY KEY, sci_name, sci_name_lc, rank, parent)
           -- one row per taxon; lineage walked via parent links
  altnames (taxid INTEGER, name, name_lc, name_class)   -- common/synonym only
  meta     (k, v)

Usage:
  python tools/build_ncbi_taxonomy_index.py --src _tmp_tax
"""
from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

# alternative-name classes worth searching (drop authority/type-material noise)
_ALT_CLASSES = {"synonym", "genbank common name", "common name", "equivalent name"}


def _parse(line: str):
    return [c.strip() for c in line.rstrip("\n").rstrip("|").split("\t|")]


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()

    # nodes.dmp -> taxid -> (parent, rank)
    nodes = {}
    with (src / "nodes.dmp").open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            p = _parse(ln)
            if len(p) >= 3 and p[0].isdigit():
                nodes[int(p[0])] = (int(p[1]) if p[1].isdigit() else 0, p[2])

    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE taxa (taxid INTEGER PRIMARY KEY, sci_name TEXT, "
                "sci_name_lc TEXT, rank TEXT, parent INTEGER)")
    cur.execute("CREATE TABLE altnames (taxid INTEGER, name TEXT, name_lc TEXT, "
                "name_class TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    sci = {}        # taxid -> scientific name
    alt_batch = []
    n_alt = 0
    with (src / "names.dmp").open(encoding="utf-8", errors="replace") as f:
        for ln in f:
            p = _parse(ln)
            if len(p) < 4 or not p[0].isdigit():
                continue
            taxid = int(p[0])
            name, cls = p[1], p[3]
            if cls == "scientific name":
                sci[taxid] = name
            elif cls in _ALT_CLASSES:
                alt_batch.append((taxid, name, name.lower(), cls))
                if len(alt_batch) >= 10000:
                    cur.executemany(
                        "INSERT INTO altnames VALUES (?,?,?,?)", alt_batch)
                    n_alt += len(alt_batch)
                    alt_batch = []
    if alt_batch:
        cur.executemany("INSERT INTO altnames VALUES (?,?,?,?)", alt_batch)
        n_alt += len(alt_batch)

    tax_batch = []
    n_tax = 0
    for taxid, (parent, rank) in nodes.items():
        s = sci.get(taxid, "")
        tax_batch.append((taxid, s, s.lower(), rank, parent))
        if len(tax_batch) >= 10000:
            cur.executemany("INSERT INTO taxa VALUES (?,?,?,?,?)", tax_batch)
            n_tax += len(tax_batch)
            tax_batch = []
    if tax_batch:
        cur.executemany("INSERT INTO taxa VALUES (?,?,?,?,?)", tax_batch)
        n_tax += len(tax_batch)

    cur.execute("CREATE INDEX idx_sci ON taxa(sci_name_lc)")
    cur.execute("CREATE INDEX idx_alt ON altnames(name_lc)")
    meta = {
        "source": "NCBI Taxonomy (taxdump)",
        "license": "Public Domain (U.S. NCBI / NLM)",
        "url": "https://www.ncbi.nlm.nih.gov/taxonomy",
        "attribution": "Taxonomy from the NCBI Taxonomy database, public domain "
                       "(acknowledge NCBI/NLM).",
        "taxa": str(n_tax), "altnames": str(n_alt),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"taxa": n_tax, "altnames": n_alt, "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_tax",
                    help="dir with names.dmp and nodes.dmp")
    ap.add_argument("--out", default="lw/00_source/ncbi_taxonomy/taxonomy.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("taxonomy.db built: %s" % out)
    print("  taxa=%d altnames=%d  (%.1f MB)" % (
        r["taxa"], r["altnames"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
