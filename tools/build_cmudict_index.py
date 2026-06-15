#!/usr/bin/env python3
"""Build the CMU Pronouncing Dictionary Layer-0 index (offline, reproducible).

Source: cmudict.dict from the CMU Pronouncing Dictionary
https://github.com/cmusphinx/cmudict (raw .../master/cmudict.dict).
License: 2-clause BSD, (c) 1993-2015 Carnegie Mellon University.

word -> ARPABET pronunciation (North American English), ~126k words, with
stress digits on vowels (0 none, 1 primary, 2 secondary) and (2)/(3) variants.
This is the PHONICS / pronunciation level of the language tree -- it pairs with
language_data (phoneme inventories), word_meaning (semantics), and word_study
(original-language morphology).

This is EXTERNAL, ATTRIBUTED data -- a Layer-0 source, never engine-authored.

Output: lw/00_source/cmudict/cmudict.db  (SQLite, query-by-word, low memory)
  pron (word TEXT, variant INTEGER, arpabet TEXT)   -- indexed by word
  meta (k, v)

Usage:
  python tools/build_cmudict_index.py --src _tmp_cmu/cmudict.dict
"""
from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

_VAR = re.compile(r"^(.+)\((\d+)\)$")


def build(src: Path, out: Path) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = sqlite3.connect(str(out))
    cur = con.cursor()
    cur.execute("CREATE TABLE pron (word TEXT, variant INTEGER, arpabet TEXT)")
    cur.execute("CREATE TABLE meta (k TEXT, v TEXT)")

    rows = []
    n = 0
    words = set()
    with src.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            # drop a trailing "# ..." comment if present
            if " #" in line:
                line = line.split(" #", 1)[0].rstrip()
            parts = line.split(" ", 1)
            if len(parts) != 2:
                continue
            tok, phones = parts[0], parts[1].strip()
            m = _VAR.match(tok)
            if m:
                word, var = m.group(1), int(m.group(2))
            else:
                word, var = tok, 1
            rows.append((word, var, phones))
            words.add(word)
            if len(rows) >= 5000:
                cur.executemany("INSERT INTO pron VALUES (?,?,?)", rows)
                n += len(rows)
                rows = []
    if rows:
        cur.executemany("INSERT INTO pron VALUES (?,?,?)", rows)
        n += len(rows)

    cur.execute("CREATE INDEX idx_word ON pron(word)")
    meta = {
        "source": "CMU Pronouncing Dictionary (cmudict)",
        "license": "BSD-2-Clause, (c) 1993-2015 Carnegie Mellon University",
        "url": "https://github.com/cmusphinx/cmudict",
        "attribution": "Pronunciations from the CMU Pronouncing Dictionary "
                       "(cmudict), (c) Carnegie Mellon University, BSD-2.",
        "scheme": "ARPABET; vowel stress 0=none 1=primary 2=secondary",
        "entries": str(n),
        "words": str(len(words)),
    }
    for k, v in meta.items():
        cur.execute("INSERT INTO meta VALUES (?,?)", (k, v))
    con.commit()
    con.execute("VACUUM")
    con.close()
    return {"entries": n, "words": len(words), "size": out.stat().st_size}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="_tmp_cmu/cmudict.dict")
    ap.add_argument("--out", default="lw/00_source/cmudict/cmudict.db")
    args = ap.parse_args()
    rt = Path(__file__).resolve().parents[1]
    src = (rt / args.src) if not Path(args.src).is_absolute() else Path(args.src)
    out = (rt / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    r = build(src, out)
    print("cmudict.db built: %s" % out)
    print("  entries=%d words=%d  (%.1f MB)" % (
        r["entries"], r["words"], r["size"] / (1024 * 1024)))


if __name__ == "__main__":
    main()
