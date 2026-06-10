#!/usr/bin/env python3
"""office_nn_train.py — small from-scratch neural office model. No lineage.

Char-n-gram features (3..5-grams, hashed to a fixed bucket vocab) + multiclass
softmax (a single-layer "fastText"-style classifier). Trained from random init
in numpy on our own corpus. Char n-grams give the model what bag-of-words
couldn't: subword similarity ("verify" ↔ "verification", "admit" ↔ "admission")
— the kind of signal Steward and Scribe need.

Saves model JSON to data/offices/models_nn/<office>.json. Reports accuracy
side-by-side with the NB baseline so we can see whether this rung helps.
"""
from __future__ import annotations
import argparse, json, os, sys, math
from pathlib import Path
import numpy as np

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
MODEL_DIR = REPO_ROOT / "data" / "offices" / "models_nn"

BUCKETS = 5000
NGRAM_LO = 3
NGRAM_HI = 5
EPOCHS = 250
LR = 0.5
L2 = 1e-4

STEWARD_DECISIONS = {"keep": ["admit", "quarantine", "deny"],
                     "provision": ["work", "yield"], "build": ["build", "defer"]}


def hash_feats(text: str) -> list:
    s = "$" + (text or "").lower() + "$"
    out = set()
    for n in range(NGRAM_LO, NGRAM_HI + 1):
        for i in range(len(s) - n + 1):
            out.add(hash(s[i:i + n]) % BUCKETS)
    return list(out)


def featurize(prompts: list) -> np.ndarray:
    X = np.zeros((len(prompts), BUCKETS), dtype=np.float32)
    for i, p in enumerate(prompts):
        for f in hash_feats(p):
            X[i, f] = 1.0
    return X


def train_softmax(X: np.ndarray, y: np.ndarray, n_classes: int) -> np.ndarray:
    W = np.zeros((X.shape[1], n_classes), dtype=np.float32)
    Y = np.eye(n_classes, dtype=np.float32)[y]
    n = X.shape[0]
    for _ in range(EPOCHS):
        logits = X @ W
        logits -= logits.max(axis=1, keepdims=True)
        P = np.exp(logits)
        P /= P.sum(axis=1, keepdims=True)
        grad = X.T @ (P - Y) / n + L2 * W
        W -= LR * grad
    return W


def extractors(office: str) -> dict:
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


def read(path: Path) -> list:
    rows = []
    if not path.exists():
        return rows
    for ln in path.read_text("utf-8", errors="replace").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
            c = json.loads(r["completion"]) if isinstance(r.get("completion"), str) else r["completion"]
            rows.append((r.get("prompt", ""), c or {}))
        except Exception:
            continue
    return rows


def fit_field(train_rows: list, eval_rows: list, fn) -> dict | None:
    tr = [(p, fn(c)) for p, c in train_rows if fn(c) is not None]
    ev = [(p, fn(c)) for p, c in eval_rows if fn(c) is not None]
    if len(tr) < 20:
        return None
    classes = sorted({l for _, l in tr})
    cidx = {c: i for i, c in enumerate(classes)}
    Xtr = featurize([p for p, _ in tr])
    ytr = np.array([cidx[l] for _, l in tr])
    W = train_softmax(Xtr, ytr, len(classes))
    Xev = featurize([p for p, _ in ev])
    truth = np.array([cidx.get(l, -1) for _, l in ev])
    logits = Xev @ W
    pred = logits.argmax(axis=1)
    acc = float((pred == truth).mean()) if len(ev) else 0.0
    return {"classes": classes, "W": W.tolist(), "acc": acc,
            "buckets": BUCKETS, "ngram_lo": NGRAM_LO, "ngram_hi": NGRAM_HI}


def predict_office(model: dict, text: str) -> tuple:
    """Return (decision, confidence) using the NN model — same shape as NB."""
    office = model["office"]
    fm = model["fields"]
    feats = hash_feats(text)
    out, conf = {}, {}

    def _pick(name, allowed=None):
        if name not in fm:
            return None
        W = np.array(fm[name]["W"], dtype=np.float32)
        classes = fm[name]["classes"]
        # sparse dot: sum the rows of W at feature indices
        logits = W[feats].sum(axis=0)
        if allowed:
            mask = np.array([c in allowed for c in classes])
            if mask.any():
                logits = np.where(mask, logits, -1e9)
        logits -= logits.max()
        e = np.exp(logits)
        p = e / e.sum()
        idx = int(p.argmax())
        out[name] = classes[idx]
        conf[name] = float(p.max())

    if office == "shepherd":
        _pick("action")
        if out.get("action") == "route":
            _pick("tool")
    elif office == "scribe":
        _pick("kind")
        _pick("route")
    elif office == "steward":
        _pick("aspect")
        _pick("decision", allowed=STEWARD_DECISIONS.get(out.get("aspect")))
        out["gate"] = ""
        if out.get("aspect") == "keep":
            _pick("gate")
    return out, conf


def evaluate(model: dict, rows: list) -> dict:
    office = model["office"]
    ext = extractors(office)
    per = {f: [0, 0] for f in model["fields"]}
    exact = [0, 0]
    for p, c in rows:
        pred, _ = predict_office(model, p)
        ok = True
        for f in model["fields"]:
            truth = ext[f](c)
            if truth is None:
                continue
            per[f][1] += 1
            if pred.get(f) == truth:
                per[f][0] += 1
            else:
                ok = False
        exact[1] += 1
        if ok:
            exact[0] += 1
    return {"per_field": {f: (per[f][0] / per[f][1] if per[f][1] else 0) for f in per},
            "exact": exact[0] / exact[1] if exact[1] else 0, "eval_n": exact[1]}


def train_office(office: str) -> None:
    train_rows = read(OFFICE_DIR / f"{office}.train.jsonl")
    eval_rows = read(OFFICE_DIR / f"{office}.eval.jsonl")
    if len(train_rows) < 20:
        print(f"[nn] {office}: too few train rows.")
        return
    ext = extractors(office)
    model = {"office": office, "trained_on": len(train_rows), "fields": {},
             "buckets": BUCKETS, "ngram_lo": NGRAM_LO, "ngram_hi": NGRAM_HI}
    for f, fn in ext.items():
        r = fit_field(train_rows, eval_rows, fn)
        if r:
            model["fields"][f] = r
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    out = MODEL_DIR / f"{office}.json"
    out.write_text(json.dumps(model, ensure_ascii=False))
    kb = out.stat().st_size / 1024
    rep = evaluate(model, eval_rows)
    fields = " · ".join(f"{f} {rep['per_field'][f]*100:.0f}%" for f in rep["per_field"])
    print(f"[nn] {office}: trained on {len(train_rows)}, model {kb:.0f}KB -> {out.name}")
    print(f"     eval n={rep['eval_n']}: {fields} || exact {rep['exact']*100:.0f}%")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--office", choices=["shepherd", "scribe", "steward", "all"], default="all")
    args = ap.parse_args()
    targets = ["shepherd", "scribe", "steward"] if args.office == "all" else [args.office]
    for o in targets:
        train_office(o)
    return 0


if __name__ == "__main__":
    sys.exit(main())
