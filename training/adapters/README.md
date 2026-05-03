# Provider Adapters

Three minimal scripts, one per major path:

- `openai_finetune.py` — OpenAI fine-tune API (upload data, start job, monitor)
- `huggingface_sft.py` — HuggingFace + PEFT LoRA SFT loop (single GPU)
- `anthropic_messages.py` — Format items for Anthropic's Messages API for evaluation/distillation

These are starting points, not turnkey solutions. Each is short on
purpose: copy, adapt to your project, run. The seed dataset is small
(20 conversational items) so a full fine-tune typically completes in
minutes on any path.

## Pick your path

| Goal | Use |
|---|---|
| Fastest "just train it" path with no GPU | `openai_finetune.py` (cloud API) |
| Open-weights model you control | `huggingface_sft.py` (Llama 3.x, Qwen, Mistral, etc. with PEFT/LoRA) |
| Score predictions from Claude or another Messages API | `anthropic_messages.py` |

You can mix: train via HF, evaluate via OpenAI judging, etc.

## Common workflow

1. **Convert** the seed data to your provider's format:
   ```bash
   python training/loader.py \
       --in training/data/conversational_train.jsonl \
       --format <hf|openai|anthropic> \
       --out training/data/<provider>_train.<ext>
   ```

2. **Fine-tune** with the provider's adapter.

3. **Run inference** on the held-out eval set (`eval/eval_chat.jsonl`)
   to produce a predictions JSONL.

4. **Score**:
   ```bash
   python training/score.py --predictions preds.jsonl
   ```

5. If accuracy is below the target tier in `BASELINE.md`, add training
   items where the confusions are concentrated and retrain.

## Notes

- The seed is intentionally small. If you need more data, *write more
  items by hand*. Synthetic-from-LLM data without human curation tends
  to amplify the model's existing biases rather than teach the
  protocol.
- The system prompt must be byte-for-byte identical between training
  items and inference. The loader scripts preserve it; if you write
  your own loader, copy from `training/SYSTEM_PROMPT.md`.
- Hold `eval/eval_chat.jsonl` out of training. Treat it as the test set;
  contaminating it makes your numbers meaningless.
