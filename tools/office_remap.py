#!/usr/bin/env python3
"""office_remap.py — does label simplification actually lift the ceiling?

Free measurement (no retrain, no regen). For the existing trained NB models on
the existing eval sets, applies two label simplifications and re-scores:
  Shepherd  tool:   merge {discern, walk} -> "weigh"  (near-synonyms)
  Steward   exact:  drop gate from the exact-decision check
                    (gate is a reasoned judgment; defer to rule/review)
Reports the lifted accuracy alongside the baseline. If it jumps materially, the
cleanup is the cheap path; if not, we need the neural model.
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
from api import office_models  # noqa

EXT = {
    "shepherd": {"action": lambda c: c.get("action"),
                 "tool": lambda c: c.get("tool") if c.get("action") == "route" else None},
    "scribe":   {"kind": lambda c: c.get("kind"), "route": lambda c: c.get("route")},
    "steward":  {"aspect": lambda c: c.get("aspect"),
                 "decision": lambda c: c.get("decision"),
                 "gate": lambda c: c.get("gate") if c.get("aspect") == "keep" else None},
}

# remap (truth_label -> simplified_label), applied to BOTH truth and prediction
MERGE = {"shepherd": {"tool": {"discern": "weigh", "walk": "weigh"}}}
# fields to drop from the exact-decision check (still measured per-field)
DROP_FROM_EXACT = {"steward": {"gate"}}


def read(p):
    out = []
    if not p.exists():
        return out
    for ln in p.read_text("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
            c = json.loads(r["completion"]) if isinstance(r.get("completion"), str) else r["completion"]
            out.append((r.get("prompt", ""), c or {}))
        except Exception:
            continue
    return out


def remap(office, field, v):
    return MERGE.get(office, {}).get(field, {}).get(v, v)


for office, fields in EXT.items():
    rows = read(OFFICE_DIR / f"{office}.eval.jsonl")
    if not rows:
        continue
    per = {f: [0, 0] for f in fields}
    exact = [0, 0]
    exact_lift = [0, 0]
    drop = DROP_FROM_EXACT.get(office, set())
    for prompt, comp in rows:
        pred = office_models.predict(office, prompt) or {}
        ok_base = True
        ok_lift = True
        for f, fn in fields.items():
            truth = fn(comp)
            if truth is None:
                continue
            tr = remap(office, f, truth)
            pr = remap(office, f, pred.get(f))
            per[f][1] += 1
            if pr == tr:
                per[f][0] += 1
            else:
                if pred.get(f) != truth:
                    ok_base = False
                if pr != tr:
                    if f not in drop:
                        ok_lift = False
            if pred.get(f) != truth and f in drop:
                # field is dropped from exact_lift but counts against baseline only
                ok_base = False
        exact[1] += 1
        exact_lift[1] += 1
        if ok_base:
            exact[0] += 1
        if ok_lift:
            exact_lift[0] += 1
    fa = " · ".join(f"{f} {(per[f][0]/per[f][1] if per[f][1] else 0)*100:.0f}%" for f in per)
    eb = exact[0] / exact[1] if exact[1] else 0
    el = exact_lift[0] / exact_lift[1] if exact_lift[1] else 0
    note = []
    if office in MERGE:
        for f, m in MERGE[office].items():
            note.append(f"merge {f}:{'+'.join(set(m.keys()))}->{list(m.values())[0]}")
    if office in DROP_FROM_EXACT:
        note.append("drop gate from exact")
    n = "; ".join(note) or "no remap"
    print(f"[{office}] {fa}  ||  exact base {eb*100:.0f}%  ->  lifted {el*100:.0f}%   ({n})")
