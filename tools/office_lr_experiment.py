#!/usr/bin/env python3
"""office_lr_experiment.py — is the bottleneck the MODEL or the DATA?

Trains a from-scratch multiclass logistic regression (softmax, random init,
gradient descent in numpy — no lineage, no pretrained weights) on the SAME
office corpus and reports accuracy, to compare against the Naive Bayes baseline.
Read-only experiment: writes no production model, spends nothing.

    python tools/office_lr_experiment.py --office all
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
TOKEN_RE = re.compile(r"[a-z0-9']+")
STEWARD_DECISIONS = {"keep": ["admit", "quarantine", "deny"],
                     "provision": ["work", "yield"], "build": ["build", "defer"]}


def toks(s):
    return TOKEN_RE.findall((s or "").lower())


def extractors(office):
    if office == "shepherd":
        return {"action": lambda c: c.get("action"),
                "tool": lambda c: c.get("tool") if c.get("action") == "route" else None}
    if office == "scribe":
        return {"kind": lambda c: c.get("kind"), "route": lambda c: c.get("route")}
    if office == "steward":
        return {"aspect": lambda c: c.get("aspect"),
                "decision": lambda c: c.get("decision"),
                "gate": lambda c: c.get("gate") if c.get("aspect") == "keep" else None}
    return {}


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


def featurize(prompts, vocab=None):
    if vocab is None:
        vocab = {}
        for p in prompts:
            for t in set(toks(p)):
                if t not in vocab:
                    vocab[t] = len(vocab)
    X = np.zeros((len(prompts), len(vocab) + 1), dtype=np.float32)
    X[:, -1] = 1.0  # bias
    for i, p in enumerate(prompts):
        for t in set(toks(p)):
            j = vocab.get(t)
            if j is not None:
                X[i, j] = 1.0
    return X, vocab


def train_lr(X, y, n_classes, epochs=300, lr=0.5, l2=1e-4):
    W = np.zeros((X.shape[1], n_classes), dtype=np.float32)
    Y = np.eye(n_classes, dtype=np.float32)[y]
    n = X.shape[0]
    for _ in range(epochs):
        logits = X @ W
        logits -= logits.max(axis=1, keepdims=True)
        P = np.exp(logits)
        P /= P.sum(axis=1, keepdims=True)
        grad = X.T @ (P - Y) / n + l2 * W
        W -= lr * grad
    return W


def fit_field(train_rows, eval_rows, fn):
    tr = [(p, fn(c)) for p, c in train_rows if fn(c) is not None]
    ev = [(p, fn(c)) for p, c in eval_rows if fn(c) is not None]
    if len(tr) < 20 or not ev:
        return None
    classes = sorted({l for _, l in tr})
    cidx = {c: i for i, c in enumerate(classes)}
    Xtr, vocab = featurize([p for p, _ in tr])
    ytr = np.array([cidx[l] for _, l in tr])
    W = train_lr(Xtr, ytr, len(classes))
    Xev, _ = featurize([p for p, _ in ev], vocab)
    pred = (Xev @ W).argmax(axis=1)
    truth = np.array([cidx.get(l, -1) for _, l in ev])
    acc = float((pred == truth).mean())
    return {"classes": classes, "vocab": vocab, "W": W, "cidx": cidx, "acc": acc}


def run(office):
    train_rows = read(OFFICE_DIR / f"{office}.train.jsonl")
    eval_rows = read(OFFICE_DIR / f"{office}.eval.jsonl")
    ext = extractors(office)
    fits = {}
    for f, fn in ext.items():
        r = fit_field(train_rows, eval_rows, fn)
        if r:
            fits[f] = r
    # exact-decision on eval
    exact = [0, 0]
    for p, c in eval_rows:
        ok = True
        x, _ = featurize([p], fits[list(fits)[0]]["vocab"]) if fits else (None, None)
        preds = {}
        for f, r in fits.items():
            xv, _ = featurize([p], r["vocab"])
            pi = int((xv @ r["W"]).argmax())
            preds[f] = r["classes"][pi]
        for f, fn in ext.items():
            truth = fn(c)
            if truth is None or f not in fits:
                continue
            if preds.get(f) != truth:
                ok = False
        exact[1] += 1
        if ok:
            exact[0] += 1
    fa = " · ".join(f"{f} {fits[f]['acc']*100:.0f}%" for f in fits)
    ex = exact[0] / exact[1] if exact[1] else 0
    print(f"[LR] {office}: {fa} || exact {ex*100:.0f}%  (eval n={exact[1]})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--office", choices=["shepherd", "scribe", "steward", "all"], default="all")
    args = ap.parse_args()
    targets = ["shepherd", "scribe", "steward"] if args.office == "all" else [args.office]
    for o in targets:
        run(o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
