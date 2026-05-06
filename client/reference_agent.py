"""
reference_agent.py — An AI agent operating inside the Concordance Engine substrate.

Two behaviors demonstrated:

  VERIFY BEFORE STATE
    The agent calls the engine to check every computational claim before asserting it.
    Wrong answers don't make it into the record. The verifier is the external standard —
    the agent's confidence doesn't override it.

  GATE BEFORE ACT
    Before committing any irreversible decision, the agent constructs a governance packet
    and passes it through the four gates. Nothing records without witness and record.

This is the pattern. The substrate does not change per deployment.

────────────────────────────────────────────────────────────────
Run (standalone — calls narrowhighway.com):

    pip install anthropic
    export ANTHROPIC_API_KEY=sk-ant-...
    python reference_agent.py

Run (local engine):

    export CONCORDANCE_URL=http://localhost:8000
    python reference_agent.py

Run (MCP — if concordance-mcp is configured in your Claude Desktop):

    The same tools this script registers manually are available as
    native MCP tools. Replace the tool_call() dispatch below with
    your MCP client's tool invocation. The tool names and schemas
    are identical.
────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# ── Engine client (REST) ────────────────────────────────────────────────
# Uses concordance_client.py if it's alongside this file; otherwise
# falls back to raw urllib so there are no hard dependencies.

_CLIENT_DIR = Path(__file__).parent
sys.path.insert(0, str(_CLIENT_DIR))

try:
    from concordance_client import Concordance
    _engine = Concordance(
        base_url=os.environ.get("CONCORDANCE_URL", "https://narrowhighway.com")
    )

    def _call_engine(tool: str, args: dict) -> dict:
        if tool == "verify_chemistry":
            return _engine._request("POST", "/verify/chemistry",
                                    json={"equation": args["equation"]})
        if tool == "verify_statistics":
            return _engine._request("POST", "/verify/statistics",
                                    json=args)
        if tool == "verify_physics":
            return _engine._request("POST", "/verify/physics",
                                    json=args)
        if tool == "reflect_packet":
            return _engine.reflect(args["packet"])
        if tool == "submit_packet":
            return _engine.submit(args["packet"])
        if tool == "ask_path":
            return _engine._request("POST", "/path",
                                    json={"text": args["text"]})
        raise ValueError(f"unknown tool: {tool}")

except ImportError:
    import urllib.request
    _BASE = os.environ.get("CONCORDANCE_URL", "https://narrowhighway.com")

    def _call_engine(tool: str, args: dict) -> dict:
        paths = {
            "verify_chemistry": "/verify/chemistry",
            "verify_statistics": "/verify/statistics",
            "verify_physics": "/verify/physics",
            "reflect_packet": "/reflect",
            "submit_packet": "/submit",
            "ask_path": "/path",
        }
        path = paths.get(tool)
        if not path:
            raise ValueError(f"unknown tool: {tool}")
        body = json.dumps(
            args if tool not in ("reflect_packet", "submit_packet")
            else {"packet": args["packet"]}
        ).encode()
        req = urllib.request.Request(
            _BASE + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())


# ── Anthropic SDK ───────────────────────────────────────────────────────

try:
    import anthropic
except ImportError:
    sys.exit("Install anthropic: pip install anthropic")

_anthropic = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

# ── Tool definitions (identical to MCP tool schemas) ───────────────────

TOOLS: list[dict] = [
    {
        "name": "verify_chemistry",
        "description": (
            "Check whether a chemical equation is balanced. "
            "Returns CONFIRMED, MISMATCH, or ERROR. "
            "Call this before stating any chemical equation as fact."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equation": {
                    "type": "string",
                    "description": "The equation to check, e.g. 'CH4 + 2O2 -> CO2 + 2H2O'",
                },
            },
            "required": ["equation"],
        },
    },
    {
        "name": "verify_statistics",
        "description": (
            "Recompute a p-value from raw inputs. "
            "Returns CONFIRMED if the reported p-value matches the recomputed one, "
            "MISMATCH if not. "
            "Call this before stating any statistical result as fact."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "test_type": {
                    "type": "string",
                    "enum": ["two_sample_t", "paired_t", "one_proportion_z", "fisher_exact"],
                },
                "claimed_p": {"type": "number"},
                "t_stat":    {"type": "number"},
                "n1":        {"type": "integer"},
                "n2":        {"type": "integer"},
                "alternative": {
                    "type": "string",
                    "enum": ["two-sided", "less", "greater"],
                    "default": "two-sided",
                },
            },
            "required": ["test_type", "claimed_p"],
        },
    },
    {
        "name": "verify_physics",
        "description": (
            "Check dimensional consistency of a physics equation. "
            "Returns CONFIRMED or MISMATCH. "
            "Call this before stating any physics relationship as fact."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string"},
                "lhs_units": {"type": "string"},
                "rhs_units": {"type": "string"},
            },
            "required": ["equation"],
        },
    },
    {
        "name": "reflect_packet",
        "description": (
            "Rehearse a governance decision through all four gates without committing to the ledger. "
            "Use this before every real submission. "
            "Iterate until the result is what you intend, then call submit_packet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "packet": {
                    "type": "object",
                    "description": "Governance decision packet.",
                    "properties": {
                        "title":    {"type": "string"},
                        "decision": {"type": "string"},
                        "rationale":  {"type": "array", "items": {"type": "string"}},
                        "scope":      {"type": "array", "items": {"type": "string"}},
                        "authority":  {"type": "string"},
                        "witnesses":  {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "role": {"type": "string"},
                                    "timestamp_epoch": {"type": "integer"},
                                },
                            },
                        },
                        "submission_timestamp_epoch": {"type": "integer"},
                    },
                    "required": ["title", "decision", "rationale", "scope",
                                 "authority", "witnesses"],
                },
            },
            "required": ["packet"],
        },
    },
    {
        "name": "submit_packet",
        "description": (
            "Commit a governance decision to the permanent ledger. "
            "The record cannot be altered after this call. "
            "Only call after reflect_packet returns a passing result."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "packet": {"type": "object"},
            },
            "required": ["packet"],
        },
    },
]

# ── System prompt ───────────────────────────────────────────────────────

SYSTEM = """You are an agent operating inside the Concordance Engine substrate.

Two rules govern everything you do:

RULE 1 — VERIFY BEFORE STATE
Before asserting any chemistry, physics, statistics, or mathematics claim as fact,
call the appropriate verifier. If it returns MISMATCH, correct your answer. If it
returns ERROR, say so. Never state a computational claim without checking it first.

RULE 2 — GATE BEFORE ACT
Before committing any irreversible decision, call reflect_packet to rehearse it
through the four gates. If it passes, call submit_packet to record it permanently.
If it fails, fix what failed and rehearse again. Never commit without the gates clearing.

The engine is the external standard. Your confidence does not override it.
The ledger is permanent. The record of what you decided will not change.
"""

# ── Task ────────────────────────────────────────────────────────────────

TASK = """
Review this research proposal and make a funding recommendation.

CLAIM 1 (Chemistry):
The team states that methane combustion is: CH4 + 2O2 → CO2 + 2H2O
They plan to use this reaction as the basis for an energy yield model.

CLAIM 2 (Statistics):
A pilot study shows the intervention is effective:
  t-stat = 2.18, n1 = 25, n2 = 25, reported p = 0.034 (two-tailed)

TASK:
1. Verify both claims before accepting them.
2. If both hold, recommend funding and commit that recommendation to the ledger.
   Witness: Dr. Sarah Chen, role: Principal Investigator.
   Authority: Research Funding Committee.
3. If either claim fails, do not commit — explain what failed and why.
"""

# ── Agent loop ──────────────────────────────────────────────────────────

def run(task: str = TASK, model: str = "claude-sonnet-4-6") -> None:
    print(f"\n{'═'*60}")
    print("CONCORDANCE ENGINE — REFERENCE AGENT")
    print(f"Model: {model}")
    print(f"Engine: {os.environ.get('CONCORDANCE_URL', 'https://narrowhighway.com')}")
    print(f"{'═'*60}\n")
    print("TASK:")
    print(task.strip())
    print(f"\n{'─'*60}\n")

    messages: list[dict] = [{"role": "user", "content": task}]

    while True:
        response = _anthropic.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text and tool calls from this turn
        tool_calls: list[Any] = []
        for block in response.content:
            if hasattr(block, "text"):
                print(f"AGENT: {block.text}\n")
            elif block.type == "tool_use":
                tool_calls.append(block)

        # If no tool calls and stop reason is end_turn, we're done
        if not tool_calls:
            break

        # Execute tool calls and collect results
        tool_results: list[dict] = []
        for call in tool_calls:
            print(f"  → {call.name}({json.dumps(call.input, indent=4)})")
            try:
                result = _call_engine(call.name, call.input)
                status = (
                    result.get("result") or
                    result.get("overall") or
                    result.get("status") or
                    "ok"
                )
                print(f"  ← {status}\n")
            except Exception as exc:
                result = {"error": str(exc)}
                print(f"  ← ERROR: {exc}\n")

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": json.dumps(result),
            })

        # Append assistant turn + tool results and continue
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    print(f"\n{'═'*60}")
    print("DONE")
    print(f"{'═'*60}\n")


if __name__ == "__main__":
    run()
