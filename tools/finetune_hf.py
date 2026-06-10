#!/usr/bin/env python3
"""finetune_hf.py — fine-tune any HuggingFace causal LM with LoRA via
transformers + PEFT. Phase 5 of the standalone trajectory.

For CUDA boxes — RunPod, Vast.ai, Lambda, or any local NVIDIA GPU.
Recommended hardware:
  - 8B model + LoRA at bs=2, ctx=1024 → fits on a 24 GB GPU (3090/4090)
  - 70B model + QLoRA → needs an 80 GB GPU (A100/H100) or multi-GPU

Prereqs:
    pip install transformers accelerate peft datasets bitsandbytes trl

Inputs:
    A JSONL training corpus produced by tools/export_corpus.py with the
    narrowhighway.training_pair/1 schema.

Outputs:
    data/models/hf/<run-id>/
        adapters/            (LoRA adapter — load via PeftModel.from_pretrained)
        manifest.json        (run metadata: base, hyperparams, corpus_hash, etc.)
        log.txt              (training log)

Usage:
    # 8B with 4-bit QLoRA on a 24 GB GPU:
    python tools/finetune_hf.py \
        --corpus data/training_corpus/corpus-gated-generation-*.jsonl \
        --base meta-llama/Llama-3.1-8B-Instruct \
        --epochs 3 --lora-rank 16 --lora-alpha 32 --4bit

    # Mistral 7B on a 16 GB GPU:
    python tools/finetune_hf.py \
        --corpus data/training_corpus/... \
        --base mistralai/Mistral-7B-Instruct-v0.3 \
        --epochs 3 --lora-rank 8 --lora-alpha 16 --4bit

This script is meant to be COPIED to the GPU box along with the corpus.
On the GPU box: `python finetune_hf.py --corpus corpus.jsonl ...`
Sync the resulting adapter back to data/models/hf/<run-id>/ and register
via tools/model_registry.py register.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
MODELS_DIR = REPO_ROOT / "data" / "models" / "hf"
LOG_DIR = REPO_ROOT / "logs"


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(1024 * 1024)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Fine-tune via transformers + PEFT (CUDA)")
    ap.add_argument("--corpus", required=True, help="JSONL training corpus")
    ap.add_argument("--base", default="mistralai/Mistral-7B-Instruct-v0.3",
                    help="HF repo id of the base model")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--learning-rate", type=float, default=2e-5)
    ap.add_argument("--lora-rank", type=int, default=16)
    ap.add_argument("--lora-alpha", type=float, default=32.0)
    ap.add_argument("--lora-dropout", type=float, default=0.05)
    ap.add_argument("--max-seq-len", type=int, default=1024)
    ap.add_argument("--4bit", dest="quant_4bit", action="store_true",
                    help="Use 4-bit QLoRA (saves VRAM; needs bitsandbytes)")
    ap.add_argument("--seed", type=int, default=1117)
    ap.add_argument("--prepare-only", action="store_true",
                    help="Just split + summarize; don't import torch/run training")
    args = ap.parse_args()

    corpus_path = Path(args.corpus).resolve()
    if not corpus_path.exists():
        print(f"ERROR: corpus missing: {corpus_path}", file=sys.stderr)
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    base_tag = args.base.split("/")[-1].replace(".", "-")[:20]
    run_id = f"hf-{base_tag}-{stamp}"
    run_dir = MODELS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"finetune_hf_{run_id}.log"
    print(f"[finetune-hf] run_id={run_id}")

    # Read corpus
    lines = [l for l in corpus_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"[finetune-hf] corpus pairs: {len(lines)}")

    # Manifest
    manifest = {
        "schema": "narrowhighway.finetune_run/1",
        "run_id": run_id,
        "backend": "hf",
        "base": args.base,
        "corpus_path": str(corpus_path.relative_to(REPO_ROOT)
                            if corpus_path.is_relative_to(REPO_ROOT)
                            else corpus_path).replace("\\", "/"),
        "corpus_pairs": len(lines),
        "corpus_hash": _hash_file(corpus_path),
        "hyperparams": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "lora_rank": args.lora_rank,
            "lora_alpha": args.lora_alpha,
            "lora_dropout": args.lora_dropout,
            "max_seq_len": args.max_seq_len,
            "quant_4bit": args.quant_4bit,
            "seed": args.seed,
        },
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    if args.prepare_only:
        print(f"[finetune-hf] --prepare-only complete. manifest at {run_dir}/manifest.json")
        return 0

    # Heavy imports only at run time (not during --prepare-only)
    try:
        import torch
        from datasets import Dataset
        from transformers import (
            AutoModelForCausalLM, AutoTokenizer,
            TrainingArguments, Trainer, DataCollatorForLanguageModeling,
        )
        from peft import LoraConfig, get_peft_model, TaskType
        if args.quant_4bit:
            from transformers import BitsAndBytesConfig
    except ImportError as e:
        print(f"ERROR: required packages missing: {e}", file=sys.stderr)
        print("Run: pip install transformers accelerate peft datasets bitsandbytes",
              file=sys.stderr)
        return 3

    # Format records as {text: "..."}
    random.seed(args.seed)
    random.shuffle(lines)
    n = len(lines)
    n_train = int(n * 0.9)

    def make_text(obj_line):
        try:
            obj = json.loads(obj_line)
        except Exception:
            return None
        p = (obj.get("prompt") or "").strip()
        c = (obj.get("completion") or "").strip()
        if not p or not c:
            return None
        # Generic chat-template-friendly format
        return f"<|user|>\n{p}\n<|assistant|>\n{c}"

    train_texts = [t for t in (make_text(l) for l in lines[:n_train]) if t]
    eval_texts = [t for t in (make_text(l) for l in lines[n_train:]) if t]
    print(f"[finetune-hf] train pairs: {len(train_texts)} | eval: {len(eval_texts)}")
    if not train_texts:
        print("ERROR: no usable training records", file=sys.stderr)
        return 4

    # Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(args.base, use_fast=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(batch):
        toks = tokenizer(
            batch["text"], truncation=True, max_length=args.max_seq_len,
            padding=False,
        )
        toks["labels"] = toks["input_ids"].copy()
        return toks

    train_ds = Dataset.from_dict({"text": train_texts}).map(tokenize, batched=True, remove_columns=["text"])
    eval_ds = Dataset.from_dict({"text": eval_texts}).map(tokenize, batched=True, remove_columns=["text"]) if eval_texts else None

    # Model load (optional 4-bit)
    model_kwargs = {"device_map": "auto"}
    if args.quant_4bit:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
        )
        model_kwargs["quantization_config"] = bnb
    else:
        model_kwargs["torch_dtype"] = torch.bfloat16

    model = AutoModelForCausalLM.from_pretrained(args.base, **model_kwargs)
    model.gradient_checkpointing_enable()

    # Detect attention modules (varies by architecture)
    target_modules_by_family = {
        "mistral": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "llama":   ["q_proj", "k_proj", "v_proj", "o_proj"],
        "phi":     ["q_proj", "k_proj", "v_proj", "dense"],
        "qwen":    ["q_proj", "k_proj", "v_proj", "o_proj"],
        "gemma":   ["q_proj", "k_proj", "v_proj", "o_proj"],
    }
    base_lower = args.base.lower()
    targets = None
    for fam, tm in target_modules_by_family.items():
        if fam in base_lower:
            targets = tm
            break
    targets = targets or ["q_proj", "k_proj", "v_proj", "o_proj"]

    lora_cfg = LoraConfig(
        r=args.lora_rank,
        lora_alpha=args.lora_alpha,
        target_modules=targets,
        lora_dropout=args.lora_dropout,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_cfg)
    model.print_trainable_parameters()

    output_dir = run_dir / "adapters"
    output_dir.mkdir(parents=True, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        logging_steps=20,
        save_strategy="epoch",
        eval_strategy="epoch" if eval_ds else "no",
        bf16=True,
        seed=args.seed,
        report_to="none",
    )

    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(
        model=model, args=training_args,
        train_dataset=train_ds, eval_dataset=eval_ds,
        data_collator=collator,
    )

    print(f"[finetune-hf] starting training...")
    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    manifest["ended_at"] = datetime.now(timezone.utc).isoformat()
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"[finetune-hf] DONE. adapter at {output_dir}")
    print(f"[finetune-hf] register with:")
    print(f"  python tools/model_registry.py register \\")
    print(f"    --base {args.base} --adapter {output_dir} \\")
    print(f"    --backend hf --corpus {corpus_path} --run {run_id} \\")
    print(f"    --hyperparams '{json.dumps(manifest['hyperparams'])}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
