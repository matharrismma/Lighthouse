"""Anthropic Messages API adapter.

Anthropic does not currently expose a fine-tune API surface for Claude
models, so this adapter is for **inference and evaluation** rather than
training. Use it to:
  - Run the held-out eval against any Claude model (without fine-tuning)
  - Get a strong-model baseline to compare your fine-tunes against
  - Generate distillation data: have Claude produce gate reasoning that
    a smaller model is then trained on

Usage:
    # 1. Convert eval set to Anthropic format (system extracted):
    python training/loader.py --in eval/eval_chat.jsonl \
        --format anthropic --out training/data/anthropic_eval.jsonl

    # 2. Run inference and write predictions:
    ANTHROPIC_API_KEY=... python training/adapters/anthropic_messages.py \
        --model claude-sonnet-4-6 \
        --in training/data/anthropic_eval.jsonl \
        --out preds_claude.jsonl

    # 3. Score:
    python training/score.py --predictions preds_claude.jsonl

Requires: pip install anthropic
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path


_GATE_RE = re.compile(
    r"\b(?P<gate>RED|FLOOR|WAY|EXECUTION)\s+GATE\s*[:\-]\s*(?P<verdict>FAIL|PASS|CAUTION)\b",
    re.IGNORECASE,
)


def extract_halt_gate(text: str) -> str:
    matches = list(_GATE_RE.finditer(text))
    for m in matches:
        if m.group("verdict").upper() == "FAIL":
            return m.group("gate").upper()
    if matches:
        return matches[-1].group("gate").upper()
    return "UNKNOWN"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True,
                    help="Claude model id, e.g. claude-sonnet-4-6")
    ap.add_argument("--in", dest="inp", required=True, type=Path,
                    help="Anthropic-format JSONL ({system, messages})")
    ap.add_argument("--out", required=True, type=Path,
                    help="Predictions JSONL output")
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--sleep", type=float, default=0.5,
                    help="Seconds between requests (rate-limit hygiene)")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("set ANTHROPIC_API_KEY", file=sys.stderr)
        sys.exit(1)

    try:
        import anthropic
    except ImportError:
        print("pip install anthropic", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with args.inp.open("r", encoding="utf-8") as inf, \
         args.out.open("w", encoding="utf-8") as outf:
        for line in inf:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)

            # Strip the assistant message — we want the model to generate.
            user_msgs = [m for m in item["messages"] if m["role"] != "assistant"]

            resp = client.messages.create(
                model=args.model,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                system=item.get("system", ""),
                messages=user_msgs,
            )
            text = "".join(
                block.text for block in resp.content if hasattr(block, "text")
            )

            outf.write(json.dumps({
                "id": item.get("id", ""),
                "predicted_halt_gate": extract_halt_gate(text),
                "raw": text,
            }) + "\n")
            n += 1
            if n % 5 == 0:
                print(f"  predicted {n} ...")
            time.sleep(args.sleep)

    print(f"Wrote {n} predictions to {args.out}")


if __name__ == "__main__":
    main()
