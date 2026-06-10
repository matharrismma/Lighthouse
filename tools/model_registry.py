#!/usr/bin/env python3
"""model_registry.py — track trained model versions and their provenance.

Each fine-tune run produces a model entry with:
  - id              short slug, generated from base + corpus + timestamp
  - base_model      the foundation model id (e.g. mistralai/Mistral-7B-Instruct-v0.2)
  - adapter_path    path to the LoRA/PEFT adapter directory (relative to repo)
  - backend         'mlx' | 'hf'
  - training_run    id of the fine-tune run that produced it
  - corpus_hash     SHA256 over the JSONL training file (provenance)
  - corpus_path     path to the JSONL training file used
  - corpus_pairs    number of training pairs
  - hyperparams     {epochs, batch_size, lr, lora_rank, lora_alpha, ...}
  - eval_scores     populated when the benchmark runs against this model
  - registered_at   ISO timestamp
  - notes           free text

Registry file: data/models/registry.json
Adapter files: data/models/{mlx,hf}/<run-id>/

Usage:
    python tools/model_registry.py list
    python tools/model_registry.py show <id>
    python tools/model_registry.py register \
        --base mistralai/Mistral-7B-Instruct-v0.2 \
        --adapter data/models/mlx/run-20260601-abc/ \
        --backend mlx --corpus data/training_corpus/corpus-...jsonl \
        --hyperparams '{"epochs": 3, "lora_rank": 8}'
    python tools/model_registry.py record-eval <id> <eval-json>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
MODELS_DIR = REPO_ROOT / "data" / "models"
REGISTRY_PATH = MODELS_DIR / "registry.json"

# Ensure dirs exist
MODELS_DIR.mkdir(parents=True, exist_ok=True)
(MODELS_DIR / "mlx").mkdir(parents=True, exist_ok=True)
(MODELS_DIR / "hf").mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {
            "schema": "narrowhighway.model_registry/1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "models": [],
        }
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _save_registry(reg: dict) -> None:
    REGISTRY_PATH.write_text(
        json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _hash_file(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _count_lines(path: Path) -> int:
    n = 0
    with path.open("rb") as f:
        for _ in f:
            n += 1
    return n


def make_model_id(base: str, corpus_hash: str) -> str:
    """nh-<basetag>-<corpushash6>-<ts>"""
    base_tag = base.replace("/", "-").replace(":", "").split("-")[-1][:8].lower()
    if not base_tag:
        base_tag = "model"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"nh-{base_tag}-{corpus_hash[:6]}-{stamp}"


def register(args):
    reg = _load_registry()
    corpus_path = Path(args.corpus).resolve()
    if not corpus_path.exists():
        print(f"ERROR: corpus file missing: {corpus_path}", file=sys.stderr)
        return 2
    corpus_hash = _hash_file(corpus_path)
    corpus_pairs = _count_lines(corpus_path)
    model_id = args.id or make_model_id(args.base, corpus_hash)
    hyperparams = json.loads(args.hyperparams) if args.hyperparams else {}

    entry = {
        "id": model_id,
        "base_model": args.base,
        "adapter_path": str(
            Path(args.adapter).resolve().relative_to(REPO_ROOT)
        ).replace("\\", "/"),
        "backend": args.backend,
        "training_run": args.run or "",
        "corpus_path": str(corpus_path.relative_to(REPO_ROOT)).replace("\\", "/"),
        "corpus_hash": corpus_hash,
        "corpus_pairs": corpus_pairs,
        "hyperparams": hyperparams,
        "eval_scores": {},
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "notes": args.notes or "",
    }
    # Replace if id already exists
    reg["models"] = [m for m in reg.get("models", []) if m.get("id") != model_id]
    reg["models"].append(entry)
    _save_registry(reg)
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    return 0


def list_models(args):
    reg = _load_registry()
    models = reg.get("models", [])
    if not models:
        print("(no models registered yet)")
        return 0
    print(f"{'id':<40} {'backend':<6} {'pairs':>7} {'eval':<16} registered")
    print("-" * 90)
    for m in sorted(models, key=lambda x: x.get("registered_at", ""), reverse=True):
        evs = m.get("eval_scores") or {}
        ev = ""
        if evs:
            # pick the most recent eval's headline metric
            latest_eval = max(evs.values(), key=lambda e: e.get("stamp", ""))
            o = latest_eval.get("overall", {})
            if "avg_overhead_ms" in o:
                ev = f"+{o['avg_overhead_ms']}ms ovh"
        print(f"{m['id']:<40} {m.get('backend', ''):<6} "
              f"{m.get('corpus_pairs', 0):>7} {ev:<16} "
              f"{m.get('registered_at', '')[:19]}")
    return 0


def show(args):
    reg = _load_registry()
    for m in reg.get("models", []):
        if m.get("id") == args.id:
            print(json.dumps(m, indent=2, ensure_ascii=False))
            return 0
    print(f"ERROR: model id not found: {args.id}", file=sys.stderr)
    return 2


def record_eval(args):
    reg = _load_registry()
    for m in reg.get("models", []):
        if m.get("id") == args.id:
            data = json.loads(Path(args.eval_file).read_text(encoding="utf-8"))
            stamp = data.get("stamp", datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S"))
            m.setdefault("eval_scores", {})[stamp] = data
            _save_registry(reg)
            print(f"recorded eval {stamp} for {args.id}")
            return 0
    print(f"ERROR: model id not found: {args.id}", file=sys.stderr)
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the fine-tuned model registry")
    sub = parser.add_subparsers(dest="cmd")

    p_reg = sub.add_parser("register", help="Register a newly-trained model")
    p_reg.add_argument("--base", required=True, help="Base model id (e.g. mistralai/Mistral-7B-Instruct-v0.2)")
    p_reg.add_argument("--adapter", required=True, help="Path to the adapter directory")
    p_reg.add_argument("--backend", required=True, choices=["mlx", "hf"])
    p_reg.add_argument("--corpus", required=True, help="Path to training corpus JSONL")
    p_reg.add_argument("--id", default="", help="Optional explicit model id (default: auto-generated)")
    p_reg.add_argument("--run", default="", help="Training run id")
    p_reg.add_argument("--hyperparams", default="", help="JSON-encoded hyperparameters")
    p_reg.add_argument("--notes", default="", help="Free-text notes")
    p_reg.set_defaults(func=register)

    p_list = sub.add_parser("list", help="List all registered models")
    p_list.set_defaults(func=list_models)

    p_show = sub.add_parser("show", help="Show detail for one model")
    p_show.add_argument("id")
    p_show.set_defaults(func=show)

    p_ev = sub.add_parser("record-eval", help="Attach benchmark results to a model")
    p_ev.add_argument("id")
    p_ev.add_argument("eval_file", help="Path to aggregate.json from a benchmark run")
    p_ev.set_defaults(func=record_eval)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
