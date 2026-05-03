"""Convert training/eval JSONL into provider-specific formats.

Usage:
    python training/loader.py --in training/data/conversational_train.jsonl \
        --format hf       --out training/data/hf_train

    python training/loader.py --in training/data/conversational_train.jsonl \
        --format openai   --out training/data/openai_train.jsonl

    python training/loader.py --in training/data/conversational_train.jsonl \
        --format anthropic --out training/data/anthropic_train.jsonl

Formats:
    hf         — HuggingFace `datasets` JSONL with 'messages' key (works directly with TRL SFTTrainer).
    openai     — OpenAI fine-tune JSONL: {"messages": [...]}
    anthropic  — Anthropic-style: {"system": str, "messages": [{role, content}, ...]}
                 (system pulled out of messages and into top-level field)
    eval       — Predictions-runner format: {"id": "EVAL-NNNN", "predicted_halt_gate": "RED|FLOOR|WAY|EXECUTION|NONE"}
                 (used by `--format eval` after running inference; pairs with eval/run_eval.py --mode=score)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


_GATE_RE = re.compile(
    r"\b(?P<gate>RED|FLOOR|WAY|EXECUTION)\s+GATE\s*[:\-]\s*(?P<verdict>FAIL|PASS|CAUTION)\b",
    re.IGNORECASE,
)


def load_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(items: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def to_hf(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """HF / TRL SFTTrainer format. Each row has a 'messages' field that's
    a chat list. SFTTrainer applies the model's chat template at training time."""
    return [{"messages": it["messages"], "id": it.get("id")} for it in items]


def to_openai(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """OpenAI fine-tune JSONL — same shape as our source: {messages: [...]}."""
    return [{"messages": it["messages"]} for it in items]


def to_anthropic(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Anthropic Messages API format: system prompt is its own top-level
    field, not a role inside messages."""
    out = []
    for it in items:
        msgs = it["messages"]
        sys_msg = next((m for m in msgs if m["role"] == "system"), None)
        rest = [m for m in msgs if m["role"] != "system"]
        out.append({
            "id": it.get("id"),
            "system": sys_msg["content"] if sys_msg else "",
            "messages": rest,
        })
    return out


def extract_halt_gate(assistant_text: str) -> str:
    """Walk gate verdicts in order; return the first FAIL gate.
    If no FAIL, return the last gate mentioned (for full-pass items, that's EXECUTION).
    Mirrors eval/run_eval.py extraction logic."""
    matches = list(_GATE_RE.finditer(assistant_text))
    for m in matches:
        if m.group("verdict").upper() == "FAIL":
            return m.group("gate").upper()
    if matches:
        return matches[-1].group("gate").upper()
    return "UNKNOWN"


def to_eval_predictions(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract assistant gate-halt verdicts as a predictions JSONL.
    Each output line: {"id": ..., "predicted_halt_gate": ...}.
    Useful as a sanity baseline (extract from your own training data)."""
    out = []
    for it in items:
        msgs = it["messages"]
        a = next((m for m in msgs if m["role"] == "assistant"), None)
        if not a:
            continue
        out.append({
            "id": it.get("id", ""),
            "predicted_halt_gate": extract_halt_gate(a["content"]),
        })
    return out


def write_hf_directory(items: List[Dict[str, Any]], out_dir: Path) -> None:
    """Write a directory that `datasets.load_from_disk` or
    `load_dataset('json', data_files=...)` can consume."""
    out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(items, out_dir / "train.jsonl")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, type=Path,
                    help="Input JSONL (training or eval shape)")
    ap.add_argument("--format", required=True,
                    choices=["hf", "openai", "anthropic", "eval"],
                    help="Output format")
    ap.add_argument("--out", required=True, type=Path,
                    help="Output path (file for jsonl formats, directory for hf)")
    args = ap.parse_args()

    if not args.inp.exists():
        print(f"input not found: {args.inp}", file=sys.stderr)
        sys.exit(1)

    items = list(load_jsonl(args.inp))
    print(f"loaded {len(items)} items from {args.inp}")

    if args.format == "hf":
        write_hf_directory(to_hf(items), args.out)
        print(f"wrote HF dataset to {args.out}/train.jsonl")
    elif args.format == "openai":
        write_jsonl(to_openai(items), args.out)
        print(f"wrote OpenAI JSONL to {args.out}")
    elif args.format == "anthropic":
        write_jsonl(to_anthropic(items), args.out)
        print(f"wrote Anthropic JSONL to {args.out}")
    elif args.format == "eval":
        write_jsonl(to_eval_predictions(items), args.out)
        print(f"wrote eval predictions to {args.out}")
    else:
        print(f"unknown format {args.format}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
