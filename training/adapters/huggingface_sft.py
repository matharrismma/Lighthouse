"""HuggingFace + PEFT LoRA SFT adapter.

A minimal supervised fine-tune loop using TRL's SFTTrainer + PEFT LoRA.
Tunes only the LoRA adapters; the base model stays frozen. Runs on a
single consumer GPU for the seed dataset size.

Usage:
    # 1. Convert data:
    python training/loader.py --in training/data/conversational_train.jsonl \
        --format hf --out training/data/hf_train

    # 2. Train:
    python training/adapters/huggingface_sft.py \
        --train training/data/hf_train/train.jsonl \
        --base-model meta-llama/Llama-3.1-8B-Instruct \
        --output ./out/lighthouse-llama-8b-lora \
        --epochs 3

    # 3. (Inference is done via your own eval loop using the resulting
    #    PEFT adapter on top of the base model.)

Requires: pip install transformers trl peft accelerate datasets bitsandbytes
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True, type=Path,
                    help="HF-format training JSONL ({messages: [...]} per line)")
    ap.add_argument("--base-model", required=True,
                    help="HF base model id (instruction-tuned recommended)")
    ap.add_argument("--output", required=True, type=Path,
                    help="Output directory for the LoRA adapter")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=4096)
    ap.add_argument("--quantize", action="store_true",
                    help="Use 4-bit quantization (requires bitsandbytes + GPU)")
    args = ap.parse_args()

    try:
        from datasets import load_dataset
        from peft import LoraConfig, get_peft_model
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import SFTConfig, SFTTrainer
    except ImportError as e:
        print(f"missing dependency: {e}", file=sys.stderr)
        print("pip install transformers trl peft accelerate datasets", file=sys.stderr)
        if args.quantize:
            print("(also: pip install bitsandbytes for --quantize)", file=sys.stderr)
        sys.exit(1)

    print(f"Loading dataset from {args.train}")
    ds = load_dataset("json", data_files=str(args.train), split="train")
    print(f"  {len(ds)} examples")

    print(f"Loading base model {args.base_model}")
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {"torch_dtype": "auto"}
    if args.quantize:
        from transformers import BitsAndBytesConfig
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype="bfloat16",
        )
    model = AutoModelForCausalLM.from_pretrained(args.base_model, **model_kwargs)

    lora = LoraConfig(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    cfg = SFTConfig(
        output_dir=str(args.output),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=4,
        learning_rate=args.lr,
        logging_steps=2,
        save_strategy="epoch",
        bf16=True,
        max_length=args.max_len,
        packing=False,
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=ds,
        args=cfg,
        tokenizer=tokenizer,
    )
    trainer.train()

    args.output.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    print(f"\nSaved LoRA adapter + tokenizer to {args.output}")
    print(f"Load for inference with:")
    print(f"  from peft import PeftModel")
    print(f"  base = AutoModelForCausalLM.from_pretrained('{args.base_model}')")
    print(f"  model = PeftModel.from_pretrained(base, '{args.output}')")


if __name__ == "__main__":
    main()
