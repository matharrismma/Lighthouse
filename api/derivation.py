"""
Multi-step verification — the derivation chain (Task B keystone, Fable 2026-06-10).

A single verifier confirms ONE claim. A DERIVATION is an ordered chain of claims
where each step's verifier must confirm AND each step may build only on prior
steps that themselves confirmed. This runner verifies every step deterministically
(via the existing verifier dispatch) and checks the links, producing ONE checkable
trail with a composite verdict.

The engine never generates the answer — it verifies a PROVIDED derivation and
reports EXACTLY where it breaks (the elimination trail; the trail is the trust —
project_mapping_reality_2026-06-10). This is what makes "solve a real calculus/
physics problem, every step verified" real (project_moat_track_2026-06-10): the
free 64-verifier stack confirms each structured step; the chain ties them into a
proof.

THE BRIDGE: a step's `spec` is the exact kwargs its verifier wants (the structured
form). Supplying structured steps directly is the faithful, oracle-free path
(this module). An oracle-assisted prose->steps translator can ride on top later
(oracle STRUCTURES, this runner JUDGES — runs on prod), per
project_academia_connection_atlas_2026-06-09.

A step:
  {
    "id": "s1",                 # unique within the derivation (default: s<index>)
    "domain": "mathematics",    # -> verify_<domain>
    "spec": {...},              # the structured claim (kwargs for that verifier)
    "uses": ["s0"],             # ids of prior steps this builds on (optional)
    "claim": "f'(x) = 2x"       # human-readable, for the trail (optional)
  }

Composite verdict:
  HOLDS      — every step CONFIRMED and every `uses` -> a CONFIRMED prior step.
  BROKEN     — a step MISMATCH/ERROR, or `uses` -> a missing/unconfirmed step;
               `broken_at` = the first such step (the trail stops being trustworthy there).
  INCOMPLETE — a step's verifier returned NOT_APPLICABLE (couldn't run: the spec
               wasn't structured enough — the prose->spec bridge gap); `gap_at`.
"""
from __future__ import annotations

from typing import Any, Dict, List

_TERMINAL_FAIL = ("MISMATCH", "ERROR")


def _collect_statuses(res: Any, acc: List) -> None:
    """Walk a verifier result of any shape and append (status, detail) pairs.

    Handles: a VerifierResult dataclass, a dict with a "status", a dict nesting
    a list under checks/results/verifications, and lists of any of these."""
    if res is None:
        return
    if isinstance(res, list):
        for r in res:
            _collect_statuses(r, acc)
        return
    status = getattr(res, "status", None)
    if status is not None and not isinstance(res, dict):
        acc.append((str(status), str(getattr(res, "detail", "") or "")))
        return
    if isinstance(res, dict):
        if "status" in res:
            acc.append((str(res["status"]), str(res.get("detail", "") or "")))
            return
        for key in ("checks", "results", "verifications", "domain_results"):
            sub = res.get(key)
            if isinstance(sub, list):
                _collect_statuses(sub, acc)
                return


def verify_step(domain: str, spec: Dict[str, Any]) -> Dict[str, str]:
    """Run one step's verifier and reduce its (possibly multi-part) result to a
    single status. A step CONFIRMS iff at least one applicable invariant confirmed
    and none contradicted; it FAILS on any applicable MISMATCH/ERROR; it is
    NOT_APPLICABLE if the verifier could not run (spec too thin)."""
    from api import agent_manifest as _am  # local import: avoid import cycles
    domain = (domain or "").strip()
    if not domain:
        return {"status": "ERROR", "detail": "step missing 'domain'"}
    out = _am.dispatch(f"verify_{domain}", spec or {})
    if not out.get("ok"):
        return {"status": "ERROR", "detail": str(out.get("error", "dispatch failed"))[:300]}
    acc: List = []
    _collect_statuses(out.get("result"), acc)
    if not acc:
        return {"status": "ERROR", "detail": "verifier returned no status"}
    applicable = [(s, d) for s, d in acc if s != "NOT_APPLICABLE"]
    fails = [(s, d) for s, d in applicable if s in _TERMINAL_FAIL]
    if fails:
        s, d = fails[0]
        return {"status": s, "detail": d[:300]}
    if not applicable:
        return {"status": "NOT_APPLICABLE", "detail": acc[0][1][:300]}
    confs = [d for s, d in applicable if s == "CONFIRMED"]
    return {"status": "CONFIRMED", "detail": (confs[0] if confs else "")[:300]}


def verify_derivation(steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify an ordered derivation. Every step is checked (the full trail is
    returned), but the COMPOSITE verdict is governed by the FIRST step that
    breaks — that is where the derivation stops being trustworthy."""
    if not isinstance(steps, list) or not steps:
        return {"verdict": "ERROR", "detail": "no steps provided", "trail": []}

    trail: List[Dict[str, Any]] = []
    seen_ids: set = set()
    confirmed_ids: set = set()
    verdict = "HOLDS"
    broken_at = None
    gap_at = None

    for i, step in enumerate(steps):
        sid = str(step.get("id") or f"s{i}")
        domain = str(step.get("domain", ""))
        spec = step.get("spec") or {}
        uses = [str(u) for u in (step.get("uses") or [])]

        # Link integrity: a step may build only on prior steps that CONFIRMED.
        missing = [u for u in uses if u not in seen_ids]
        unconfirmed = [u for u in uses if u in seen_ids and u not in confirmed_ids]
        link_ok = not missing and not unconfirmed

        sr = verify_step(domain, spec)
        st = sr["status"]

        entry: Dict[str, Any] = {
            "id": sid, "domain": domain, "claim": str(step.get("claim", "")),
            "uses": uses, "status": st, "detail": sr.get("detail", ""),
            "link_ok": link_ok,
        }
        if missing:
            entry["missing_refs"] = missing
        if unconfirmed:
            entry["builds_on_unconfirmed"] = unconfirmed
        trail.append(entry)
        seen_ids.add(sid)

        if st == "CONFIRMED" and link_ok:
            confirmed_ids.add(sid)
        elif verdict == "HOLDS":
            # first break governs the composite
            if st == "NOT_APPLICABLE":
                verdict, gap_at = "INCOMPLETE", sid
            else:  # MISMATCH / ERROR / broken link
                verdict, broken_at = "BROKEN", sid

    return {
        "verdict": verdict,
        "steps": len(steps),
        "confirmed_steps": len(confirmed_ids),
        "broken_at": broken_at,
        "gap_at": gap_at,
        "trail": trail,
        "note": ("The trail is the trust: each step is machine-verified and may "
                 "build only on confirmed prior steps. The engine verifies a "
                 "provided derivation; it does not generate the answer."),
    }
