"""
Concordance Agent — Path B (oracle layer).

Routes natural-language claims to deterministic verifiers via Claude tool use.
Called when the rule-based dispatcher (dispatch.py) finds no matching rule.

Two outputs from every oracle call:
  1. A structured VerifyResult for the immediate caller.
  2. A training example written to data/agent_training/{domain}.jsonl
     so rule_extractor.py can mine it and propose new regex rules for
     promotion into dispatch.py. The agent teaches itself to need itself
     less over time.

The strength of the engine is the *connections* between domains. When
multiple verifiers independently confirm the same claim from different axes
of the dimensional grid, that convergence is surfaced explicitly. Single-axis
CONFIRMED is weaker evidence than convergent CONFIRMED across orthogonal axes.

Usage:
    from concordance_engine.agent.claude_agent import verify_claim

    result = verify_claim("SHA-256 of 'hello' is 2cf24dba...")
    print(result["verdict"])         # CONFIRMED
    print(result["domains"])         # ["cryptography"]
    print(result["cross_domain"])    # False (only one domain)

    result = verify_claim("1kg at c carries 9e16 J of energy per E=mc^2")
    print(result["domains"])         # ["physics_dimensional", "mathematics"]
    print(result["cross_domain"])    # True
    print(result["axes"])            # ["signal_wave", "measurement_reasoning", ...]
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import anthropic as _anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False

from ..mcp_server.tools import TOOLS, TOOL_BY_NAME

# ---------------------------------------------------------------------------
# Domain axis grid
# Each axis groups domains that share a structural dimension.
# When a claim touches one domain, adjacent domains on the same axis are
# natural candidates for cross-verification — convergent CONFIRMED across
# orthogonal axes is the strongest signal the engine can produce.
# ---------------------------------------------------------------------------

DOMAIN_AXES: Dict[str, List[str]] = {
    "information_encoding": [
        "genetics", "cryptography", "information_theory", "linguistics",
        "networking", "computer_science",
    ],
    "physical_substance": [
        "chemistry", "physics_conservation", "physics_dimensional",
        "geology", "construction", "soil_science",
    ],
    "time_sequence": [
        "calendar_time", "astronomy", "formal_logic",
    ],
    "conservation_balance": [
        "physics_conservation", "finance", "energy", "labor",
        "economics", "real_estate",
    ],
    "metabolism": [
        "nutrition", "medicine", "exercise_science", "biology",
        "genetics", "agriculture",
    ],
    "authority_trust": [
        "governance", "witness", "linguistics",
    ],
    "measurement_reasoning": [
        "mathematics", "statistics", "formal_logic", "number_theory",
        "combinatorics",
    ],
    "spatial_structural": [
        "geometry", "geography", "construction", "hydrology",
    ],
    "signal_wave": [
        "acoustics", "optics", "physics_dimensional", "meteorology",
        "electrical", "quantum_computing",
    ],
    "life_system": [
        "medicine", "biology", "nutrition", "exercise_science",
        "agriculture", "soil_science",
    ],
}

_DOMAIN_TO_AXES: Dict[str, List[str]] = {}
for _axis, _doms in DOMAIN_AXES.items():
    for _d in _doms:
        _DOMAIN_TO_AXES.setdefault(_d, []).append(_axis)


def axes_for_domain(domain: str) -> List[str]:
    return _DOMAIN_TO_AXES.get(domain, [])


def adjacent_domains(domain: str) -> List[str]:
    """Domains that share at least one axis with the given domain."""
    seen: set = set()
    for axis in axes_for_domain(domain):
        for d in DOMAIN_AXES[axis]:
            if d != domain:
                seen.add(d)
    return sorted(seen)


# ---------------------------------------------------------------------------
# Anthropic tool definitions (converted from TOOLS list)
# ---------------------------------------------------------------------------

def _build_tool_defs() -> List[Dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
        for t in TOOLS
    ]


_TOOL_DEFS: List[Dict[str, Any]] = _build_tool_defs()


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are the Concordance routing agent. The Concordance Engine is the authority — not you.

YOUR JOB:
1. Read the claim carefully.
2. Identify which verify_* tool(s) can evaluate it deterministically.
3. Extract the exact numeric/symbolic parameters explicitly stated in the claim.
4. Call the most relevant tool first. Then consider whether adjacent domains apply.
5. After each tool result, relay the verdict in this structured format:

   VERDICT: [CONFIRMED|MISMATCH|NOT_APPLICABLE|ERROR]
   DOMAIN: [domain name]
   DETAIL: [one sentence from the tool's detail field]

THE GRID — 48 domains organized around shared dimensional axes:
  information_encoding : genetics, cryptography, information_theory, linguistics, networking, computer_science
  physical_substance   : chemistry, physics_conservation, physics_dimensional, geology, construction, soil_science
  time_sequence        : calendar_time, astronomy, formal_logic
  conservation_balance : physics_conservation, finance, energy, labor, economics, real_estate
  metabolism           : nutrition, medicine, exercise_science, biology, genetics, agriculture
  measurement_reasoning: mathematics, statistics, formal_logic, number_theory, combinatorics
  spatial_structural   : geometry, geography, construction, hydrology
  signal_wave          : acoustics, optics, physics_dimensional, meteorology, electrical, quantum_computing
  life_system          : medicine, biology, nutrition, exercise_science, agriculture, soil_science

CROSS-DOMAIN RULE: When a claim spans multiple axes, call a verifier for each
relevant axis. Convergent CONFIRMED across axes is stronger than single-domain
CONFIRMED. State the axes when convergence occurs.

RULES:
- You MUST call at least one verify_* tool before giving your final answer.
- Do NOT assert a verdict without calling a tool first.
- Do NOT fabricate parameter values. Only extract what is explicitly stated.
- If parameters are insufficient, call with what is present. NOT_APPLICABLE is valid.
- After all tool calls, give a brief cross-domain summary if multiple domains fired.
- The engine's result is the verdict. You are the router; the engine is the judge.
"""


# ---------------------------------------------------------------------------
# Verdict extraction
# ---------------------------------------------------------------------------

def _extract_verdict(result: Any) -> str:
    """Walk a tool result and return the dominant meaningful verdict.

    NOT_APPLICABLE results mean the spec didn't trigger any check (missing
    fields). They are neutral — not a real engine disagreement. Only
    MISMATCH from a check that actually computed something is negative.
    """
    if not isinstance(result, dict):
        return "UNKNOWN"
    top = result.get("status")
    if top and top not in ("", None):
        return top

    # Collect statuses from checks list and nested dicts
    all_statuses: List[str] = []
    for c in result.get("checks", []):
        if isinstance(c, dict):
            s = c.get("status", "")
            if s:
                all_statuses.append(s)
    for v in result.values():
        if isinstance(v, dict):
            s = v.get("status", "")
            if s:
                all_statuses.append(s)

    # Meaningful statuses: checks that actually ran (not just "no artifact")
    meaningful = [s for s in all_statuses if s not in ("NOT_APPLICABLE",)]
    ranked = meaningful if meaningful else all_statuses

    if "MISMATCH" in ranked:
        return "MISMATCH"
    if "ERROR" in ranked:
        return "ERROR"
    if "CONFIRMED" in ranked:
        return "CONFIRMED"
    if "NOT_APPLICABLE" in all_statuses:
        return "NOT_APPLICABLE"
    return ranked[0] if ranked else "UNKNOWN"


def _is_meaningful_call(tool_call: Dict[str, Any]) -> bool:
    """Return True if the tool call produced an actual verdict (not just NOT_APPLICABLE)."""
    return tool_call.get("verdict") not in ("NOT_APPLICABLE", "UNKNOWN", "ERROR")


# ---------------------------------------------------------------------------
# Training log — feeds rule_extractor.py
# ---------------------------------------------------------------------------

def _log_oracle_call(
    claim_text: str,
    domain: str,
    spec: Dict[str, Any],
    summary: str,
    training_dir: Optional[Path],
) -> None:
    if training_dir is None:
        return
    try:
        training_dir.mkdir(parents=True, exist_ok=True)
        log_file = training_dir / f"{domain}.jsonl"
        entry = {
            "text": claim_text,
            "domain": domain,
            "spec": spec,
            "summary": summary,
            "source": "oracle",
            "ts": int(time.time()),
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core agent
# ---------------------------------------------------------------------------

def verify_claim(
    claim_text: str,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
    max_tool_rounds: int = 6,
    training_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Route a natural-language claim through the Concordance Engine.

    Args:
        claim_text:    The natural-language claim to verify.
        model:         Claude model to use for routing.
        api_key:       Anthropic API key (falls back to ANTHROPIC_API_KEY env var).
        max_tool_rounds: Maximum tool-call rounds before forcing a relay.
        training_dir:  If set, log oracle calls here for rule_extractor.py.

    Returns a dict:
        claim         — original claim text
        verdict       — dominant verdict: CONFIRMED|MISMATCH|NOT_APPLICABLE|ERROR|NO_TOOL_CALLED
        domains       — list of domain names that fired (one per tool call)
        axes          — grid axes touched (union across all fired domains)
        cross_domain  — True if more than one domain fired
        tool_calls    — [{tool, domain, args, result, verdict}, ...]
        relay_text    — Claude's structured relay after tool calls
        latency_ms    — wall-clock milliseconds
    """
    if not _ANTHROPIC_AVAILABLE:
        return {
            "claim": claim_text,
            "verdict": "ERROR",
            "error": "anthropic package not installed. Run: pip install anthropic",
        }

    _api_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or None
    if not _api_key:
        return {
            "claim": claim_text,
            "verdict": "ERROR",
            "error": "ANTHROPIC_API_KEY not set",
        }

    client = _anthropic.Anthropic(api_key=_api_key)
    t0 = time.time()

    messages: List[Dict[str, Any]] = [{"role": "user", "content": claim_text}]
    tool_calls: List[Dict[str, Any]] = []
    relay_text: Optional[str] = None

    for _round in range(max_tool_rounds):
        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            tools=_TOOL_DEFS,
            messages=messages,
        )

        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if not tool_use_blocks:
            if text_blocks:
                relay_text = "\n".join(b.text for b in text_blocks).strip()
            break

        tool_results_for_msg = []
        for tub in tool_use_blocks:
            tool_name = tub.name
            tool_input = dict(tub.input)
            tool_entry = TOOL_BY_NAME.get(tool_name)
            if tool_entry:
                try:
                    tool_result = tool_entry["fn"](tool_input)
                except Exception as exc:
                    tool_result = {"status": "ERROR", "error": str(exc)}
            else:
                tool_result = {"status": "ERROR", "error": f"unknown tool: {tool_name}"}

            call_verdict = _extract_verdict(tool_result)
            domain = tool_name.replace("verify_", "") if tool_name.startswith("verify_") else tool_name

            tool_calls.append({
                "tool": tool_name,
                "domain": domain,
                "args": tool_input,
                "result": tool_result,
                "verdict": call_verdict,
            })

            # Log for rule_extractor training pipeline
            _log_oracle_call(claim_text, domain, tool_input, call_verdict, training_dir)

            tool_results_for_msg.append({
                "type": "tool_result",
                "tool_use_id": tub.id,
                "content": json.dumps(tool_result),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results_for_msg})

        if response.stop_reason == "end_turn":
            break

    # Get relay text if not already captured
    if tool_calls and relay_text is None:
        relay_response = client.messages.create(
            model=model,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            tools=_TOOL_DEFS,
            messages=messages,
        )
        for b in relay_response.content:
            if b.type == "text":
                relay_text = b.text.strip()
                break

    # Aggregate results
    # Per-domain best verdict: when the same domain is called multiple times (agent
    # refining its spec), take the best result — CONFIRMED from any call counts.
    # This prevents a first-call spec miss from overriding a later correct CONFIRMED.
    _verdict_rank = {"CONFIRMED": 0, "MISMATCH": 1, "NOT_APPLICABLE": 2, "ERROR": 3, "UNKNOWN": 4}
    per_domain_best: Dict[str, str] = {}
    for tc in tool_calls:
        d, v = tc["domain"], tc["verdict"]
        prev = per_domain_best.get(d, "UNKNOWN")
        if _verdict_rank.get(v, 99) < _verdict_rank.get(prev, 99):
            per_domain_best[d] = v

    meaningful_calls = [tc for tc in tool_calls if _is_meaningful_call(tc)]
    all_verdicts = [tc["verdict"] for tc in tool_calls]
    # Use per-domain best for the cross-domain aggregate
    meaningful_domain_verdicts = [v for v in per_domain_best.values() if v not in ("NOT_APPLICABLE", "UNKNOWN", "ERROR")]
    domains_fired = [tc["domain"] for tc in tool_calls]
    axes_touched: List[str] = []
    for d in domains_fired:
        for ax in axes_for_domain(d):
            if ax not in axes_touched:
                axes_touched.append(ax)

    # Priority: MISMATCH > CONFIRMED > NOT_APPLICABLE
    # A domain is MISMATCH only if the BEST call for that domain was MISMATCH
    if "MISMATCH" in meaningful_domain_verdicts:
        aggregate = "MISMATCH"
    elif "CONFIRMED" in meaningful_domain_verdicts:
        aggregate = "CONFIRMED"
    elif meaningful_domain_verdicts:
        aggregate = meaningful_domain_verdicts[0]
    elif "NOT_APPLICABLE" in all_verdicts:
        aggregate = "NOT_APPLICABLE"
    elif all_verdicts:
        aggregate = all_verdicts[0]
    else:
        aggregate = "NO_TOOL_CALLED"

    return {
        "claim": claim_text,
        "verdict": aggregate,
        "domains": domains_fired,
        "axes": axes_touched,
        "cross_domain": len(set(domains_fired)) > 1,
        "tool_calls": tool_calls,
        "relay_text": relay_text,
        "latency_ms": round((time.time() - t0) * 1000, 1),
    }
