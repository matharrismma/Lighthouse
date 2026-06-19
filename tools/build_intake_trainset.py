#!/usr/bin/env python3
"""build_intake_trainset.py — labeled (text -> intent) data for the intake specialist.

The intake router is hive specialist #1: classify what a person brings into one
intent so the work area knows what to do. This bootstraps its training/eval set
from three honest sources:
  1. SEED templates — hand-written examples per intent (the floor; covers every
     class even before real traffic exists).
  2. The homepage chips — the canonical labeled examples already shipped.
  3. Real logged intakes — data/mcp_requests.jsonl / the intake log, if present
     and if the text was retained (privacy-permitting; truncated/owner only).

Output: data/prompt_sets/intake_trainset.jsonl  ({"text","intent","source"} per line)
Split off a held-out eval set with --eval-frac for the head-to-head harness.

    python tools/build_intake_trainset.py
    python tools/build_intake_trainset.py --eval-frac 0.2   # also write *_eval.jsonl

A small tuned classifier learns from this; tools/specialist_eval.py measures it
head-to-head against the general model. Intuition proposes the hive; the eval disposes.
"""
from __future__ import annotations
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "prompt_sets", "intake_trainset.jsonl")

# The intents the work-area router classifies into (matches index.html nhRender +
# the intent_legend). "verify" is the load-bearing one (routes to the engine).
SEED = {
    "verify": [
        "91 is a prime number", "the derivative of x squared is 2x",
        "water boils at 100 degrees celsius at sea level", "2 + 2 = 5",
        "the speed of light is about 300,000 km/s", "a triangle's angles sum to 180 degrees",
        "8 METs for 70 kg over 1 hour is 560 kcal", "is 17 prime",
        "check: the molar mass of water is 18 g/mol", "force equals mass times acceleration",
    ],
    "list": [
        "milk, eggs, bread and a dozen apples", "add bananas to my grocery list",
        "things to pack: tent, sleeping bag, stove", "todo: call the dentist, mow the lawn",
        "shopping: flour, sugar, butter, vanilla", "remember to buy nails and screws",
    ],
    "draft": [
        "tell Sarah I'll be 15 minutes late for dinner tonight",
        "write a thank-you note to grandma for the gift", "email my boss that I'm taking Friday off",
        "draft a message to the team about the schedule change",
        "reply to John that the meeting is moved to 3pm",
    ],
    "note": [
        "remember the wifi password is sunflower42", "note: the car is parked on level 3",
        "keep this: Mom's birthday is March 12", "save the kids' shoe sizes",
        "jot down that the plumber comes Tuesday",
    ],
    "ask": [
        "what's the capital of France", "how do tides work", "who wrote the book of Romans",
        "what year did the Berlin Wall fall", "why is the sky blue",
    ],
    "learn": [
        "teach me how fractions work", "I want to learn to read music",
        "explain photosynthesis step by step", "help me understand long division",
        "teach me the books of the Bible",
    ],
    "scholar": [
        "find studies on intermittent fasting", "look up the paper on CRISPR gene editing",
        "papers about ocean acidification", "research on sleep and memory",
        "show me the literature on vitamin D and immunity",
    ],
    "search": [
        "search the concordance for grace", "find verses about patience",
        "look for hymns about the cross",
    ],
    "settings": [
        "set up my household", "change my profile", "update my schedule preferences",
    ],
}

# Homepage chips (the shipped canonical labels) — kept in sync with site/index.html.
CHIPS = [
    ("91 is a prime number", "verify"),
    ("the derivative of x squared is 2x", "verify"),
    ("teach me how fractions work", "learn"),
    ("tell Sarah I'll be 15 minutes late for dinner tonight", "draft"),
    ("milk, eggs, bread and a dozen apples", "list"),
    ("remember the wifi password is sunflower42", "note"),
]


def _real_logged(limit=2000):
    """Best-effort: pull (text,intent) from a local intake log if one retained text.
    Privacy: only reads local files; skips silently if absent or text not retained."""
    out = []
    for rel in ("data/mcp_requests.jsonl", "data/live/intake_log.jsonl",
                "data/engine_queue/intake.jsonl"):
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        try:
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if not line:
                    continue
                r = json.loads(line)
                t = r.get("text") or r.get("query") or r.get("input")
                it = r.get("intent")
                if t and it and isinstance(t, str) and len(t) < 300:
                    out.append((t.strip(), it, "logged"))
                    if len(out) >= limit:
                        return out
        except Exception:
            continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-frac", type=float, default=0.0, help="hold out this fraction for eval")
    args = ap.parse_args()

    rows = []
    for intent, examples in SEED.items():
        for t in examples:
            rows.append({"text": t, "intent": intent, "source": "seed"})
    for t, it in CHIPS:
        rows.append({"text": t, "intent": it, "source": "chip"})
    for t, it, src in _real_logged():
        rows.append({"text": t, "intent": it, "source": src})

    # de-dup on (text,intent)
    seen, uniq = set(), []
    for r in rows:
        k = (r["text"].lower(), r["intent"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    by_intent = {}
    for r in uniq:
        by_intent[r["intent"]] = by_intent.get(r["intent"], 0) + 1

    if args.eval_frac > 0:
        # deterministic split: every Nth row to eval (no RNG — reproducible)
        n = max(2, int(round(1 / args.eval_frac)))
        train = [r for i, r in enumerate(uniq) if i % n != 0]
        evalset = [r for i, r in enumerate(uniq) if i % n == 0]
        with open(OUT, "w", encoding="utf-8") as f:
            for r in train:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        ev = OUT.replace(".jsonl", "_eval.jsonl")
        with open(ev, "w", encoding="utf-8") as f:
            for r in evalset:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("wrote %d train -> %s + %d eval -> %s" % (len(train), OUT, len(evalset), ev))
    else:
        with open(OUT, "w", encoding="utf-8") as f:
            for r in uniq:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print("wrote %d labeled examples -> %s" % (len(uniq), OUT))
    print("by intent:", by_intent)
    print("NOTE: seed + chips are the floor; real logged intakes augment it as traffic grows.")


if __name__ == "__main__":
    main()
