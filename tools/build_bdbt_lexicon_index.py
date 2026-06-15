#!/usr/bin/env python3
"""Build the richer scholarly lexical-take index -- BDB/Thayer-grade definitions.

Source: STEPBible TBESH (Hebrew) + TBESG (Greek) -- "Translators Brief lexicon of
Extended Strongs", from https://github.com/STEPBible/STEPBible-Data (Lexicons/).
License: CC BY 4.0 (STEPBible.org). These are scholar-grade extended-Strongs
lexicons in the Brown-Driver-Briggs / Thayer tradition (the (AS) entries are
Abbott-Smith for Greek; the Hebrew draws on BDB). EXTERNAL Layer-0, attributed,
never engine-authored.

This layers a RICHER take beside the terse Strong's gloss already wired into
read_passage / word_study: the same Strong's key now also yields a fuller scholarly
definition. The named "then BDB/Thayer" depth of the lexicon milestone.

TSV columns: strongs | ext-key | ext-key2 | word | translit | morph | gloss | def(HTML)
We key by the BASE Strong's number (col 0), normalized to match the corpus
(G0001 -> G1, H7225 -> H7225), keeping the first (primary) sense per number.

Output: lw/00_source/lexicon_bdbt/bdbt.db  (SQLite)
  entries (strongs TEXT PRIMARY KEY, word TEXT, translit TEXT, gloss TEXT, definition TEXT)
  meta    (k, v)

Usage:  python tools/build_bdbt_lexicon_index.py --src <dir with tbesh.txt + tbesg.txt>
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(s: str) -> str:
    if not s:
        return ""
    s = _TAG.sub(" ", s)          # drop <b>/<BR>/<i>/<ref=...> tags, keep inner text
    s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    s = _WS.sub(" ", s).strip()
    s = s.rstrip("† ").strip()   # trailing dagger marks
    return s


def _norm(strongs: str) -> str:
    m = re.match(r"^([GH])0*(\d+)", strongs.strip())
    if not m:
        return ""
    return m.group(1) + m.group(2)    # G0001 -> G1 ; H7225 -> H7225


def _parse(fp: Path, rows: dict) -> int:
    n = 0
    if not fp.exists():
        return 0
    for line in fp.open(encoding="utf-8"):
        if "\t" not in line:
            continue
        c = line.rstrip("\n").split("\t")
        if len(c) < 7:
            continue
        base = c[0].strip()
        if not (base[:1] in ("G", "H") and base[1:2].isdigit()):
            continue                  # skip header/preamble lines
        key = _norm(base)
        if not key or key in rows:    # first (primary) sense per base number
            continue
        word = c[3].strip()
        translit = c[4].strip()
        gloss = _clean(c[6])
        definition = _clean(c[7]) if len(c) > 7 else ""
        rows[key] = (key, word, translit, gloss, definition)
        n += 1
    return n


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    rows: dict = {}
    nh = _parse(src / "tbesh.txt", rows)
    ng = _parse(src / "tbesg.txt", rows)
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE entries (strongs TEXT PRIMARY KEY, word TEXT, "
                "translit TEXT, gloss TEXT, definition TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")
    cur.executemany("INSERT INTO entries VALUES (?,?,?,?,?)", list(rows.values()))
    meta = {
        "source": "STEPBible TBESH (Hebrew) + TBESG (Greek) -- Translators Brief lexicon of Extended Strongs",
        "url": "https://github.com/STEPBible/STEPBible-Data (Lexicons/)",
        "license": "CC BY 4.0 (STEPBible.org)",
        "attribution": "STEPBible.org, CC BY (TBESH/TBESG; Greek incl. Abbott-Smith; Hebrew in the BDB tradition)",
        "n_entries": str(len(rows)), "n_hebrew": str(nh), "n_greek": str(ng),
        "note": "Richer scholarly take beside the terse Strong's gloss. Keyed by base Strong's "
                "(normalized G0001->G1, H7225->H7225), primary sense per number. BDB/Thayer-grade.",
    }
    cur.executemany("INSERT INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()
    return {"entries": len(rows), "hebrew": nh, "greek": ng}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="dir with tbesh.txt + tbesg.txt")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = (Path(a.out) if a.out
           else Path(__file__).resolve().parents[1] / "lw" / "00_source" / "lexicon_bdbt" / "bdbt.db")
    print(build(Path(a.src), out))
    print("wrote", out)
