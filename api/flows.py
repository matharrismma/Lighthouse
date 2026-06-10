"""Flow primitive — first-class composition over the engine's tools.

A flow is a named, registered sequence of tool calls + branches + state.
The engine has plenty of tools; flows give those tools sequence and
substrate-shape so a human or an agent can run a journey end-to-end
without guessing what to call next.

Three audiences:
  - Humans see flows via the "What next?" cards on each result page.
  - Agents see flows via /flows (list) + /flow/run (execute).
  - Operators see flow runs in the Steward audit (action=flow_step:...).

Flow definition (declarative JSONL at data/flows/*.jsonl):

{
  "id": "walk_to_keep",
  "name": "Walk a hard decision, write what you learned",
  "description": "Carry a situation through the four gates, then write a
                  reflection the keeping decides on.",
  "audience": ["human", "agent"],
  "starts_from": "any",            // or "walk", "apothecary", etc — for
                                   //   UI affordance: where this flow
                                   //   is offered as "What next?"
  "first_input": {                 // initial state required to start
    "key": "situation",
    "label": "What are you carrying?",
    "kind": "text"
  },
  "steps": [
    {
      "id": "start_walk",
      "kind": "tool",              // tool | input | branch | output
      "tool": "walk_start",        // matches an engine endpoint or MCP tool
      "method": "POST",
      "path": "/coach/journal/start",
      "inputs": {"situation": "{situation}", "visitor_id": "{visitor_id}"},
      "binds": "walk_id"           // result -> state.walk_id
    },
    {
      "id": "reflect",
      "kind": "input",
      "label": "What did you learn?",
      "binds": "reflection"
    },
    {
      "id": "submit",
      "kind": "tool",
      "tool": "scribe_submit",
      "method": "POST",
      "path": "/scribe/intake",
      "inputs": {
        "text": "{reflection}",
        "title": "Walk: {situation}",
        "visitor_id": "{visitor_id}"
      },
      "binds": "writing_id"
    }
  ],
  "outputs": ["walk_id", "writing_id"]
}

The runner is paused-by-default: when it hits an `input` step, it returns
{state: 'waiting', expects: <step.id>} and the caller resumes with the
visitor's answer.

Standing test: every flow step is an admissible engine action. Steward
gates every tool call. The keeping is the substrate; flows are how it's
walked.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_FLOW_DIR = _REPO / "data" / "flows"
_RUNS_DIR = _REPO / "data" / "flow_runs"
_LOCAL_API = "http://127.0.0.1:8000"

_lock = Lock()


# ── Flow definition shape ─────────────────────────────────────

@dataclass(frozen=True)
class Flow:
    id: str
    name: str
    description: str
    audience: List[str]
    starts_from: str
    first_input: Dict[str, Any]
    steps: List[Dict[str, Any]]
    outputs: List[str] = field(default_factory=list)


def _load_flows() -> Dict[str, Flow]:
    """Walk data/flows/*.jsonl and load every flow definition.

    Defensive: malformed records skip; never raises. Re-read on each
    listing call so file edits show up without restart."""
    out: Dict[str, Flow] = {}
    if not _FLOW_DIR.exists():
        return out
    for p in sorted(_FLOW_DIR.glob("*.jsonl")):
        try:
            for line in p.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fid = r.get("id")
                if not fid:
                    continue
                out[fid] = Flow(
                    id=fid,
                    name=r.get("name", fid),
                    description=r.get("description", ""),
                    audience=list(r.get("audience") or ["human", "agent"]),
                    starts_from=r.get("starts_from", "any"),
                    first_input=dict(r.get("first_input") or {}),
                    steps=list(r.get("steps") or []),
                    outputs=list(r.get("outputs") or []),
                )
        except OSError:
            continue
    return out


def list_flows(audience: Optional[str] = None,
               starts_from: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all known flows; optionally filter by audience or
    starts-from (used by the UI to show 'What next?' cards relevant to
    the current page)."""
    flows = _load_flows()
    out = []
    for f in flows.values():
        if audience and audience not in f.audience:
            continue
        if starts_from and starts_from not in (f.starts_from, "any"):
            continue
        out.append({
            "id": f.id,
            "name": f.name,
            "description": f.description,
            "audience": f.audience,
            "starts_from": f.starts_from,
            "first_input": f.first_input,
            "step_count": len(f.steps),
            "outputs": f.outputs,
        })
    out.sort(key=lambda r: r["id"])
    return out


def get_flow(flow_id: str) -> Optional[Flow]:
    return _load_flows().get(flow_id)


# ── State + template substitution ─────────────────────────────

_TEMPLATE_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_.]*)\}")


def _substitute(value: Any, state: Dict[str, Any]) -> Any:
    """Resolve {placeholders} in flow inputs from the run state.
    Recursive for dicts/lists. Unknown placeholders pass through as-is
    so the engine endpoint can defend."""
    if isinstance(value, str):
        def replace(m):
            key = m.group(1)
            v = state
            for part in key.split("."):
                if isinstance(v, dict):
                    v = v.get(part, "")
                else:
                    return m.group(0)
            return str(v) if v is not None else ""
        return _TEMPLATE_RE.sub(replace, value)
    if isinstance(value, dict):
        return {k: _substitute(v, state) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute(v, state) for v in value]
    return value


# ── Flow runner ───────────────────────────────────────────────

def _engine_call(method: str, path: str, body: Optional[Dict[str, Any]] = None,
                 params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Call an engine endpoint. Defensive."""
    url = _LOCAL_API + path
    if params:
        q = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        if q:
            url = f"{url}?{q}"
    try:
        if method.upper() == "GET":
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
        else:
            data = json.dumps(body or {}).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                method=method.upper(),
            )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "url": url}


def _append_run_step(run_id: str, step_record: Dict[str, Any]) -> None:
    """Append-only run log at data/flow_runs/<run_id>.jsonl."""
    try:
        _RUNS_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c for c in run_id if c.isalnum() or c in "_-")[:64]
        p = _RUNS_DIR / f"{safe}.jsonl"
        with _lock:
            with p.open("a", encoding="utf-8") as f:
                f.write(json.dumps(step_record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run_step(flow: Flow, state: Dict[str, Any], step_index: int,
             run_id: str) -> Dict[str, Any]:
    """Execute one step of a flow. Returns the next state + a hint
    about what to do next:

      {
        "status": "running" | "waiting_for_input" | "complete" | "error",
        "state": <updated>,
        "next_step_index": <int>,
        "expects": <step.id> | null,    // when waiting_for_input
        "trace": [<step records...>],
      }
    """
    if step_index >= len(flow.steps):
        return {"status": "complete", "state": state, "next_step_index": step_index}
    step = flow.steps[step_index]
    kind = step.get("kind", "tool")
    step_id = step.get("id", f"step_{step_index}")

    if kind == "input":
        # Pause; caller resumes by supplying state[step['binds']]
        bind_key = step.get("binds") or step_id
        if state.get(bind_key) is None or state.get(bind_key) == "":
            _append_run_step(run_id, {
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "step_id": step_id,
                "kind": "input",
                "status": "waiting",
                "expects": bind_key,
            })
            return {
                "status": "waiting_for_input",
                "state": state,
                "next_step_index": step_index,
                "expects": bind_key,
                "label": step.get("label", ""),
            }
        # Input already provided — advance
        _append_run_step(run_id, {
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "step_id": step_id,
            "kind": "input",
            "status": "received",
            "key": bind_key,
        })
        return {"status": "running", "state": state, "next_step_index": step_index + 1}

    if kind == "tool":
        method = step.get("method", "GET").upper()
        path = step.get("path", "")
        inputs = _substitute(step.get("inputs") or {}, state)
        if not path:
            return {"status": "error", "state": state, "error": f"step {step_id!r} missing path"}
        if method == "GET":
            result = _engine_call("GET", path, params=inputs)
        else:
            result = _engine_call(method, path, body=inputs)
        # Bind result to state under step["binds"] if specified
        bind_key = step.get("binds")
        if bind_key:
            state[bind_key] = result
        _append_run_step(run_id, {
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "step_id": step_id,
            "kind": "tool",
            "method": method,
            "path": path,
            "result_keys": list(result.keys()) if isinstance(result, dict) else None,
            "error": result.get("error") if isinstance(result, dict) else None,
        })
        return {"status": "running", "state": state, "next_step_index": step_index + 1}

    if kind == "branch":
        cond_key = step.get("if", "")
        # Simple truthy check on state[cond_key] or substituted expression
        truthy = bool(state.get(cond_key)) if cond_key in state else bool(_substitute(cond_key, state))
        target = step.get("then") if truthy else step.get("else")
        # Find target step index by id
        next_idx = step_index + 1
        if target:
            for i, s in enumerate(flow.steps):
                if s.get("id") == target:
                    next_idx = i
                    break
        _append_run_step(run_id, {
            "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "step_id": step_id,
            "kind": "branch",
            "took": "then" if truthy else "else",
            "target": target,
        })
        return {"status": "running", "state": state, "next_step_index": next_idx}

    if kind == "output":
        # Terminal step — collect declared outputs from state
        return {
            "status": "complete",
            "state": state,
            "next_step_index": step_index + 1,
            "outputs": {k: state.get(k) for k in flow.outputs},
        }

    # Unknown kind — treat as no-op
    return {"status": "running", "state": state, "next_step_index": step_index + 1}


def run_flow(flow_id: str, initial_state: Optional[Dict[str, Any]] = None,
             run_id: Optional[str] = None, max_steps: int = 50) -> Dict[str, Any]:
    """Execute a flow from step 0 (or resume from a paused state).

    For paused flows, the caller passes:
      initial_state.{step.binds}  = the user's input
      initial_state._step_index   = resume point

    Returns the final state + trace + status."""
    flow = get_flow(flow_id)
    if not flow:
        return {"status": "error", "error": f"flow {flow_id!r} not found"}
    state = dict(initial_state or {})
    if not run_id:
        run_id = f"run_{int(time.time())}_{flow_id}"
    state["_run_id"] = run_id
    state["_flow_id"] = flow_id
    step_index = int(state.pop("_step_index", 0) or 0)
    for _ in range(max_steps):
        if step_index >= len(flow.steps):
            _append_run_step(run_id, {
                "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "kind": "complete",
                "outputs": {k: state.get(k) for k in flow.outputs},
            })
            return {
                "status": "complete",
                "state": state,
                "run_id": run_id,
                "outputs": {k: state.get(k) for k in flow.outputs},
            }
        result = run_step(flow, state, step_index, run_id)
        state = result.get("state", state)
        if result.get("status") == "waiting_for_input":
            state["_step_index"] = result["next_step_index"]
            return {
                "status": "waiting_for_input",
                "state": state,
                "run_id": run_id,
                "expects": result.get("expects"),
                "label": result.get("label", ""),
            }
        if result.get("status") == "error":
            return {
                "status": "error",
                "state": state,
                "run_id": run_id,
                "error": result.get("error"),
            }
        step_index = result.get("next_step_index", step_index + 1)
    return {
        "status": "error",
        "state": state,
        "run_id": run_id,
        "error": f"flow exceeded max_steps={max_steps}",
    }
