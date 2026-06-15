#!/usr/bin/env python3
"""Build the internet-protocols Layer-0 index (offline, reproducible).

Two authoritative, PUBLIC-DOMAIN registries of how the internet is defined:
  * IANA Service Name and Transport Protocol Port Number Registry
    https://www.iana.org/assignments/service-names-port-numbers/
    (service-names-port-numbers.csv) -- port <-> service (e.g. 443/tcp = https).
  * The RFC Index (RFC Editor / IETF)
    https://www.ietf.org/rfc/rfc-index.xml -- RFC number -> title, status, date,
    and obsoletes/obsoleted-by/updates/updated-by links (e.g. RFC 9113 = HTTP/2,
    obsoletes RFC 7540).

EXTERNAL, ATTRIBUTED data -- Layer-0, never engine-authored. Grounds the
networking and cryptography verifiers and "which RFC defines X" (with the
obsolete chain so a superseded RFC is flagged).

Output: lw/00_source/protocols/protocols.db  (SQLite, query-by-key, low memory)
  ports (port INTEGER, protocol TEXT, service TEXT, description TEXT, reference TEXT)
  rfcs  (num INTEGER, doc_id TEXT, title TEXT, status TEXT, date TEXT,
         obsoletes TEXT, obsoleted_by TEXT, updates TEXT, updated_by TEXT)
  meta  (k, v)

Usage:
  python tools/build_protocols_index.py --src _tmp_iana
"""
from __future__ import annotations

import argparse
import csv
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path


def _tag(e):
    return e.tag.split("}")[-1]


def _build_ports(cur, path: Path) -> int:
    n = 0
    rows = []
    with path.open(encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        next(r, None)  # header
        for row in r:
            if len(row) < 4:
                continue
            service, port, proto, desc = row[0], row[1], row[2], row[3]
            ref = row[8] if len(row) > 8 else ""
            if not port or not port.isdigit() or not proto:
                continue  # skip ranges / reserved / unspecified protocol
            rows.append((int(port), proto.strip().lower(), service.strip(),
                         desc.strip(), ref.strip()))
    cur.executemany("INSERT INTO ports VALUES (?,?,?,?,?)", rows)
    n = len(rows)
    cur.execute("CREATE INDEX idx_port ON ports(port)")
    cur.execute("CREATE INDEX idx_service ON ports(service)")
    return n


def _doc_num(doc_id: str):
    digits = "".join(ch for ch in doc_id if ch.isdigit())
    return int(digits) if digits else None


def _build_rfcs(cur, path: Path) -> int:
    root = ET.parse(str(path)).getroot()
    rows = []
    for e in root:
        if _tag(e) != "rfc-entry":
            continue
        rec = {"doc_id": "", "title": "", "status": "", "date": "",
               "obsoletes": "", "obsoleted_by": "", "updates": "", "updated_by": ""}
        for c in e:
            ct = _tag(c)
            if ct == "doc-id":
                rec["doc_id"] = (c.text or "").strip()
            elif ct == "title":
                rec["title"] = (c.text or "").strip()
            elif ct == "current-status":
                rec["status"] = (c.text or "").strip()
            elif ct == "date":
                mon = "".join(g.text or "" for g in c if _tag(g) == "month")
                yr = "".join(g.text or "" for g in c if _tag(g) == "year")
                rec["date"] = (mon + " " + yr).strip()
            elif ct in ("obsoletes", "obsoleted-by", "updates", "updated-by"):
                ids = ",".join((g.text or "").strip() for g in c
                               if _tag(g) == "doc-id")
                rec[ct.replace("-", "_")] = ids
        num = _doc_num(rec["doc_id"])
        if num is None:
            continue
        rows.append((num, rec["doc_id"], rec["title"], rec["status"],
                     rec["date"], rec["obsoletes"], rec["obsoleted_by"],
                     rec["updates"], rec["updated_by"]))
    cur.executemany(
        "INSERT INTO rfcs VALUES (?,?,?,?,?,?,?,?,?)", rows)
    cur.execute("CREATE INDEX idx_num ON rfcs(num)")
    return len(rows)


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE ports (port INTEGER, protocol TEXT, service TEXT, "
                "description TEXT, reference TEXT)")
    cur.execute("CREATE TABLE rfcs (num INTEGER, doc_id TEXT, title TEXT, "
                "status TEXT, date TEXT, obsoletes TEXT, obsoleted_by TEXT, "
                "updates TEXT, updated_by TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    n_ports = _build_ports(cur, src / "ports.csv")
    n_rfcs = _build_rfcs(cur, src / "rfc-index.xml")

    meta = {
        "ports_source": "IANA Service Name and Transport Protocol Port Number Registry",
        "ports_license": "Public Domain (IANA)",
        "ports_url": "https://www.iana.org/assignments/service-names-port-numbers/",
        "rfc_source": "The RFC Index (RFC Editor / IETF)",
        "rfc_license": "Public Domain (IETF Trust / RFC Editor)",
        "rfc_url": "https://www.rfc-editor.org/",
        "attribution": "Port assignments (c) IANA; RFC index (c) IETF/RFC Editor; "
                       "both public domain.",
        "ports": str(n_ports),
        "rfcs": str(n_rfcs),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"ports": n_ports, "rfcs": n_rfcs, "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_iana",
                    help="dir with ports.csv and rfc-index.xml")
    ap.add_argument("--out", default="lw/00_source/protocols/protocols.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("protocols.db built: %s" % out)
    print("  ports=%d rfcs=%d  (%.1f MB)" % (
        r["ports"], r["rfcs"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
