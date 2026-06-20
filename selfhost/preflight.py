#!/usr/bin/env python3
"""selfhost/preflight.py — prove the engine stands on its own.

Run this ANYWHERE (a laptop, a Node, an air-gapped box) to confirm the
deterministic core owes no external provider, then report what is sovereign and
what is optional. It makes ZERO network calls for the core checks; the only
network touch is an OPTIONAL probe of a local model endpoint (Ollama) for
sovereign generation. Exit 0 iff the sovereign core is operational.

  python selfhost/preflight.py            # full report
  python selfhost/preflight.py --quiet    # just the verdict line
"""
from __future__ import annotations
import importlib
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

OK, BAD = "✓", "✗"
results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> bool:
    results.append((ok, msg))
    return ok


def main() -> int:
    quiet = "--quiet" in sys.argv

    # 1) Python
    check(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (need >=3.10)")

    # 2) Core deps — the WHOLE deterministic engine. All offline, pip-installable.
    for mod in ("sympy", "numpy", "scipy", "cryptography"):
        try:
            importlib.import_module(mod)
            check(True, f"core dep: {mod}")
        except Exception as e:
            check(False, f"core dep MISSING: {mod} ({e})")

    # 3) The proof: a deterministic verification with NO network, NO cloud key.
    core_ok = False
    try:
        import api.derivation as D
        def eqspec(a, b):
            return {"mode": "equality", "params": {"expr_a": a, "expr_b": b, "variables": {}}}
        holds = D.verify_derivation([{"id": "s", "domain": "mathematics", "spec": eqspec("2**10", "1024")}])
        broken = D.verify_derivation([{"id": "s", "domain": "mathematics", "spec": eqspec("2+2", "5")}])
        core_ok = (holds.get("verdict") == "HOLDS" and broken.get("verdict") == "BROKEN")
        check(core_ok, "deterministic verify offline: 2^10=1024 HOLDS, 2+2=5 BROKEN "
                       "(the engine confirms truth AND catches falsehood, no provider)")
    except Exception as e:
        check(False, f"deterministic verify FAILED: {e}")

    # 4) The seal (signing) — own keys, no provider.
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        k = Ed25519PrivateKey.generate()
        sig = k.sign(b"narrow highway")
        k.public_key().verify(sig, b"narrow highway")
        check(True, "seal/signature offline (Ed25519, own keys)")
    except Exception as e:
        check(False, f"seal FAILED: {e}")

    # 5) No cloud key required for the core (informational — never a hard fail).
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    check(True, f"cloud key present: {'yes' if has_anthropic else 'no'} "
                f"(NOT required — the deterministic core needs none)")

    # 6) OPTIONAL: local model endpoint for sovereign GENERATION (Ollama).
    base = os.environ.get("NH_OPENAI_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    tags = base.replace("/v1", "") + "/api/tags"
    local_gen = False
    try:
        with urllib.request.urlopen(tags, timeout=3) as r:  # noqa: S310 (local only)
            local_gen = r.status == 200
    except Exception:
        local_gen = False
    check(True, f"local generation endpoint ({base}): "
                f"{'reachable — sovereign generation available' if local_gen else 'not reachable (optional; the core is sovereign without it)'}")

    # ── Report ──
    core_pass = core_ok and all(ok for ok, m in results if "core dep" in m)
    if not quiet:
        print("\nNarrow Highway — sovereignty preflight\n" + "-" * 44)
        for ok, m in results:
            print(f"  {OK if ok else BAD} {m}")
        print("-" * 44)
    verdict = ("SOVEREIGN CORE OPERATIONAL — the engine stands on its own "
               "(deterministic verification + seal, zero external providers)."
               if core_pass else
               "CORE NOT OPERATIONAL — install core deps: pip install sympy numpy scipy cryptography")
    print(verdict)
    print("  generation:", "sovereign local available" if local_gen else
          "cloud or local-model needed for the assistant voice (the receipt/verify core does not need it)")
    return 0 if core_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
