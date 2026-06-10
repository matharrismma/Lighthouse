#!/usr/bin/env python3
"""office_confusion.py — where do the from-scratch models actually err?

Loads the trained NB models + eval sets and tallies the top (truth -> predicted)
confusions per field. If errors cluster on near-synonymous labels, a cheap label
cleanup fixes accuracy; if they're scattered, the task needs a stronger model.
Read-only, free.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
sys.path.insert(0, str(REPO_ROOT))
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"

from api import office_models  # noqa: E402

EXT = {
    "shepherd": {"action": lambda c: c.get("action"),
                 "tool": lambda c: c.get("tool") if c.get("action") == "route" else None},
    "scribe": {"kind": lambda c: c.get("kind"), "route": lambda c: c.get("route")},
    "steward": {"aspect": lambda c: c.get("aspect"),
                "decision": lambda c: c.get("decision"),
                "gate": lambda c: c.get("gate") if c.get("aspect") == "keep" else None},
}


def read(path):
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            c = json.loads(r["completion"]) if isinstance(r.get("completion"), str) else r["completion"]
            rows.append((r.get("prompt", ""), c or {}))
        except Exception:
            continue
    return rows


for office, fields in EXT.items():
    rows = read(OFFICE_DIR / f"{office}.eval.jsonl")
    if not rows:
        continue
    print(f"\n=== {office} (eval n={len(rows)}) ===")
    conf = {f: Counter() for f in fields}
    for prompt, comp in rows:
        pred = office_models.predict(office, prompt) or {}
        for f, fn in fields.items():
            truth = fn(comp)
            if truth is None:
                continue
            p = pred.get(f)
            if p != truth:
                conf[f][(truth, p)] += 1
    for f, ctr in conf.items():
        if not ctr:
            print(f"  {f}: no errors")
            continue
        top = ", ".join(f"{t}->{p}:{n}" for (t, p), n in ctr.most_common(5))
        print(f"  {f} (errs {sum(ctr.values())}): {top}")
