"""OpenAI fine-tune adapter.

Uploads the JSONL training file to OpenAI, starts a fine-tune job,
polls for completion, and prints the resulting model id.

Optional inference mode runs the held-out eval against the fine-tuned
model and writes a predictions JSONL that `training/score.py` can score.

Usage:
    # Convert seed first:
    python training/loader.py --in training/data/conversational_train.jsonl \
        --format openai --out training/data/openai_train.jsonl

    # Train:
    OPENAI_API_KEY=... python training/adapters/openai_finetune.py \
        --train training/data/openai_train.jsonl \
        --base-model gpt-4o-mini-2024-07-18

    # Run inference on eval set:
    OPENAI_API_KEY=... python training/adapters/openai_finetune.py \
        --predict --model ft:gpt-4o-mini-2024-07-18:org::abc123 \
        --in eval/eval_chat.jsonl \
        --out preds.jsonl

Requires: pip install openai
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List


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


def cmd_train(train_path: Path, base_model: str) -> None:
    try:
        from openai import OpenAI
    except ImportError:
        print("pip install openai", file=sys.stderr)
        sys.exit(1)
    client = OpenAI()

    print(f"Uploading {train_path} ...")
    with train_path.open("rb") as f:
        upload = client.files.create(file=f, purpose="fine-tune")
    print(f"  file id: {upload.id}")

    print(f"Starting fine-tune on {base_model} ...")
    job = client.fine_tuning.jobs.create(
        training_file=upload.id,
        model=base_model,
    )
    print(f"  job id: {job.id}")
    print(f"  status: {job.status}")

    print("Polling job status (Ctrl+C to detach; job continues server-side)")
    while True:
        time.sleep(30)
        job = client.fine_tuning.jobs.retrieve(job.id)
        print(f"  [{job.status}] trained_tokens={job.trained_tokens}")
        if job.status in ("succeeded", "failed", "cancelled"):
            break

    if job.status == "succeeded":
        print(f"\nFine-tuned model: {job.fine_tuned_model}")
        print(f"Use --model {job.fine_tuned_model} for inference.")
    else:
        print(f"\nJob {job.status}; see OpenAI dashboard for details.")
        sys.exit(2)


def cmd_predict(model: str, eval_path: Path, out_path: Path) -> None:
    try:
        from openai import OpenAI
    except ImportError:
        print("pip install openai", file=sys.stderr)
        sys.exit(1)
    client = OpenAI()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with eval_path.open("r", encoding="utf-8") as inf, \
         out_path.open("w", encoding="utf-8") as outf:
        for line in inf:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            messages = [m for m in item["messages"] if m["role"] != "assistant"]
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,
            )
            text = resp.choices[0].message.content or ""
            outf.write(json.dumps({
                "id": item["id"],
                "predicted_halt_gate": extract_halt_gate(text),
                "raw": text,
            }) + "\n")
            n += 1
            if n % 5 == 0:
                print(f"  predicted {n} ...")
    print(f"Wrote {n} predictions to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", type=Path, help="OpenAI-format JSONL to fine-tune on")
    ap.add_argument("--base-model", default="gpt-4o-mini-2024-07-18",
                    help="Base model to fine-tune (default gpt-4o-mini)")
    ap.add_argument("--predict", action="store_true",
                    help="Run inference on --in instead of training")
    ap.add_argument("--model", help="Fine-tuned model id (for --predict)")
    ap.add_argument("--in", dest="inp", type=Path,
                    help="Eval JSONL to run predictions on")
    ap.add_argument("--out", type=Path,
                    help="Predictions JSONL output")
    args = ap.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("set OPENAI_API_KEY", file=sys.stderr)
        sys.exit(1)

    if args.predict:
        if not (args.model and args.inp and args.out):
            print("--predict requires --model, --in, --out", file=sys.stderr)
            sys.exit(2)
        cmd_predict(args.model, args.inp, args.out)
    else:
        if not args.train:
            print("--train required (or use --predict)", file=sys.stderr)
            sys.exit(2)
        cmd_train(args.train, args.base_model)


if __name__ == "__main__":
    main()
