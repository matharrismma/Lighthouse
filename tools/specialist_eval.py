#!/usr/bin/env python3
"""specialist_eval.py — head-to-head: does the intake specialist beat the general model?

The assay applied to the architecture itself. Runs a labeled eval set through the
LIVE intake router (POST /workspace/intake) and reports routing ACCURACY + LATENCY
for whatever model is currently configured for the task. Run it twice:

  1) with the general model (NH_ORACLE_PROVIDER_INTAKE unset)        -> baseline
  2) with the tuned specialist (NH_ORACLE_PROVIDER_INTAKE=ollama:nh-intake; restart)

Compare the two reports. Keep the specialist ONLY if it wins (accuracy at lower
latency/cost). Intuition proposes the hive; this disposes.

    python tools/specialist_eval.py --label general
    python tools/specialist_eval.py --label specialist --base https://narrowhighway.com

Eval set: data/prompt_sets/intake_trainset_eval.jsonl (or _trainset.jsonl).
"""
from __future__ import annotations
import argparse
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_eval(path):
    rows = []
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            if r.get("text") and r.get("intent"):
                rows.append(r)
    return rows


def _intake(base, text, timeout=30):
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(base.rstrip("/") + "/workspace/intake", data=body,
                                 headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read().decode("utf-8", "replace"))
    return d, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://narrowhighway.com")
    ap.add_argument("--label", default="run", help="general | specialist (labels the report)")
    ap.add_argument("--eval", default="")
    args = ap.parse_args()

    path = args.eval or os.path.join(ROOT, "data/prompt_sets/intake_trainset_eval.jsonl")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "data/prompt_sets/intake_trainset.jsonl")
    if not os.path.exists(path):
        print("no eval set — run tools/build_intake_trainset.py --eval-frac 0.2 first")
        return 1
    rows = _load_eval(path)
    print("HEAD-TO-HEAD [%s] — %d examples from %s\n" % (args.label, len(rows), os.path.basename(path)))

    correct, total, lat = 0, 0, []
    miss = []
    for r in rows:
        try:
            d, dt = _intake(args.base, r["text"])
        except Exception as e:  # noqa: BLE001
            miss.append((r["text"][:50], r["intent"], "ERR:" + type(e).__name__))
            total += 1
            continue
        got = d.get("intent") or "?"
        lat.append(dt)
        total += 1
        if got == r["intent"]:
            correct += 1
        else:
            miss.append((r["text"][:50], r["intent"], got))

    acc = correct / total if total else 0.0
    lat_sorted = sorted(lat)
    p50 = lat_sorted[len(lat_sorted) // 2] if lat_sorted else 0.0
    p95 = lat_sorted[int(len(lat_sorted) * 0.95)] if lat_sorted else 0.0
    print("ACCURACY : %d/%d = %.1f%%" % (correct, total, 100 * acc))
    print("LATENCY  : p50 %.2fs · p95 %.2fs · mean %.2fs"
          % (p50, p95, (sum(lat) / len(lat)) if lat else 0.0))
    if miss:
        print("\nMISROUTES (expected -> got):")
        for t, exp, got in miss[:25]:
            print("  %-52s %s -> %s" % (t, exp, got))
    print("\n[%s] accuracy %.1f%% | p50 %.2fs — compare against the other model's run."
          % (args.label, 100 * acc, p50))
    return 0


if __name__ == "__main__":
    main()
