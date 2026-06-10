#!/usr/bin/env python3
"""office_train.py — train the from-scratch office classifiers. No lineage.

This is the "without descent" model: a multinomial Naive Bayes text classifier
implemented in PURE PYTHON (stdlib only). No pretrained weights, no library
lineage, no GPU — it learns only from our own corpus, trains in seconds on the
CPU, and saves as a small JSON the engine loads with zero dependencies. For the
narrow office tasks (route / sort / decide) this is a legitimate baseline; we
can grow to a small from-scratch neural model later, same data, same contract.

Per office it learns the label-space fields:
  shepherd : action  (+ tool, only when action=route)
  scribe   : kind, route
  steward  : aspect, decision (constrained to the aspect), gate (only keep)

Trains on  <office>.train.jsonl, evaluates on  <office>.eval.jsonl,
writes the model to  data/offices/models/<office>.json, prints accuracy.

Usage:
    python tools/office_train.py --office all
    python tools/office_train.py --office steward
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
MODEL_DIR = REPO_ROOT / "data" / "offices" / "models"

TOKEN_RE = re.compile(r"[a-z0-9']+")

# Weight on the class prior. 1.0 = standard NB (biases toward common classes,
# causing majority-class collapse on imbalanced data); 0.0 = uniform prior
# (decide on word evidence alone). Tunable via env for quick experiments.
PRIOR_WEIGHT = float(os.environ.get("NH_NB_PRIOR_WEIGHT", "1.0") or 1.0)

STEWARD_DECISIONS = {"keep": ["admit", "quarantine", "deny"],
                     "provision": ["work", "yield"],
                     "build": ["build", "defer"]}


def toks(s: str) -> list:
    return TOKEN_RE.findall((s or "").lower())


def field_extractors(office: str) -> dict:
    """field name -> function(completion_dict) -> label or None (None = skip)."""
    if office == "shepherd":
        return {
            "action": lambda c: c.get("action"),
            "tool": lambda c: c.get("tool") if c.get("action") == "route" else None,
        }
    if office == "scribe":
        return {"kind": lambda c: c.get("kind"), "route": lambda c: c.get("route")}
    if office == "steward":
        return {
            "aspect": lambda c: c.get("aspect"),
            "decision": lambda c: c.get("decision"),
            "gate": lambda c: c.get("gate") if c.get("aspect") == "keep" else None,
        }
    return {}


def _read(path: Path) -> list:
    rows = []
    if not path.exists():
        return rows
    for line in path.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            comp = json.loads(rec["completion"]) if isinstance(rec.get("completion"), str) else rec.get("completion")
            rows.append((rec.get("prompt", ""), comp or {}))
        except Exception:
            continue
    return rows


def train_field(examples: list) -> dict:
    """examples: list of (tokens, label). Returns a multinomial-NB field model."""
    class_tok = defaultdict(Counter)
    class_n = Counter()
    vocab = set()
    for tokens, label in examples:
        class_n[label] += 1
        for t in tokens:
            class_tok[label][t] += 1
            vocab.add(t)
    V = len(vocab) or 1
    total = sum(class_n.values()) or 1
    model = {"V": V, "classes": {}}
    for c, n in class_n.items():
        tot_c = sum(class_tok[c].values())
        denom = tot_c + V
        model["classes"][c] = {
            "log_prior": PRIOR_WEIGHT * math.log(n / total),
            "unseen": math.log(1.0 / denom),
            "tok": {t: math.log((cnt + 1) / denom) for t, cnt in class_tok[c].items()},
        }
    return model


def score_field(fm: dict, tokens: list) -> dict:
    out = {}
    for c, p in fm["classes"].items():
        s = p["log_prior"]
        tk = p["tok"]
        un = p["unseen"]
        for t in tokens:
            s += tk.get(t, un)
        out[c] = s
    return out


def predict_field(fm: dict, tokens: list, allowed=None):
    sc = score_field(fm, tokens)
    if allowed:
        restricted = {c: v for c, v in sc.items() if c in allowed}
        sc = restricted or sc
    return max(sc, key=sc.get) if sc else None


def predict_office(model: dict, text: str) -> dict:
    """Predict the full office decision from a trained model (the no-lineage path)."""
    office = model["office"]
    fm = model["fields"]
    tk = toks(text)
    out = {}
    if office == "shepherd":
        out["action"] = predict_field(fm["action"], tk) if "action" in fm else "route"
        if out["action"] == "route" and "tool" in fm:
            out["tool"] = predict_field(fm["tool"], tk)
    elif office == "scribe":
        if "kind" in fm:
            out["kind"] = predict_field(fm["kind"], tk)
        if "route" in fm:
            out["route"] = predict_field(fm["route"], tk)
    elif office == "steward":
        asp = predict_field(fm["aspect"], tk) if "aspect" in fm else None
        out["aspect"] = asp
        if "decision" in fm:
            out["decision"] = predict_field(fm["decision"], tk, allowed=STEWARD_DECISIONS.get(asp))
        out["gate"] = ""
        if asp == "keep" and "gate" in fm:
            out["gate"] = predict_field(fm["gate"], tk)
    return out


def evaluate(model: dict, rows: list) -> dict:
    """Per-field accuracy + exact-decision accuracy on held-out rows."""
    office = model["office"]
    ext = field_extractors(office)
    per_field = {f: [0, 0] for f in model["fields"]}  # [correct, total]
    exact = [0, 0]
    for prompt, comp in rows:
        pred = predict_office(model, prompt)
        ok_all = True
        for f in model["fields"]:
            truth = ext[f](comp)
            if truth is None:
                continue  # field not applicable for this example
            per_field[f][1] += 1
            if pred.get(f) == truth:
                per_field[f][0] += 1
            else:
                ok_all = False
        exact[1] += 1
        if ok_all:
            exact[0] += 1
    acc = {f: (c / t if t else 0.0) for f, (c, t) in per_field.items()}
    return {"per_field": acc, "per_field_n": {f: t for f, (c, t) in per_field.items()},
            "exact": (exact[0] / exact[1] if exact[1] else 0.0), "eval_n": exact[1]}


def train_office(office: str) -> dict | None:
    train_rows = _read(OFFICE_DIR / f"{office}.train.jsonl")
    eval_rows = _read(OFFICE_DIR / f"{office}.eval.jsonl")
    if len(train_rows) < 20:
        print(f"[train] {office}: only {len(train_rows)} train rows — skipping (need ≥20).")
        return None
    ext = field_extractors(office)
    model = {"office": office, "trained_on": len(train_rows), "fields": {}}
    for f, fn in ext.items():
        examples = [(toks(p), fn(c)) for p, c in train_rows if fn(c) is not None]
        if not examples:
            continue
        model["fields"][f] = train_field(examples)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MODEL_DIR / f"{office}.json"
    out_path.write_text(json.dumps(model, ensure_ascii=False), encoding="utf-8")
    rep = evaluate(model, eval_rows) if eval_rows else {"per_field": {}, "exact": 0.0, "eval_n": 0}
    size_kb = out_path.stat().st_size / 1024
    print(f"[train] {office}: trained on {len(train_rows)}, model {size_kb:.0f}KB -> {out_path.name}")
    if rep["eval_n"]:
        fields = " · ".join(f"{f} {rep['per_field'][f]*100:.0f}%" for f in rep["per_field"])
        print(f"        eval n={rep['eval_n']}: {fields} || exact-decision {rep['exact']*100:.0f}%")
    else:
        print("        (no eval set yet)")
    return {"office": office, "report": rep}


def main() -> int:
    ap = argparse.ArgumentParser(description="Train the from-scratch office classifiers")
    ap.add_argument("--office", choices=["shepherd", "scribe", "steward", "all"], default="all")
    args = ap.parse_args()
    targets = ["shepherd", "scribe", "steward"] if args.office == "all" else [args.office]
    for o in targets:
        train_office(o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
