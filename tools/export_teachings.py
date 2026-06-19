#!/usr/bin/env python3
"""Export the operator's teachings as training pairs into the corpus prompt-set.

Matt: "From here on out I want my work here to train the Concordance engine."
This turns api/teachings.py into prompt/completion pairs and writes them where the
corpus / fine-tune pipeline reads (data/prompt_sets/teachings_v1.jsonl). The
completions teach the METHOD and the honest status of each idea, never "this is
true" — so the model learns the project's posture, not unverified conclusions.

The actual fine-tune pass is the operator's (his hardware); this prepares the
material. Re-runnable; stdlib only.

    python tools/export_teachings.py
"""
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import teachings as T  # noqa: E402


def main():
    pairs = T.to_training_pairs()
    out_dir = os.path.join(_ROOT, "data", "prompt_sets")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "teachings_v1.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print("wrote %d training pairs from %d teachings -> %s"
          % (len(pairs), T.listing()["count"], out))
    print("the fine-tune pass is the operator's; this is the prepared material.")


if __name__ == "__main__":
    main()
