#!/usr/bin/env python
"""Build target→English alignment tables.

Mirrors `build_bible_alignment.py` but in the reverse direction: for each
target-language token, find the most-likely English translation via Dice
coefficient across the parallel verses.

Why: when a visitor types in their language ("ansiedad", "anxiété",
"焦り") and we need to do retrieval against the English substrate, we
translate target → English using the same Bible-corpus alignment trick.

Output: data/lang_corpus/<lang>_to_en.jsonl, mirror of <lang>.jsonl shape.
"""
from __future__ import annotations
import io
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Reuse the tokenization + verse-loader from the forward script.
sys.path.insert(0, str(Path(__file__).parent))
from build_bible_alignment import (  # type: ignore
    EN_FILE, TARGETS, en_tokens, target_tokens, load_verses,
)

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "lang_corpus"


def align_reverse(lang: str, target_path: Path,
                  en_verses: Dict[Tuple[str, int, int], str],
                  min_freq: int = 3,
                  top_k: int = 3) -> List[Dict]:
    print(f"  reverse aligning {lang}...", flush=True)
    target_verses = load_verses(target_path)
    shared = set(en_verses.keys()) & set(target_verses.keys())
    print(f"    {len(shared):,} parallel verses", flush=True)

    en_count: Counter = Counter()
    tgt_count: Counter = Counter()
    cooc: Dict[str, Counter] = defaultdict(Counter)  # tgt → {en → N}

    for key in shared:
        en_set = set(en_tokens(en_verses[key]))
        tgt_set = set(target_tokens(lang, target_verses[key]))
        for et in en_set:
            en_count[et] += 1
        for tt in tgt_set:
            tgt_count[tt] += 1
        for tt in tgt_set:
            for et in en_set:
                cooc[tt][et] += 1

    print(f"    {len(tgt_count):,} target tokens, {len(en_count):,} EN tokens", flush=True)

    results: List[Dict] = []
    for tt, tt_freq in sorted(tgt_count.items()):
        if tt_freq < min_freq:
            continue
        candidates: List[Tuple[str, float, int]] = []
        for et, c in cooc[tt].items():
            if c < min_freq:
                continue
            et_freq = en_count[et]
            if et_freq < min_freq:
                continue
            dice = (2.0 * c) / (tt_freq + et_freq)
            candidates.append((et, dice, c))
        if not candidates:
            continue
        candidates.sort(key=lambda x: (-x[1], -x[2]))
        results.append({
            "src": tt,
            "freq": tt_freq,
            "candidates": [
                {"text": et, "score": round(d, 3), "freq": c}
                for et, d, c in candidates[:top_k]
            ],
        })
    print(f"    {len(results):,} aligned target tokens kept", flush=True)
    return results


def main() -> int:
    if not EN_FILE.exists():
        print(f"missing English source: {EN_FILE}", file=sys.stderr)
        return 1
    print(f"loading English ({EN_FILE})...", flush=True)
    en_verses = load_verses(EN_FILE)
    print(f"  {len(en_verses):,} English verses indexed", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, int] = {}
    for lang, path in TARGETS.items():
        rows = align_reverse(lang, path, en_verses)
        out_file = OUT_DIR / f"{lang}_to_en.jsonl"
        with out_file.open("w", encoding="utf-8") as out:
            for r in rows:
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
        summary[lang] = len(rows)
        print(f"  -> wrote {len(rows):,} rows to {out_file.name}", flush=True)

    print()
    print("=== Summary ===")
    for lang, n in summary.items():
        print(f"  {lang}_to_en: {n:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
