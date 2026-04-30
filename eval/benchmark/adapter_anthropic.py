"""Anthropic adapter: claude_alone vs claude_with_tools.

Two completion-fn factories:

    claude_alone(model)      -> a fn(messages) that just calls the model.
    claude_with_tools(model) -> a fn(messages) that runs a tool-use loop with
                                the concordance verifier tools available.

Both return the assistant's final text. Drop them into eval/benchmark/runner.run().

Usage:

    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...

    from eval.benchmark.runner import run
    from eval.benchmark.adapter_anthropic import claude_alone, claude_with_tools

    a = run(claude_alone("claude-haiku-4-5-20251001"),     label="haiku-alone")
    b = run(claude_with_tools("claude-haiku-4-5-20251001"), label="haiku-tools")

    print(a.summary())
    print(b.summary())
    a.to_jsonl(Path("eval/benchmark/results_haiku_alone.jsonl"))
    b.to_jsonl(Path("eval/benchmark/results_haiku_tools.jsonl"))
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))


# Tool schemas in the format the Anthropic Messages API expects.
# A subset of the verifier toolbox — the three tools that map cleanly to the
# benchmark's three domains.
ANTHROPIC_TOOLS = [
    {
        "name": "verify_chemistry",
        "description": (
            "Verify a chemical equation balances atoms and charges, "
            "or compute the smallest balancing coefficients. Use this whenever "
            "asked whether a chemical equation is balanced."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string",
                              "description": "The equation, e.g. '2 H2 + O2 -> 2 H2O'"},
                "temperature_K": {"type": "number"},
            },
            "required": ["equation"],
        },
    },
    {
        "name": "verify_physics_dimensional",
        "description": (
            "Reduce both sides of a physics equation to base SI units and check "
            "they match. Use this for any 'is this equation dimensionally consistent' "
            "question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string"},
                "symbols": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Map each symbol to its unit name, e.g. "
                                   "{'F': 'newton', 'm': 'kilogram', 'a': 'meter/second**2'}",
                },
            },
            "required": ["equation", "symbols"],
        },
    },
    {
        "name": "verify_statistics_pvalue",
        "description": (
            "Recompute the p-value of a statistical test from raw inputs. "
            "Tests supported: two_sample_t, one_sample_t, paired_t, z, chi2, f, "
            "one_proportion_z, two_proportion_z, fisher_exact, mannwhitney, "
            "wilcoxon_signed_rank, regression_coefficient_t. Use this for any "
            "p-value computation question."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "spec": {
                    "type": "object",
                    "description": (
                        "Test inputs. Examples: "
                        "{test:'two_sample_t', n1:30, n2:30, mean1:5.0, mean2:4.0, sd1:1.0, sd2:1.0, tail:'two'}; "
                        "{test:'paired_t', n:20, mean_diff:0.5, sd_diff:1.0, tail:'two'}; "
                        "{test:'one_proportion_z', n:200, successes:110, p0:0.5, tail:'two'}; "
                        "{test:'fisher_exact', table:[[8,2],[1,5]], tail:'two'}."
                    ),
                },
            },
            "required": ["spec"],
        },
    },
]


def _dispatch_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Call the actual concordance-engine tool by name."""
    from concordance_engine.mcp_server.tools import ALL_TOOLS  # noqa: WPS433
    fn = ALL_TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        return fn(**args)
    except TypeError:
        # Some tools take positional args; try unpacking single dict
        try:
            return fn(args)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _to_anthropic_messages(messages: List[Dict[str, str]]):
    """Split chat-completions style messages into (system, anthropic_messages)."""
    system = ""
    out = []
    for m in messages:
        if m["role"] == "system":
            system = m["content"]
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return system, out


def claude_alone(model: str = "claude-haiku-4-5-20251001",
                 max_tokens: int = 256) -> Callable[[List[Dict[str, str]]], str]:
    """Plain completion — no tools. Returns the assistant's text."""
    from anthropic import Anthropic

    client = Anthropic()

    def fn(messages):
        system, msgs = _to_anthropic_messages(messages)
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=system, messages=msgs,
        )
        # Concatenate all text blocks
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()

    return fn


def claude_with_tools(model: str = "claude-haiku-4-5-20251001",
                       max_tokens: int = 1024,
                       max_iterations: int = 5,
                       tools: List[Dict[str, Any]] = None
                       ) -> Callable[[List[Dict[str, str]]], str]:
    """Tool-use loop. Returns the assistant's final text after tool calls resolve."""
    from anthropic import Anthropic

    client = Anthropic()
    tools = tools or ANTHROPIC_TOOLS

    def fn(messages):
        system, msgs = _to_anthropic_messages(messages)
        history = list(msgs)
        for _ in range(max_iterations):
            resp = client.messages.create(
                model=model, max_tokens=max_tokens,
                system=system, messages=history, tools=tools,
            )
            # Add the assistant turn (mixed text + tool_use blocks) to history
            history.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                # Extract final text and return
                parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
                return "".join(parts).strip()

            # Otherwise, dispatch every tool_use block and add tool_result blocks.
            tool_results = []
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use":
                    out = _dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(out),
                    })
            if tool_results:
                history.append({"role": "user", "content": tool_results})
            else:
                break  # nothing to dispatch; bail
        # Hit iteration cap — return whatever text was last produced
        last = history[-1] if history else {}
        if isinstance(last.get("content"), list):
            parts = [b.text for b in last["content"] if getattr(b, "type", "") == "text"]
            return "".join(parts).strip() or "[no final text after tool loop]"
        return "[no final text after tool loop]"

    return fn


def run_both(model: str = "claude-haiku-4-5-20251001",
             out_dir: Path = None) -> None:
    """Convenience: run both modes and save results JSONL plus a comparison."""
    # Path-based import so this works whether the file is run as a script
    # ("python eval/benchmark/adapter_anthropic.py") or as a module.
    sys.path.insert(0, str(THIS.parent))
    from runner import run as bench_run  # type: ignore

    out_dir = out_dir or THIS.parent
    a = bench_run(claude_alone(model), label=f"{model} (alone)")
    b = bench_run(claude_with_tools(model), label=f"{model} (with tools)")

    (out_dir / f"results_{model}_alone.jsonl").write_text(
        "\n".join(
            __import__("json").dumps({
                "id": r.id, "domain": r.domain, "task": r.task,
                "correct": r.correct, "reply": r.reply, "detail": r.detail,
            }) for r in a.items
        ) + "\n"
    )
    (out_dir / f"results_{model}_tools.jsonl").write_text(
        "\n".join(
            __import__("json").dumps({
                "id": r.id, "domain": r.domain, "task": r.task,
                "correct": r.correct, "reply": r.reply, "detail": r.detail,
            }) for r in b.items
        ) + "\n"
    )

    print()
    print(a.summary())
    print()
    print(b.summary())
    print()

    # Per-item comparison
    by_id_a = {r.id: r for r in a.items}
    fixed_by_tools = []
    broken_by_tools = []
    for r in b.items:
        a_r = by_id_a.get(r.id)
        if a_r is None:
            continue
        if r.correct and not a_r.correct:
            fixed_by_tools.append(r.id)
        if a_r.correct and not r.correct:
            broken_by_tools.append(r.id)
    print(f"Items the engine fixed: {len(fixed_by_tools)}")
    for x in fixed_by_tools:
        print(f"  + {x}")
    print(f"Items the engine broke (regressions): {len(broken_by_tools)}")
    for x in broken_by_tools:
        print(f"  - {x}")


if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY first.", file=sys.stderr)
        sys.exit(1)
    run_both()
