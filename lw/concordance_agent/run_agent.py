"""
Concordance Agent CLI — route a natural-language claim to the engine.

Usage:
    python run_agent.py "The SHA-256 hash of 'hello' is 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    python run_agent.py --demo
    echo "2 + 2 = 5" | python run_agent.py -

Environment:
    ANTHROPIC_API_KEY  — required
    CONCORDANCE_MODEL  — optional (default: claude-haiku-4-5-20251001)
"""
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

repo = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo / "src"))
sys.path.insert(0, str(repo))

# Load .env
_env = repo / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if v:
                os.environ[k] = v

from concordance_engine.agent import verify_claim, adjacent_domains, DOMAIN_AXES, dispatch
from concordance_engine.agent.rule_extractor import extract_proposals, load_training_examples

MODEL = os.environ.get("CONCORDANCE_MODEL", "claude-haiku-4-5-20251001")

# ---------------------------------------------------------------------------
# Demo claims — one per axis to show cross-domain connections
# ---------------------------------------------------------------------------
DEMO_CLAIMS = [
    # mathematics
    "The integral of x^2 with respect to x is x^3/3 + C.",
    # cryptography + information_theory (cross-axis)
    "The SHA-256 hash of 'hello' is 2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824.",
    # physics_conservation + energy (conservation_balance axis)
    "A system starts with 1000 J of kinetic energy and 500 J of potential energy. After the event it has 900 J kinetic and 600 J potential energy.",
    # chemistry + mathematics
    "The equation H2 + O2 -> H2O is balanced.",
    # medicine + nutrition (life_system axis)
    "A person weighing 70 kg and 1.75 m tall has a BMI of 22.86.",
    # economics + labor (conservation_balance axis) — FLSA overtime: 40 regular + 5 OT at 1.5x = $878.75
    "An employee earning $18.50/hour who works 45 hours (40 regular + 5 overtime) should receive $878.75 under FLSA overtime rules.",
    # genetics + information_theory
    "The DNA sequence ATCG has a complement of TAGC.",
    # formal_logic (time_sequence + measurement axis) — use claimed_satisfiable boolean
    "The propositional formula (A >> B) & A is satisfiable.",
]


def _print_result(r: dict) -> None:
    verdict = r.get("verdict", "?")
    domains = r.get("domains", [])
    axes = r.get("axes", [])
    cross = r.get("cross_domain", False)
    lat = r.get("latency_ms", 0)

    verdict_marker = {"CONFIRMED": "[OK]", "MISMATCH": "[!!]", "NOT_APPLICABLE": "[--]",
                      "ERROR": "[ERR]", "NO_TOOL_CALLED": "[??]"}.get(verdict, f"[{verdict}]")

    print(f"\n{verdict_marker} {verdict}")
    print(f"  Domains : {', '.join(domains) if domains else '(none)'}")
    if axes:
        print(f"  Axes    : {', '.join(axes)}")
    if cross:
        print(f"  >>> Cross-domain convergence across {len(set(domains))} domains")
    print(f"  Latency : {lat:.0f} ms")

    relay = r.get("relay_text", "")
    if relay:
        print()
        for line in relay.splitlines():
            print(f"  {line}")

    if r.get("error"):
        print(f"  Error   : {r['error']}")


def main() -> None:
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return

    if args[0] == "--demo":
        training_dir = repo / "data" / "agent_training"
        print(f"Running {len(DEMO_CLAIMS)} demo claims against {MODEL}...\n")
        for i, claim in enumerate(DEMO_CLAIMS, 1):
            print(f"[{i}/{len(DEMO_CLAIMS)}] {claim[:80]}{'...' if len(claim) > 80 else ''}")
            r = verify_claim(claim, model=MODEL, training_dir=training_dir)
            _print_result(r)
            print()
        print(f"Training data written to: {training_dir}")
        return

    if args[0] == "--extract":
        training_dir = repo / "data" / "agent_training"
        min_ex = int(args[1]) if len(args) > 1 else 1
        by_domain = load_training_examples(training_dir)
        total = sum(len(v) for v in by_domain.items())
        print(f"Training store: {training_dir}")
        print(f"Domains with oracle data: {list(by_domain.keys())}\n")
        proposals = extract_proposals(training_dir, min_examples=min_ex)
        if not proposals:
            print(f"No proposals (need >= {min_ex} confirmed example(s) per domain).")
            print("Run --demo first, or pass a lower threshold: --extract 1")
        else:
            for p in proposals:
                print(f"[{p.domain}]  conf={p.confidence:.0%}  support={p.support}")
                print(f"  pattern   : {p.pattern}")
                print(f"  spec_keys : {p.spec_keys}")
                print(f"  note      : {p.note}")
                print()
        return

    if args[0] == "--axes":
        print("Domain axis grid:\n")
        for axis, doms in DOMAIN_AXES.items():
            print(f"  {axis:<25} {', '.join(doms)}")
        return

    if args[0] == "--adjacent" and len(args) > 1:
        domain = args[1]
        adj = adjacent_domains(domain)
        print(f"Domains adjacent to '{domain}': {', '.join(adj) if adj else '(none)'}")
        return

    # Claim from arg or stdin
    if args[0] == "-":
        claim = sys.stdin.read().strip()
    else:
        claim = " ".join(args)

    if not claim:
        print("Error: no claim provided.", file=sys.stderr)
        sys.exit(1)

    training_dir = repo / "data" / "agent_training"
    print(f"Claim: {claim}")
    r = verify_claim(claim, model=MODEL, training_dir=training_dir)
    _print_result(r)

    if "--json" in sys.argv:
        safe = {k: v for k, v in r.items() if k != "tool_calls"}
        print("\n--- JSON ---")
        print(json.dumps(safe, indent=2))


if __name__ == "__main__":
    main()
