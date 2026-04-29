"""Example adapter: turn arbitrary chat-completions output into a predictions JSONL.

This module shows the wiring you'd add to score a real LLM against the eval.
It does not call any LLM by itself — instead it accepts a callable that maps
a list[dict] of chat messages (with system + user pre-populated from the
eval dataset) to the assistant's reply string.

Usage:

    from eval.adapter_example import score_with_model
    score_with_model(my_completion_fn, "my_predictions.jsonl")

where ``my_completion_fn(messages)`` returns the assistant string. Adapters
for OpenAI, Anthropic, local llama.cpp, etc. are about three lines apiece.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Callable, List, Dict

# Make the run_eval module importable when this file is run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_eval import EVAL_PATH, extract_halt_gate_from_assistant, load_dataset


CompletionFn = Callable[[List[Dict[str, str]]], str]


def score_with_model(completion_fn: CompletionFn, output_path: str | Path) -> None:
    """Run ``completion_fn`` on every eval item and write predictions JSONL.

    For each eval item:
      1. Take the system + user turns from the dataset.
      2. Call ``completion_fn(messages)`` to get the assistant reply.
      3. Extract the halt gate via the same heuristic the runner uses.
      4. Write {id, predicted_halt_gate} to the predictions file.

    Then run ``python eval/run_eval.py --mode=score --predictions <output>``
    to compare.
    """
    items = load_dataset(EVAL_PATH)
    out_path = Path(output_path)
    n = 0
    with out_path.open("w") as out:
        for it in items:
            # Strip the ground-truth assistant turn before sending.
            messages = [m for m in it.get("messages", [])
                        if m.get("role") in ("system", "user")]
            try:
                reply = completion_fn(messages)
            except Exception as e:
                reply = f"[completion error: {e}]"
            pred = extract_halt_gate_from_assistant(reply)
            out.write(json.dumps({"id": it["id"], "predicted_halt_gate": pred}) + "\n")
            n += 1
    print(f"Wrote {n} predictions to {out_path}")


# Reference adapters (commented; uncomment and adapt as needed)
"""
# Anthropic / Claude:
#   pip install anthropic
#
# from anthropic import Anthropic
# client = Anthropic()
#
# def claude_fn(messages):
#     system = next((m["content"] for m in messages if m["role"] == "system"), "")
#     user_turns = [m for m in messages if m["role"] != "system"]
#     resp = client.messages.create(
#         model="claude-haiku-4-5-20251001",
#         max_tokens=1024,
#         system=system,
#         messages=user_turns,
#     )
#     return resp.content[0].text

# OpenAI-compatible chat:
#
# from openai import OpenAI
# client = OpenAI()
#
# def gpt_fn(messages):
#     resp = client.chat.completions.create(
#         model="gpt-4o-mini",
#         messages=messages,
#     )
#     return resp.choices[0].message.content
"""


if __name__ == "__main__":
    # Demo: a "model" that always echoes the dataset's own assistant turn.
    # Useful as a smoke test of the wiring; it should reproduce the heuristic
    # baseline (76% as of v1.0.5).
    items = {it["id"]: it for it in load_dataset(EVAL_PATH)}

    def echo_fn(messages):
        # Find which item this is by matching the user content
        user_msg = next(m for m in messages if m["role"] == "user")["content"]
        for it in items.values():
            for m in it.get("messages", []):
                if m["role"] == "user" and m["content"] == user_msg:
                    for a in it["messages"]:
                        if a["role"] == "assistant":
                            return a["content"]
        return ""

    score_with_model(echo_fn, "eval/echo_predictions.jsonl")
