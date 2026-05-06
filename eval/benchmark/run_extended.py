"""Run the extended benchmark across all domains.

Two modes:
  alone  — Claude with no tools
  tools  — Claude with all concordance-engine MCP tools

Usage:
    python eval/benchmark/run_extended.py
    python eval/benchmark/run_extended.py --model claude-sonnet-4-6
    python eval/benchmark/run_extended.py --alone-only   (skip tools run)
    python eval/benchmark/run_extended.py --tools-only   (skip alone run)
    python eval/benchmark/run_extended.py --diagnose     (print details on failures)
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time

# Force UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

# Load .env
_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()


# ── scoring ──────────────────────────────────────────────────────────────────

_SUP_TO_EXP = {
    "⁰": "**0", "¹": "**1", "²": "**2", "³": "**3", "⁴": "**4",
    "⁵": "**5", "⁶": "**6", "⁷": "**7", "⁸": "**8", "⁹": "**9",
}

def _norm_math(s: str) -> str:
    """Normalize math expressions: Unicode superscripts, implicit multiply, spacing."""
    # Replace Unicode superscripts *as exponents* (must happen before any digit stripping)
    for char, rep in _SUP_TO_EXP.items():
        s = s.replace(char, rep)
    s = re.sub(r"(\w)\^(\d+)", r"\1**\2", s)        # x^2 → x**2
    s = re.sub(r"(\d)([a-z])", r"\1*\2", s)          # 3x → 3*x
    s = re.sub(r"\s*\*\*\s*", "**", s)
    s = re.sub(r"(?<!\*)\*(?!\*)", "*", s)            # single * spacing only
    return s.strip()


def _parse_reply(reply: str, answer_kind: str) -> Any:
    """Extract the answer token from model reply."""
    reply = reply.strip().lower()
    if answer_kind == "classification":
        if re.search(r"\byes\b", reply):
            return "yes"
        if re.search(r"\bno\b", reply):
            return "no"
        return reply.split()[0] if reply else ""
    if answer_kind == "numeric":
        # Allow leading-decimal numbers like .300; use LAST match so "I = V/R = 5/10 = 0.5"
        # returns 0.5 rather than 5.
        nums = re.findall(r"-?\d*\.?\d+(?:[eE][+-]?\d+)?", reply)
        if nums:
            try:
                return float(nums[-1])
            except ValueError:
                pass
        return None
    # string: return first non-empty line, stripping common markdown decoration
    lines = [l.strip() for l in reply.splitlines() if l.strip()]
    if lines:
        s = lines[0].strip("'\"` *")
        return s
    return reply.strip()


def _score(item: dict, reply: str) -> bool:
    kind = item["answer_kind"]
    gt = item["ground_truth"]
    parsed = _parse_reply(reply, kind)
    if kind == "classification":
        expected = str(gt).lower().strip()
        return parsed == expected
    if kind == "numeric":
        if parsed is None:
            return False
        tol = item.get("tolerance", 0.0)
        if tol == 0.0:
            return abs(float(parsed) - float(gt)) < 1e-9
        # relative tolerance
        denom = abs(float(gt)) if float(gt) != 0 else 1.0
        return abs(float(parsed) - float(gt)) / denom <= tol
    if kind == "string":
        p = _norm_math(str(parsed).lower().strip())
        g = _norm_math(str(gt).lower().strip())
        if p == g:
            return True
        # Fallback: check every line of the reply for an exact-match line,
        # and for single-word/short GTs check if last non-empty line matches.
        all_lines = [_norm_math(l.strip("'\"` *").lower())
                     for l in reply.splitlines() if l.strip()]
        if any(l == g for l in all_lines):
            return True
        # Word-boundary fallback: "encodes **Met**" or "was a Saturday" → still matches "met"/"saturday"
        if len(g) >= 2:
            if re.search(r'\b' + re.escape(g) + r'\b', _norm_math(reply.lower())):
                return True
        # Underscore-join normalization: "total_internal_reflection" matches "total internal reflection"
        g_spaced = g.replace("_", " ")
        if g_spaced != g and len(g_spaced) >= 4:
            if re.search(r'\b' + re.escape(g_spaced) + r'\b', _norm_math(reply.lower())):
                return True
        # For long GTs (e.g. SHA-256 hash) check substring containment.
        if len(g) >= 16:
            return g in _norm_math(reply.lower())
        return False
    return False


# ── result types ─────────────────────────────────────────────────────────────

@dataclass
class ItemResult:
    id: str
    domain: str
    task: str
    correct: bool
    reply: str
    ground_truth: Any
    parsed: Any
    elapsed_s: float = 0.0
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BenchResult:
    label: str
    items: List[ItemResult] = field(default_factory=list)

    def summary(self) -> str:
        total = len(self.items)
        if total == 0:
            return f"{self.label}: no items"
        correct = sum(r.correct for r in self.items)
        elapsed = [r.elapsed_s for r in self.items if r.elapsed_s > 0]
        total_s = sum(elapsed)
        avg_s = total_s / len(elapsed) if elapsed else 0.0
        p95_s = sorted(elapsed)[int(len(elapsed) * 0.95)] if elapsed else 0.0
        lines = [f"\n{'='*60}",
                 f"  {self.label}",
                 f"  Total: {correct}/{total} = {correct/total:.1%}",
                 f"  Time:  {total_s:.1f}s total  |  {avg_s:.2f}s avg  |  {p95_s:.2f}s p95",
                 f"{'─'*60}"]
        # by domain with timing
        domains: Dict[str, list] = {}
        for r in self.items:
            domains.setdefault(r.domain, []).append(r)
        for d, rs in sorted(domains.items()):
            ok = sum(r.correct for r in rs)
            marker = "+" if ok == len(rs) else ("x" if ok == 0 else "~")
            d_elapsed = [r.elapsed_s for r in rs if r.elapsed_s > 0]
            d_avg = sum(d_elapsed) / len(d_elapsed) if d_elapsed else 0.0
            lines.append(f"  {marker} {d:30s}: {ok}/{len(rs)}  ({d_avg:.2f}s avg)")
        lines.append(f"{'='*60}")
        return "\n".join(lines)

    def diagnose(self) -> str:
        """Return detailed failure report: expected vs got, tool calls made."""
        failures = [r for r in self.items if not r.correct]
        if not failures:
            return "  All items correct."
        lines = [f"\n  FAILURES ({len(failures)}):", "─" * 60]
        for r in failures:
            lines.append(f"  {r.id} [{r.domain}]")
            lines.append(f"    expected : {r.ground_truth!r}")
            lines.append(f"    parsed   : {r.parsed!r}")
            lines.append(f"    reply    : {r.reply[:200]!r}")
            if r.tool_calls:
                for tc in r.tool_calls:
                    lines.append(f"    tool     : {tc['name']}({json.dumps(tc['args'])[:120]})")
                    lines.append(f"    result   : {json.dumps(tc.get('result', {}))[:120]}")
            else:
                lines.append(f"    tool     : (none called)")
            lines.append("")
        return "\n".join(lines)

    def to_jsonl(self, path: Path) -> None:
        with path.open("w") as f:
            for r in self.items:
                f.write(json.dumps({
                    "id": r.id, "domain": r.domain, "task": r.task,
                    "correct": r.correct,
                    "reply": r.reply[:400],
                    "ground_truth": r.ground_truth,
                    "parsed": r.parsed,
                    "elapsed_s": round(r.elapsed_s, 3),
                    "tool_calls": [
                        {"name": tc["name"], "args": tc["args"],
                         "result_summary": json.dumps(tc.get("result", {}))[:200]}
                        for tc in r.tool_calls
                    ],
                }) + "\n")


# ── tool schemas ─────────────────────────────────────────────────────────────

def _build_tool_schemas() -> List[Dict]:
    """Build minimal Anthropic tool schemas for all MCP tools."""
    from concordance_engine.mcp_server.tools import TOOLS
    schemas = []
    for t in TOOLS:
        schemas.append({
            "name": t["name"],
            "description": t.get("description", t["name"]),
            "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
        })
    return schemas


def _dispatch_tool(name: str, args: Dict[str, Any]) -> Any:
    from concordance_engine.mcp_server.tools import ALL_TOOLS
    fn = ALL_TOOLS.get(name)
    if fn is None:
        return {"error": f"unknown tool {name!r}"}
    try:
        return fn(**args)
    except TypeError:
        try:
            return fn(args)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


# ── completion functions ──────────────────────────────────────────────────────

SYSTEM = (
    "You are a precise scientific assistant. When asked a factual question, "
    "answer with only the requested format (a number, 'yes', 'no', or a short string). "
    "Do not add explanation unless the question asks for it."
)


def make_alone(client, model: str, max_tokens: int = 128):
    def fn(prompt: str) -> str:
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        return "".join(parts).strip()
    return fn


def make_with_tools(client, model: str, tool_schemas: List[Dict],
                    max_tokens: int = 1024, max_iters: int = 6):
    def fn(prompt: str) -> tuple[str, List[Dict]]:
        history = [{"role": "user", "content": prompt}]
        calls: List[Dict] = []
        for _ in range(max_iters):
            resp = client.messages.create(
                model=model, max_tokens=max_tokens, system=SYSTEM,
                messages=history, tools=tool_schemas,
            )
            history.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                parts = [b.text for b in resp.content
                         if getattr(b, "type", "") == "text"]
                return "".join(parts).strip(), calls
            results = []
            for block in resp.content:
                if getattr(block, "type", "") == "tool_use":
                    out = _dispatch_tool(block.name, block.input)
                    calls.append({"name": block.name, "args": dict(block.input), "result": out})
                    results.append({"type": "tool_result",
                                    "tool_use_id": block.id,
                                    "content": json.dumps(out)})
            if results:
                history.append({"role": "user", "content": results})
            else:
                break
        parts = []
        last = history[-1] if history else {}
        if isinstance(last.get("content"), list):
            parts = [b.text for b in last["content"]
                     if getattr(b, "type", "") == "text"]
        return "".join(parts).strip() or "[no text]", calls
    return fn


# ── runner ────────────────────────────────────────────────────────────────────

def run_benchmark(items: List[dict], completion_fn,
                  label: str, delay: float = 0.3,
                  with_tool_trace: bool = False) -> BenchResult:
    result = BenchResult(label=label)
    total = len(items)
    for i, item in enumerate(items, 1):
        prompt = item["prompt"]
        t0 = time.monotonic()
        tool_calls: List[Dict] = []
        try:
            raw = completion_fn(prompt)
            if isinstance(raw, tuple):
                reply, tool_calls = raw
            else:
                reply = raw
        except Exception as e:
            reply = f"[ERROR: {e}]"
        elapsed = time.monotonic() - t0
        correct = _score(item, reply)
        parsed = _parse_reply(reply, item["answer_kind"])
        result.items.append(ItemResult(
            id=item["id"], domain=item["domain"], task=item["task"],
            correct=correct, reply=reply,
            ground_truth=item["ground_truth"], parsed=parsed,
            elapsed_s=elapsed, tool_calls=tool_calls,
        ))
        marker = "+" if correct else "x"
        tools_info = f"  [{len(tool_calls)}t]" if with_tool_trace and tool_calls else ""
        print(f"  [{i:3d}/{total}] {marker} {item['id']:12s}  {elapsed:4.1f}s{tools_info}  {reply[:40]}")
        if delay > 0:
            time.sleep(delay)
    return result


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--alone-only", action="store_true")
    parser.add_argument("--tools-only", action="store_true")
    parser.add_argument("--diagnose", action="store_true",
                        help="print failure details after each run")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="seconds between API calls (default 0.2)")
    args = parser.parse_args()

    items_path = THIS.parent / "items_extended.jsonl"
    if not items_path.exists():
        print("Run build_items_extended.py first.", file=sys.stderr)
        sys.exit(1)

    items = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    print(f"Loaded {len(items)} items from {items_path.name}")

    from anthropic import Anthropic
    client = Anthropic()
    tool_schemas = _build_tool_schemas()

    out_dir = THIS.parent
    model_tag = args.model.replace("-", "_")

    results = []

    if not args.tools_only:
        print(f"\n{'='*60}")
        print(f"  ALONE — {args.model}")
        print(f"{'='*60}")
        alone_fn = make_alone(client, args.model)
        alone = run_benchmark(items, alone_fn, f"{args.model} (alone)",
                              delay=args.delay, with_tool_trace=False)
        alone.to_jsonl(out_dir / f"results_ext_{model_tag}_alone.jsonl")
        print(alone.summary())
        if args.diagnose:
            print(alone.diagnose())
        results.append(alone)

    if not args.alone_only:
        print(f"\n{'='*60}")
        print(f"  WITH TOOLS — {args.model}")
        print(f"{'='*60}")
        tools_fn = make_with_tools(client, args.model, tool_schemas)
        with_tools = run_benchmark(items, tools_fn,
                                   f"{args.model} (with tools)",
                                   delay=args.delay, with_tool_trace=True)
        with_tools.to_jsonl(out_dir / f"results_ext_{model_tag}_tools.jsonl")
        print(with_tools.summary())
        if args.diagnose:
            print(with_tools.diagnose())
        results.append(with_tools)

    # delta summary
    if len(results) == 2:
        alone, with_tools = results
        by_id_a = {r.id: r for r in alone.items}
        fixed = [r.id for r in with_tools.items
                 if r.correct and not by_id_a.get(r.id, r).correct]
        broken = [r.id for r in with_tools.items
                  if not r.correct and by_id_a.get(r.id, r).correct]
        print(f"\n  Items the engine fixed ({len(fixed)}):")
        for x in fixed:
            print(f"    + {x}")
        print(f"  Items the engine broke ({len(broken)}):")
        for x in broken:
            print(f"    - {x}")


if __name__ == "__main__":
    main()
