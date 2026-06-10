#!/usr/bin/env python3
"""finetune_mlx.py — fine-tune a base model on the Narrow Highway corpus
using Apple Silicon via mlx-lm. Phase 4 of the standalone trajectory.

Prereqs (Mac M-series):
    pip install mlx-lm

The script:
  1. Reads a corpus JSONL (output of tools/export_corpus.py) containing
     {prompt, completion} pairs with schema narrowhighway.training_pair/1.
  2. Splits into train/valid/test (~85/10/5).
  3. Writes the train/valid splits as the JSONL format mlx_lm.lora expects.
  4. Invokes `mlx_lm.lora` to fine-tune the base model with QLoRA.
  5. Writes the adapter to data/models/mlx/<run-id>/.
  6. Records the run + registers in the model registry.

Defaults are chosen for a 7B model on a 16GB Mac (Mistral-7B-Instruct
4-bit). For an 8GB Mac, use a smaller model like Mistral 7B in 3-bit or
Llama 3.2 3B in 4-bit.

Usage:
    python tools/finetune_mlx.py \
        --corpus data/training_corpus/corpus-gated-generation-*.jsonl \
        --base mlx-community/Mistral-7B-Instruct-v0.3-4bit \
        --epochs 3 --lora-rank 8 --lora-alpha 16

This script does NOT run the fine-tune on Windows. Copy the corpus to your
Mac (Tailscale, OneDrive sync, or scp), run there, then sync the adapter
output back to data/models/mlx/<run-id>/ and register with
tools/model_registry.py register.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
MODELS_DIR = REPO_ROOT / "data" / "models" / "mlx"
LOG_DIR = REPO_ROOT / "logs"


def split_corpus(corpus_path: Path, ratio=(0.85, 0.10, 0.05), seed: int = 1117):
    """Split a JSONL corpus into train/valid/test."""
    lines = [l.strip() for l in corpus_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    rng = random.Random(seed)
    rng.shuffle(lines)
    n = len(lines)
    n_train = int(n * ratio[0])
    n_valid = int(n * ratio[1])
    return lines[:n_train], lines[n_train:n_train + n_valid], lines[n_train + n_valid:]


def to_mlx_format(records: list[str], out_path: Path) -> int:
    """Convert from narrowhighway.training_pair/1 records to the simple
    {"text": "..."} format mlx_lm.lora expects, joining prompt + completion."""
    n = 0
    with out_path.open("w", encoding="utf-8") as f:
        for line in records:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            prompt = (obj.get("prompt") or "").strip()
            completion = (obj.get("completion") or "").strip()
            if not prompt or not completion:
                continue
            text = f"<|user|>\n{prompt}\n<|assistant|>\n{completion}"
            f.write(json.dumps({"text": text}, ensure_ascii=False) + "\n")
            n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Fine-tune via mlx-lm (Apple Silicon)")
    ap.add_argument("--corpus", required=True, help="Path to JSONL training corpus")
    ap.add_argument("--base", default="mlx-community/Mistral-7B-Instruct-v0.3-4bit",
                    help="MLX-quantized base model HF repo id")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--learning-rate", type=float, default=1e-5)
    ap.add_argument("--lora-rank", type=int, default=8)
    ap.add_argument("--lora-alpha", type=float, default=16.0)
    ap.add_argument("--iters", type=int, default=0,
                    help="If >0, overrides epochs; passed straight to mlx_lm.lora --iters")
    ap.add_argument("--seed", type=int, default=1117)
    ap.add_argument("--prepare-only", action="store_true",
                    help="Just split + format the corpus; don't run the trainer")
    args = ap.parse_args()

    is_apple = (platform.system() == "Darwin"
                and platform.machine() in ("arm64", "aarch64"))
    if not is_apple and not args.prepare_only:
        print("WARNING: not running on Apple Silicon. Use --prepare-only on this "
              "machine and rsync to a Mac for the actual fine-tune, OR use "
              "tools/finetune_hf.py for a CUDA-based run.", file=sys.stderr)

    corpus_path = Path(args.corpus).resolve()
    if not corpus_path.exists():
        print(f"ERROR: corpus missing: {corpus_path}", file=sys.stderr)
        return 2

    # Run id
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_tag = args.base.split("/")[-1].replace(".", "-")[:20]
    run_id = f"mlx-{base_tag}-{stamp}"
    run_dir = MODELS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    data_dir = run_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[finetune-mlx] run_id={run_id}")
    print(f"[finetune-mlx] run_dir={run_dir}")

    # Split + convert
    train_lines, valid_lines, test_lines = split_corpus(corpus_path, seed=args.seed)
    n_train = to_mlx_format(train_lines, data_dir / "train.jsonl")
    n_valid = to_mlx_format(valid_lines, data_dir / "valid.jsonl")
    n_test = to_mlx_format(test_lines, data_dir / "test.jsonl")
    print(f"[finetune-mlx] split: train={n_train} valid={n_valid} test={n_test}")

    # Manifest
    manifest = {
        "schema": "narrowhighway.finetune_run/1",
        "run_id": run_id,
        "backend": "mlx",
        "base": args.base,
        "corpus_path": str(corpus_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "corpus_pairs": n_train + n_valid + n_test,
        "split": {"train": n_train, "valid": n_valid, "test": n_test},
        "hyperparams": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "lora_rank": args.lora_rank,
            "lora_alpha": args.lora_alpha,
            "iters": args.iters or None,
            "seed": args.seed,
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if args.prepare_only:
        print(f"[finetune-mlx] --prepare-only: data prepared at {data_dir}")
        print(f"[finetune-mlx] next: copy {run_dir} to your Mac, then run:")
        cmd_preview = (
            f"  python -m mlx_lm.lora --model {args.base} --train "
            f"--data {data_dir} --iters {args.iters or (args.epochs * max(1, n_train // args.batch_size))} "
            f"--batch-size {args.batch_size} --lora-rank {args.lora_rank} "
            f"--lora-alpha {args.lora_alpha} --learning-rate {args.learning_rate} "
            f"--adapter-path {run_dir / 'adapters'}"
        )
        print(cmd_preview)
        return 0

    # Run the trainer
    iters = args.iters or (args.epochs * max(1, n_train // args.batch_size))
    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "--model", args.base,
        "--train",
        "--data", str(data_dir),
        "--iters", str(iters),
        "--batch-size", str(args.batch_size),
        "--lora-rank", str(args.lora_rank),
        "--lora-alpha", str(args.lora_alpha),
        "--learning-rate", str(args.learning_rate),
        "--adapter-path", str(run_dir / "adapters"),
        "--save-every", str(max(50, iters // 5)),
    ]
    print(f"[finetune-mlx] running: {' '.join(cmd)}")

    log_path = LOG_DIR / f"finetune_mlx_{run_id}.log"
    with log_path.open("w", encoding="utf-8") as logf:
        result = subprocess.run(cmd, stdout=logf, stderr=subprocess.STDOUT)

    manifest["ended_at"] = datetime.now(timezone.utc).isoformat()
    manifest["returncode"] = result.returncode
    manifest["log"] = str(log_path.relative_to(REPO_ROOT)).replace("\\", "/")
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if result.returncode != 0:
        print(f"[finetune-mlx] FAILED (rc={result.returncode}); see {log_path}",
              file=sys.stderr)
        return result.returncode

    print(f"[finetune-mlx] DONE. adapter at {run_dir / 'adapters'}")
    print(f"[finetune-mlx] next: register the model:")
    print(f"  python tools/model_registry.py register \\")
    print(f"      --base {args.base} \\")
    print(f"      --adapter {run_dir / 'adapters'} \\")
    print(f"      --backend mlx \\")
    print(f"      --corpus {corpus_path} \\")
    print(f"      --run {run_id} \\")
    print(f"      --hyperparams '{json.dumps(manifest['hyperparams'])}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
