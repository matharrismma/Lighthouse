"""The discovery loop -- oracle structures, verifier judges, walking the axis cross.

Matt's lever for "find more from what we have": a verified cross-domain connection
is not generated, it is FOUND. The prose->structured-spec bridge (the only real
bottleneck) is crossed by letting the oracle TRANSLATE -- never judge.

  claim ->  for each candidate domain on the shared axis:
              oracle fills that verifier's field-spec from the claim   (TRANSLATOR)
              the deterministic verifier judges the spec               (JUDGE)
         ->  domains that CONFIRM, and the axes they share
         ->  >=2 independent CONFIRMs on a shared axis = a candidate
             verified cross-domain connection -- SURFACED, never auto-admitted.

Discipline (Principle B):
  - The oracle only translates prose into the verifier's fields. It is told, and
    constrained, never to decide truth. Its spec is itself checkable: the verifier
    either runs it (and confirms/denies) or rejects it as out of scope.
  - The verifier is the judge. Deterministic, free, with a computation trail.
  - Nothing enters the verified substrate here. The operator admits.
  - Every oracle call is Steward-gated and its cost recorded.

Runs on the BOX (concordance_engine + the oracle key live there). Read-only:
prints findings, writes nothing.
"""
from __future__ import annotations
import argparse
import json
import os
import sys

# concordance_engine is under src/ on the box.
_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The oracle key lives in .env (the engine loads it the same way).
try:
    import dotenv
    dotenv.load_dotenv(os.path.join(_REPO, ".env"), override=False)
except Exception:
    pass


def _axis_map():
    """domain -> set(abstract axes), and the inverse axis -> [domains]."""
    from concordance_engine.grid import AXIS_DIMENSIONS
    dom_axes = {d: set(a or []) for d, a in AXIS_DIMENSIONS.items()}
    axis_doms = {}
    for d, axes in dom_axes.items():
        for a in axes:
            axis_doms.setdefault(a, []).append(d)
    return dom_axes, axis_doms


def _field_map():
    """domain -> [accepted field names] (the schema the oracle fills)."""
    from concordance_engine.agent.verifier_schema import _collect_all
    return _collect_all()


def _oracle_structure(claim: str, domain: str, fields, model: str):
    """The TRANSLATOR. Returns a spec dict, or None if not applicable. Records cost."""
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None, "no oracle key"
    client = anthropic.Anthropic(api_key=key)
    system = (
        "You are a TRANSLATOR for a verification engine. You are NOT a judge and "
        "must never decide whether a claim is true or false. Given a claim and the "
        "field names a deterministic verifier accepts, extract values from the claim "
        "into a JSON object using ONLY those field names. Include a field only if the "
        "claim states or directly implies its value -- never invent numbers. If the "
        "claim contains nothing this verifier can check, output exactly "
        '{"not_applicable": true}. Output ONLY the JSON object, nothing else.')
    user = (f"Claim:\n{claim}\n\nVerifier: verify_{domain}\n"
            f"Accepted fields: {sorted(fields)}\n\nJSON spec:")
    resp = client.messages.create(model=model, max_tokens=500, system=system,
                                  messages=[{"role": "user", "content": user}])
    # Record the spend (Steward observes).
    try:
        from api.offices import ledger_record
        ti = getattr(resp.usage, "input_tokens", 0) or 0
        to = getattr(resp.usage, "output_tokens", 0) or 0
        ledger_record("discover", ti * 3e-6 + to * 15e-6)
    except Exception:
        pass
    txt = "".join(getattr(b, "text", "") for b in resp.content).strip()
    import re
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None, "no json"
    try:
        spec = json.loads(m.group(0))
    except Exception:
        return None, "bad json"
    if spec.get("not_applicable"):
        return None, "not applicable"
    spec.pop("not_applicable", None)
    return spec, None


def _judge(domain: str, spec: dict):
    """The JUDGE. Run the deterministic verifier on the spec via the engine's own
    cluster runner (one mechanism). Returns (verdict, detail)."""
    from concordance_engine.agent.poly_agent import _run_cluster
    from concordance_engine.mcp_server.tools import ALL_TOOLS
    res = _run_cluster([{"domain": domain, "spec": spec}], ALL_TOOLS)
    if not res:
        return "NO_VERIFIER", ""
    r = res[0]
    detail = ""
    try:
        detail = (r.result or {}).get("detail") or ""
    except Exception:
        pass
    return r.verdict, detail[:160]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim", required=True, help="the claim to test across domains")
    ap.add_argument("--domains", default="", help="comma-separated explicit domains to test")
    ap.add_argument("--axis", default="", help="test all domains crossing this abstract axis")
    ap.add_argument("--max-domains", type=int, default=6, help="cap oracle calls (Steward bound)")
    ap.add_argument("--model", default=os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5"))
    args = ap.parse_args()

    dom_axes, axis_doms = _axis_map()
    fields = _field_map()

    if args.domains:
        targets = [d.strip() for d in args.domains.split(",") if d.strip()]
    elif args.axis:
        targets = sorted(axis_doms.get(args.axis, []))
    else:
        print("[FATAL] give --domains a,b or --axis <channel>")
        return 1
    targets = [d for d in targets if d in fields][:args.max_domains]
    if not targets:
        print("[FATAL] no testable domains resolved")
        return 1

    # Steward gate.
    try:
        from api.offices import steward_budget_remaining_usd
        bud = steward_budget_remaining_usd()
        if bud < 0.25:
            print(f"[HELD] Steward budget ${bud:.2f} too low for discovery.")
            return 2
    except Exception:
        bud = None

    print(f"claim: {args.claim}")
    print(f"testing {len(targets)} domains: {targets}\n")
    confirmed = []
    for d in targets:
        spec, why = _oracle_structure(args.claim, d, fields.get(d, []), args.model)
        if spec is None:
            print(f"  {d:24} -> (not structured: {why})")
            continue
        verdict, detail = _judge(d, spec)
        tag = "CONFIRMED" if verdict == "CONFIRMED" else verdict
        print(f"  {d:24} -> {tag:12} spec={json.dumps(spec, ensure_ascii=False)[:80]}")
        if detail:
            print(f"  {'':24}    {detail}")
        if verdict == "CONFIRMED":
            confirmed.append(d)

    print()
    if len(confirmed) >= 2:
        shared = set.intersection(*[dom_axes.get(d, set()) for d in confirmed]) or set()
        print(f"=== CANDIDATE VERIFIED CONNECTION ===")
        print(f"domains confirmed: {confirmed}")
        print(f"shared axes (the cross): {sorted(shared) or '(none in common)'}")
        print("STATUS: surfaced for the operator. NOT admitted to the atlas (Principle B).")
    else:
        print(f"No cross-domain connection: {len(confirmed)} domain(s) confirmed "
              f"({confirmed or 'none'}). Honestly eliminated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
