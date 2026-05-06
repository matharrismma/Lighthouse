"""
Uses claude-haiku-4-5-20251001 with verifier tools to solve training items.
Records the full tool-call trace (question → tool_call → result → answer).

For each CONFIRMED item in the training corpus, the model is asked to answer
the question using the appropriate domain verifier tool. The trace is saved so
it can be used as golden examples for retrieval / reasoning training.

Output: eval/training/golden_traces.jsonl

Each output line:
{
  "id": "...",
  "domain": "...",
  "question": "...",
  "tool_calls": [{"tool": "verify_thermodynamics", "spec": {...}, "result": {...}}],
  "model_answer": "...",
  "ground_truth_answer": "...",
  "correct": true
}

Usage:
    python eval/training/run_training_collection.py
    python eval/training/run_training_collection.py --max-items 100
    python eval/training/run_training_collection.py \
        --input eval/training/training_corpus.jsonl \
        --output eval/training/golden_traces.jsonl \
        --max-items 500
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_INPUT = _REPO_ROOT / "eval" / "training" / "training_corpus.jsonl"
_DEFAULT_OUTPUT = _REPO_ROOT / "eval" / "training" / "golden_traces.jsonl"
_MODEL = "claude-haiku-4-5-20251001"
_BATCH_SIZE = 10
_BATCH_SLEEP = 1.0  # seconds between batches

# ---------------------------------------------------------------------------
# Per-domain tool schemas (Anthropic SDK format)
# ---------------------------------------------------------------------------

_TOOL_SCHEMAS: Dict[str, Dict[str, Any]] = {
    "thermodynamics": {
        "name": "verify_thermodynamics",
        "description": (
            "Verify thermodynamics calculations including Carnot efficiency "
            "(η = 1 − T_cold/T_hot), specific heat (Q = mcΔT), ideal gas law "
            "(PV = nRT), and entropy change (ΔS = Q/T). "
            "Pass the full THERMO_VERIFY spec dict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "THERMO_VERIFY spec. For Carnot: {T_hot_K, T_cold_K, claimed_efficiency}. "
                        "For specific heat: {mass_kg, specific_heat_J_per_kgK, delta_T_K, claimed_heat_J}."
                    ),
                }
            },
            "required": ["spec"],
        },
    },
    "nuclear_physics": {
        "name": "verify_nuclear_physics",
        "description": (
            "Verify nuclear physics calculations including radioactive decay "
            "N(t) = N₀ × e^(−λt), binding energy per nucleon, half-life from "
            "activity, and decay constant. Pass the full NUCLEAR_VERIFY spec dict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "NUCLEAR_VERIFY spec. For decay: "
                        "{half_life_seconds, elapsed_seconds, initial_count, claimed_remaining_count}."
                    ),
                }
            },
            "required": ["spec"],
        },
    },
    "ecology": {
        "name": "verify_ecology",
        "description": (
            "Verify ecology calculations including trophic efficiency "
            "(output = input × efficiency^levels), logistic growth, Shannon "
            "diversity, and carbon footprint. Pass the full ECO_VERIFY spec dict."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "ECO_VERIFY spec. For trophic efficiency: "
                        "{energy_input, trophic_levels_up, trophic_efficiency, claimed_energy_output}."
                    ),
                }
            },
            "required": ["spec"],
        },
    },
    "history_chronology": {
        "name": "verify_history_chronology",
        "description": (
            "Verify history and chronology calculations: elapsed years between "
            "two CE dates (elapsed = to_year − from_year) and century assignment "
            "(century = ceil(year / 100))."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "For year_elapsed: {from_year_CE, to_year_CE, claimed_elapsed_years}. "
                        "For century_assignment: {year_CE, claimed_century}."
                    ),
                }
            },
            "required": ["spec"],
        },
    },
    "economics": {
        "name": "verify_economics",
        "description": (
            "Verify economics calculations: compound interest A = P(1+r/n)^(nt), "
            "simple interest I = Prt, present/future value, rule of 72, "
            "inflation-adjusted value, GDP per capita, price elasticity."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "ECON_VERIFY spec. For compound interest: "
                        "{principal, rate, time_years, compounding_periods, claimed_compound_amount}."
                    ),
                }
            },
            "required": ["spec"],
        },
    },
}

# Fallback for domains not in the table
_GENERIC_TOOL = {
    "name": "verify_generic",
    "description": "Verify a calculation using the Concordance engine.",
    "input_schema": {
        "type": "object",
        "properties": {
            "spec": {"type": "object", "description": "Verification spec dict."}
        },
        "required": ["spec"],
    },
}


# ---------------------------------------------------------------------------
# Local tool dispatch — no network call; runs the actual verifier
# ---------------------------------------------------------------------------

def _dispatch_tool(domain: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the real verifier locally and return a JSON-serialisable result dict.
    This keeps the ground truth deterministic even when the model calls the tool.
    """
    try:
        if domain == "thermodynamics":
            from concordance_engine.verifiers.thermodynamics import (
                verify_carnot_efficiency, verify_specific_heat,
            )
            if "claimed_efficiency" in spec:
                r = verify_carnot_efficiency(spec)
            else:
                r = verify_specific_heat(spec)
            return {"status": r.status, "detail": r.detail, "data": r.data}

        elif domain == "nuclear_physics":
            from concordance_engine.verifiers.nuclear_physics import verify_radioactive_decay
            r = verify_radioactive_decay(spec)
            return {"status": r.status, "detail": r.detail, "data": r.data}

        elif domain == "ecology":
            from concordance_engine.verifiers.ecology import verify_trophic_efficiency
            r = verify_trophic_efficiency(spec)
            return {"status": r.status, "detail": r.detail, "data": r.data}

        elif domain == "history_chronology":
            # Pure arithmetic — no dedicated verifier; compute inline
            if "claimed_elapsed_years" in spec:
                actual = spec["to_year_CE"] - spec["from_year_CE"]
                claimed = spec["claimed_elapsed_years"]
                status = "CONFIRMED" if claimed == actual else "MISMATCH"
                return {"status": status, "actual_elapsed_years": actual, "claimed": claimed}
            elif "claimed_century" in spec:
                import math as _math
                actual = _math.ceil(spec["year_CE"] / 100)
                claimed = spec["claimed_century"]
                status = "CONFIRMED" if claimed == actual else "MISMATCH"
                return {"status": status, "actual_century": actual, "claimed": claimed}
            return {"error": "unrecognised history_chronology spec keys"}

        elif domain == "economics":
            from concordance_engine.verifiers.economics import verify_compound_interest
            r = verify_compound_interest(spec)
            return {"status": r.status, "detail": r.detail, "data": r.data}

        else:
            return {"error": f"no local dispatch for domain {domain!r}"}

    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Tool schema lookup
# ---------------------------------------------------------------------------

def _tool_for_domain(domain: str) -> Dict[str, Any]:
    return _TOOL_SCHEMAS.get(domain, _GENERIC_TOOL)


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are a verification assistant for the Concordance knowledge engine. "
    "When asked to solve a quantitative question, you MUST use the available "
    "verification tool to compute the ground-truth answer. "
    "After the tool returns, state the answer clearly and concisely."
)


# ---------------------------------------------------------------------------
# Single-item processing
# ---------------------------------------------------------------------------

def _process_item(
    client: Any,
    item: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Send one training item to the model with the domain's verifier tool.
    Returns a golden-trace record.
    """
    domain = item["domain"]
    tool_def = _tool_for_domain(domain)
    ground_truth_answer = item["answer"]
    question = item["question"]

    messages = [{"role": "user", "content": question}]

    # --- First call: model should issue a tool_use ---
    resp = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=_SYSTEM,
        messages=messages,
        tools=[tool_def],
    )

    recorded_tool_calls: List[Dict[str, Any]] = []
    history = list(messages)
    history.append({"role": "assistant", "content": resp.content})

    if resp.stop_reason == "tool_use":
        # Dispatch every tool_use block locally
        tool_results = []
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use":
                tool_input = block.input or {}
                spec_arg = tool_input.get("spec", tool_input)  # accept either wrapper or flat
                result = _dispatch_tool(domain, spec_arg)
                recorded_tool_calls.append({
                    "tool": block.name,
                    "spec": spec_arg,
                    "result": result,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })
        if tool_results:
            history.append({"role": "user", "content": tool_results})
            # Second call: model synthesises its final answer
            resp2 = client.messages.create(
                model=_MODEL,
                max_tokens=256,
                system=_SYSTEM,
                messages=history,
                tools=[tool_def],
            )
            resp = resp2

    # Extract final model text
    text_parts = [
        b.text for b in resp.content if getattr(b, "type", "") == "text"
    ]
    model_answer = "".join(text_parts).strip()

    # Rough correctness check: does the ground-truth value appear in the reply?
    correct = ground_truth_answer in model_answer

    return {
        "id": item["id"],
        "domain": domain,
        "check_type": item.get("check_type", ""),
        "question": question,
        "tool_calls": recorded_tool_calls,
        "model_answer": model_answer,
        "ground_truth_answer": ground_truth_answer,
        "correct": correct,
    }


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------

def collect_traces(
    input_path: Path,
    output_path: Path,
    max_items: int = 500,
) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY environment variable not set.",
            file=sys.stderr,
        )
        sys.exit(1)

    # --- Load confirmed items only ---
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        print(
            "Run build_training_corpus.py first to generate the corpus.",
            file=sys.stderr,
        )
        sys.exit(1)

    all_items: List[Dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if obj.get("verifier_result") == "CONFIRMED":
                all_items.append(obj)

    # Cap at max_items
    items = all_items[:max_items]
    total = len(items)
    print(f"Input:     {input_path}")
    print(f"Output:    {output_path}")
    print(f"Model:     {_MODEL}")
    print(f"Items:     {total} CONFIRMED (capped at {max_items})")
    print()

    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    correct_count = 0
    processed = 0

    with output_path.open("a", encoding="utf-8") as out_fh:
        batch_start = 0
        while batch_start < total:
            batch = items[batch_start: batch_start + _BATCH_SIZE]

            for item in batch:
                processed += 1
                try:
                    trace = _process_item(client, item)
                except Exception as exc:
                    trace = {
                        "id": item["id"],
                        "domain": item["domain"],
                        "check_type": item.get("check_type", ""),
                        "question": item["question"],
                        "tool_calls": [],
                        "model_answer": f"[ERROR: {exc}]",
                        "ground_truth_answer": item["answer"],
                        "correct": False,
                    }

                if trace["correct"]:
                    correct_count += 1

                status_char = "+" if trace["correct"] else "-"
                print(
                    f"[{processed:>4}/{total}] {status_char} "
                    f"{trace['domain']:<22} {trace.get('check_type', ''):<24} "
                    f"{'CORRECT' if trace['correct'] else 'WRONG'}"
                )

                out_fh.write(json.dumps(trace, ensure_ascii=False, default=str) + "\n")
                out_fh.flush()

            batch_start += _BATCH_SIZE
            if batch_start < total:
                time.sleep(_BATCH_SLEEP)

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print()
    print("=== Golden Trace Collection Complete ===")
    print(f"Output:    {output_path}")
    print(f"Total:     {processed}")
    print(f"Correct:   {correct_count}  ({100*correct_count/max(processed,1):.1f}%)")
    print(f"Wrong:     {processed - correct_count}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Collect golden tool-call traces from the Concordance training corpus"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=_DEFAULT_INPUT,
        help=f"Input JSONL from build_training_corpus.py (default: {_DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output JSONL for golden traces (default: {_DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=500,
        dest="max_items",
        help="Maximum number of CONFIRMED items to process (default: 500)",
    )
    args = parser.parse_args()
    collect_traces(
        input_path=args.input,
        output_path=args.output,
        max_items=args.max_items,
    )
