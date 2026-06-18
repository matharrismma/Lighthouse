#!/usr/bin/env python3
"""The Fabrication Gauntlet — run a set of plausible-but-false (and true-control)
claims through the engine, deterministically, and seal every verdict.

Each claim is the kind of thing an LLM will confidently assert. The engine does
not guess: it checks the math/chemistry/constant underneath and returns a verdict
(BROKEN for a fake, HOLDS for a truth) with the worked trail and a permanent,
re-checkable seal (cite_url -> GET /seal/{hash}). A BROKEN refutation is as
citable as a HOLDS confirmation.

Writes data/gauntlet/results.json — the public page reads it. Reproducible:
re-run any claim by POSTing its `spec` to /derivation/verify yourself.

  PYTHONPATH=src .venv/bin/python tools/fabrication_gauntlet.py            # engine only
  PYTHONPATH=src .venv/bin/python tools/fabrication_gauntlet.py --llm      # + ask the base model

The --llm pass asks the configured base model, plainly, "true or false?" for each
claim and records its answer — an honest, labeled head-to-head (NOT a claim about
any specific competitor; it tests whatever NH_BASE_MODEL is set to).
"""
from __future__ import annotations
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

BASE = os.environ.get("CONCORDANCE_API_URL", "http://127.0.0.1:8000").rstrip("/")
OUT = Path(__file__).resolve().parent.parent / "data" / "gauntlet" / "results.json"


def _eq(a, b, variables=None):
    return {"mode": "equality", "params": {"expr_a": a, "expr_b": b, "variables": variables or []}}


# statement = how a person/LLM would phrase it · false = is the STATEMENT false ·
# domain/spec = how the engine checks the math underneath · corrected = the truth.
SEED = [
    {"id": "tip_percent", "statement": "15% of $84.50 is $11.68.", "false": True,
     "category": "everyday math", "why": "LLMs approximate percentages and drop cents.",
     "domain": "mathematics", "spec": _eq("0.15*84.50", "11.68"),
     "corrected": "15% of $84.50 is $12.675."},
    {"id": "pow_2_10", "statement": "2 to the 10th power equals 1,000.", "false": True,
     "category": "arithmetic", "why": "2^10 is 'about a thousand' — LLMs round it to 1000.",
     "domain": "mathematics", "spec": _eq("2**10", "1000"), "corrected": "2^10 = 1024."},
    {"id": "binom_square", "statement": "(x + 3)squared equals x squared + 6x + 6.", "false": True,
     "category": "algebra", "why": "The constant term should be 9 (3 squared), not 6.",
     "domain": "mathematics", "spec": _eq("(x+3)**2", "x**2+6*x+6", ["x"]),
     "corrected": "(x+3)^2 = x^2 + 6x + 9."},
    {"id": "freshman_square", "statement": "(a + b) squared equals a squared plus b squared.",
     "false": True, "category": "algebra", "why": "The classic dropped cross-term 2ab.",
     "domain": "mathematics", "spec": _eq("(a+b)**2", "a**2+b**2", ["a", "b"]),
     "corrected": "(a+b)^2 = a^2 + 2ab + b^2."},
    {"id": "body_temp", "statement": "A normal body temperature of 37 degrees C is 99.6 degrees F.",
     "false": True, "category": "unit conversion", "why": "37C is 98.6F; 99.6 is a one-digit slip.",
     "domain": "mathematics", "spec": _eq("37*9/5+32", "99.6"),
     "corrected": "37 degrees C = 98.6 degrees F."},
    {"id": "right_triangle", "statement": "A triangle with sides 3, 4, and 6 is a right triangle.",
     "false": True, "category": "geometry", "why": "3^2 + 4^2 = 25, not 36 — it is not right.",
     "domain": "mathematics", "spec": _eq("3**2+4**2", "6**2"),
     "corrected": "3-4-5 is the right triangle; 3-4-6 is not."},
    {"id": "chem_water", "statement": "The reaction H2 + O2 -> H2O is balanced.", "false": True,
     "category": "chemistry", "why": "Atoms do not balance; it needs 2 H2 + O2 -> 2 H2O.",
     "domain": "chemistry", "spec": {"equation": "H2 + O2 -> H2O"},
     "corrected": "2 H2 + O2 -> 2 H2O is balanced."},
    {"id": "light_speed", "statement": "The speed of light is exactly 300,000 km/s.", "false": True,
     "category": "physics", "why": "It is 299,792.458 km/s; 300,000 is the rounded figure.",
     "domain": "physical_constants",
     "spec": {"constant": "speed_of_light", "claimed_value": 300000, "claimed_unit": "km/s"},
     "corrected": "c = 299,792.458 km/s (299,792,458 m/s)."},
    # ---- TRUE controls: prove the engine confirms truth, it is not a rejection machine ----
    {"id": "tip_true", "statement": "20% of 250 is 50.", "false": False,
     "category": "everyday math", "why": "A true control.",
     "domain": "mathematics", "spec": _eq("0.20*250", "50")},
    {"id": "boiling_true", "statement": "100 degrees C equals 212 degrees F.", "false": False,
     "category": "unit conversion", "why": "A true control.",
     "domain": "mathematics", "spec": _eq("100*9/5+32", "212")},
    {"id": "chem_true", "statement": "The reaction 2 H2 + O2 -> 2 H2O is balanced.", "false": False,
     "category": "chemistry", "why": "A true control.",
     "domain": "chemistry", "spec": {"equation": "2 H2 + O2 -> 2 H2O"}},
    {"id": "fraction_true", "statement": "One third plus one sixth equals one half.", "false": False,
     "category": "arithmetic", "why": "A true control.",
     "domain": "mathematics", "spec": _eq("1/3+1/6", "1/2")},
    # ---- test-and-see (kept only if the verifier returns a clean verdict) ----
    {"id": "nt_91_prime", "statement": "91 is a prime number.", "false": True,
     "category": "number theory", "why": "91 = 7 x 13, so it is composite, not prime.",
     "domain": "mathematics", "spec": _eq("7*13", "91"),
     "corrected": "91 = 7 x 13, so it is composite.",
     "note_invert": "engine HOLDS that 7x13=91, which PROVES 91 is composite — the claim is false"},
]


def post(path, body, timeout=40):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def ask_llm(statement):
    """Ask the configured base model, plainly. Returns (verdict, note) or None."""
    try:
        import anthropic
    except Exception:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    model = os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5")
    sys_p = ("You are answering a quick true/false quiz. Reply with ONLY a JSON object "
             '{"verdict":"TRUE"|"FALSE","why":"<=12 words"}. No other text.')
    try:
        c = anthropic.Anthropic(api_key=key, timeout=20.0, max_retries=1)
        resp = c.messages.create(model=model, max_tokens=120, system=sys_p,
                                 messages=[{"role": "user", "content": "Is this statement true? " + statement}])
        raw = "".join(getattr(b, "text", "") for b in resp.content)
        i, j = raw.find("{"), raw.rfind("}")
        d = json.loads(raw[i:j + 1]) if i >= 0 else {}
        return (str(d.get("verdict", "")).upper(), str(d.get("why", "")), model)
    except Exception as e:  # noqa: BLE001
        return ("ERROR", str(e)[:80], model)


def main():
    do_llm = "--llm" in sys.argv
    results = []
    for c in SEED:
        step = {"id": "s1", "domain": c["domain"], "spec": c["spec"]}
        try:
            r = post("/derivation/verify", {"steps": [step], "seal": True})
        except Exception as e:  # noqa: BLE001
            r = {"verdict": "ERROR", "_err": str(e)[:120]}
        verdict = r.get("verdict")
        trail = (r.get("trail") or [{}])
        detail = trail[0].get("detail") if trail else ""
        status = trail[0].get("status") if trail else ""
        receipt = r.get("receipt") or {}
        row = {
            "id": c["id"], "statement": c["statement"], "category": c["category"],
            "claim_is_false": c["false"], "why": c.get("why", ""),
            "corrected": c.get("corrected", ""), "domain": c["domain"],
            "engine_verdict": verdict, "engine_status": status, "engine_detail": detail,
            "cite_url": receipt.get("cite_url"), "content_hash": receipt.get("content_hash"),
            "note_invert": c.get("note_invert", ""),
        }
        # Did the engine "catch" it? A false claim should NOT verify as a clean truth.
        # For most, BROKEN/MISMATCH = caught. For the invert proof (7x13=91 HOLDS proves
        # 91 composite), HOLDS is the catch — note_invert flags that.
        if c["false"]:
            row["engine_caught"] = (verdict in ("BROKEN",) or status in ("MISMATCH", "DISCORDANT")
                                    or bool(c.get("note_invert")) and verdict == "HOLDS")
        else:
            row["engine_caught"] = (verdict == "HOLDS" or status == "CONFIRMED")
        if do_llm:
            row["llm"] = ask_llm(c["statement"])
        results.append(row)

    false_claims = [r for r in results if r["claim_is_false"]]
    caught = [r for r in false_claims if r["engine_caught"]]
    summary = {
        "total_claims": len(results),
        "false_claims": len(false_claims),
        "true_controls": len(results) - len(false_claims),
        "engine_caught_false": len(caught),
        "engine_correct_all": sum(1 for r in results if r["engine_caught"]),
        "generated_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if do_llm:
        llm_affirmed_false = [r for r in false_claims
                              if r.get("llm") and r["llm"][0] == "TRUE"]
        summary["llm_model"] = results[0]["llm"][2] if results and results[0].get("llm") else "?"
        summary["llm_affirmed_false"] = len(llm_affirmed_false)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"summary": summary, "claims": results}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    for r in results:
        mark = "OK " if r["engine_caught"] else "!! "
        print(f"  {mark}{r['id']:16} verdict={r['engine_verdict']:10} status={r['engine_status']:12} seal={'yes' if r['cite_url'] else 'no'}")


if __name__ == "__main__":
    main()
