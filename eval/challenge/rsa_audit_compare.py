"""RSA Key Generation Audit — Cross-Model Comparison.

Ten questions across RSA, quantum, and cryptographic authentication, ordered
by computational difficulty. Runs four model configurations:

  1. Claude Haiku + Lighthouse tools  (can call verifiers — expected 10/10)
  2. Claude Haiku alone               (no tools)
  3. Claude Sonnet alone              (no tools, larger model)
  4. Claude Opus alone                (no tools, flagship model — head-to-head)

RSA parameters (pre-verified):
    p = 1013, q = 1019
    n = p * q = 1032247           (20-bit key — well below NIST 2048-bit minimum)
    phi_n = (p-1)(q-1) = 1030216
    e = 65537
    d = 65537^-1 mod 1030216 = 498233   (extended Euclidean)
    d_p = 65537^-1 mod (p-1) = 65537^-1 mod 1012 = 329   (CRT exponent)

Hard computations no LLM can do from memory:
    Q4:  65537 * 498233 mod 1030216 = 1                (modular inverse)
    Q7:  floor(pi * sqrt(2^20) / 4) = 804              (Grover iterations)
    Q8:  -sum(l*log2(l) for l in [0.7,0.2,0.1]) = 1.1568 bits (von Neumann entropy)
    Q9:  HMAC-SHA256('lighthouse', 'p=1013,q=1019,n=1032247') (deterministic hash)
    Q10: 65537 * 329 mod 1012 = 1                      (CRT d_p modular inverse)

Usage:
    python eval/challenge/rsa_audit_compare.py
    python eval/challenge/rsa_audit_compare.py --skip-sonnet
    python eval/challenge/rsa_audit_compare.py --delay 0.5
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

_env = REPO / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ[k.strip()] = v.strip()

# pre-computed HMAC (verified: sha256 hmac of 'p=1013,q=1019,n=1032247' key='lighthouse')
_HMAC_CLAIMED = "13c17c4cb5f8a35dfde0223f44ea0728036d74b0ea51e0e86a2201f67c2e9806"

# ── questions ─────────────────────────────────────────────────────────────────

QUESTIONS: List[Dict[str, Any]] = [
    # ── easy: parametric knowledge tests ─────────────────────────────────────
    {
        "id": "RSA-Q1",
        "difficulty": "easy",
        "label": "Is p=1013 prime?",
        "prompt": (
            "Use verify_number_theory to check whether p=1013 is prime. "
            "Spec: {n_prime: 1013, claimed_prime: true}. "
            "Is p=1013 a prime number? Answer yes or no."
        ),
        "prompt_alone": "Is 1013 a prime number? Answer yes or no.",
        "ground_truth": "yes",
        "note": "Basic primality — parametric knowledge for large models",
    },
    {
        "id": "RSA-Q2",
        "difficulty": "easy",
        "label": "Is q=1019 prime?",
        "prompt": (
            "Use verify_number_theory to check whether q=1019 is prime. "
            "Spec: {n_prime: 1019, claimed_prime: true}. "
            "Is q=1019 a prime number? Answer yes or no."
        ),
        "prompt_alone": "Is 1019 a prime number? Answer yes or no.",
        "ground_truth": "yes",
        "note": "Basic primality",
    },
    {
        "id": "RSA-Q3",
        "difficulty": "medium",
        "label": "gcd(e, phi_n) = 1?",
        "prompt": (
            "RSA audit: e=65537, phi_n=1030216. "
            "Use verify_number_theory with {gcd_a: 65537, gcd_b: 1030216, claimed_gcd: 1}. "
            "Is gcd(e, phi_n) = 1, confirming e is a valid public exponent? Answer yes or no."
        ),
        "prompt_alone": (
            "RSA audit: e=65537, phi_n=(p-1)*(q-1)=1030216. "
            "Is gcd(65537, 1030216) = 1? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "GCD check — 65537 is prime so likely coprime; models may know this",
    },
    # ── hard: modular inverse (requires extended Euclidean) ──────────────────
    {
        "id": "RSA-Q4",
        "difficulty": "hard",
        "label": "Is d=498233 the private exponent?",
        "prompt": (
            "RSA audit: e=65537, phi_n=1030216, claimed d=498233. "
            "Verify that e*d mod phi_n = 1: call verify_number_theory with "
            "{mod_a: 65537, mod_m: 1030216, claimed_inverse: 498233}. "
            "Is d=498233 the correct modular inverse of e=65537 mod phi_n=1030216? Answer yes or no."
        ),
        "prompt_alone": (
            "RSA audit: e=65537, phi_n=1030216, claimed d=498233. "
            "To verify: 65537 * 498233 mod 1030216 must equal 1. "
            "Is d=498233 the correct private exponent? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "HARD: 65537 * 498233 mod 1030216 — no LLM can compute this reliably",
    },
    # ── medium: known thresholds ──────────────────────────────────────────────
    {
        "id": "RSA-Q5",
        "difficulty": "medium",
        "label": "Is n=1032247 (20-bit) weak?",
        "prompt": (
            "Use verify_cryptography with {cipher: RSA, key_bits: 20, claimed_key_strength: weak}. "
            "Is a 20-bit RSA key cryptographically weak by NIST standards? Answer yes or no."
        ),
        "prompt_alone": (
            "RSA key n=1032247 is approximately 20 bits. NIST minimum is 2048 bits. "
            "Is a 20-bit RSA key cryptographically weak? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "NIST key-strength classification — models know this threshold",
    },
    {
        "id": "RSA-Q6",
        "difficulty": "medium",
        "label": "BB84 QBER=8% secure?",
        "prompt": (
            "Use verify_quantum_computing with {qber: 0.08, claimed_secure: true}. "
            "BB84 quantum channel QBER=8%, threshold is 11%. "
            "Is BB84 with QBER=8% secure? Answer yes or no."
        ),
        "prompt_alone": (
            "BB84 quantum key distribution: QBER=8%, security threshold is 11%. "
            "Is this channel considered secure? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "BB84 threshold is published — models with QKD knowledge pass this",
    },
    # ── hard: precise formula + non-trivial computation ──────────────────────
    {
        "id": "RSA-Q7",
        "difficulty": "hard",
        "label": "Grover T=804 for 2^20 keyspace?",
        "prompt": (
            "A quantum adversary applies Grover's algorithm to search an RSA 20-bit keyspace "
            "of N=2^20=1,048,576 states. Optimal iterations: T = floor(pi * sqrt(N) / 4). "
            "Call verify_quantum_computing with {n_items: 1048576, claimed_grover_iterations: 804}. "
            "Is T=804 the correct number of Grover iterations? Answer yes or no."
        ),
        "prompt_alone": (
            "Grover's algorithm searches N items in T = floor(pi * sqrt(N) / 4) iterations. "
            "For a 20-bit RSA keyspace N=2^20=1,048,576: "
            "is T=804 the correct number of optimal Grover iterations? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "HARD: pi * sqrt(1048576) / 4 = pi * 256 = 804.247... -> floor = 804",
    },
    {
        "id": "RSA-Q8",
        "difficulty": "hard",
        "label": "VNE of [0.7,0.2,0.1] = 1.1568 bits?",
        "prompt": (
            "A quantum system has density matrix eigenvalues [0.7, 0.2, 0.1]. "
            "Von Neumann entropy: S = -sum(lambda * log2(lambda)). "
            "Call verify_quantum_computing with "
            "{density_eigenvalues: [0.7, 0.2, 0.1], claimed_entropy_bits: 1.1568}. "
            "Is S approximately 1.1568 bits? Answer yes or no."
        ),
        "prompt_alone": (
            "A quantum density matrix has eigenvalues [0.7, 0.2, 0.1]. "
            "Von Neumann entropy S = -(0.7*log2(0.7) + 0.2*log2(0.2) + 0.1*log2(0.1)). "
            "Is S approximately 1.1568 bits? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "HARD: -(0.7*(-0.5146)+0.2*(-2.3219)+0.1*(-3.3219)) = 1.1568 bits",
    },
    # ── impossible: deterministic hash no model can know ─────────────────────
    {
        "id": "RSA-Q9",
        "difficulty": "impossible",
        "label": "HMAC-SHA256 audit fingerprint correct?",
        "prompt": (
            "RSA audit authentication: verify the HMAC-SHA256 fingerprint. "
            f"Key='lighthouse', message='p=1013,q=1019,n=1032247', "
            f"claimed HMAC={_HMAC_CLAIMED}. "
            "Call verify_cryptography with {"
            "hmac_algorithm: sha256, hmac_key: lighthouse, "
            "hmac_data: 'p=1013,q=1019,n=1032247', "
            f"claimed_hmac_hex: {_HMAC_CLAIMED}"
            "}. Does the HMAC match? Answer yes or no."
        ),
        "prompt_alone": (
            "RSA audit authentication: "
            "key='lighthouse', message='p=1013,q=1019,n=1032247'. "
            f"The claimed HMAC-SHA256 is: {_HMAC_CLAIMED}. "
            "Is this the correct HMAC? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "IMPOSSIBLE: no LLM can compute HMAC-SHA256 from memory; tools required",
    },
    # ── hard: CRT private exponent (modular inverse in smaller ring) ──────────
    {
        "id": "RSA-Q10",
        "difficulty": "hard",
        "label": "CRT d_p=329 (e^-1 mod p-1)?",
        "prompt": (
            "RSA-CRT optimization: the CRT private exponent is d_p = e^(-1) mod (p-1). "
            "For e=65537, p=1013 (p-1=1012), claimed d_p=329. "
            "Verify: 65537 * 329 mod 1012 must equal 1. "
            "Call verify_number_theory with {mod_a: 65537, mod_m: 1012, claimed_inverse: 329}. "
            "Is d_p=329 the correct CRT private exponent? Answer yes or no."
        ),
        "prompt_alone": (
            "RSA-CRT: d_p = e^(-1) mod (p-1) = 65537^(-1) mod 1012. "
            "Claimed d_p=329. To verify: 65537 * 329 mod 1012 must equal 1. "
            "Is d_p=329 the correct CRT private exponent? Answer yes or no."
        ),
        "ground_truth": "yes",
        "note": "HARD: 65537 * 329 mod 1012 — requires exact modular arithmetic in smaller ring",
    },
]


# ── scoring ───────────────────────────────────────────────────────────────────

def _parse(reply: str) -> str:
    reply = reply.strip().lower()
    if re.search(r"\byes\b", reply):
        return "yes"
    if re.search(r"\bno\b", reply):
        return "no"
    return reply.split()[0] if reply else ""


def _score(reply: str, gt: str) -> bool:
    return _parse(reply) == gt.lower()


# ── tool dispatch ─────────────────────────────────────────────────────────────

def _build_tool_schemas() -> List[Dict]:
    from concordance_engine.mcp_server.tools import TOOLS
    return [{
        "name": t["name"],
        "description": t.get("description", t["name"]),
        "input_schema": t.get("inputSchema", {"type": "object", "properties": {}}),
    } for t in TOOLS]


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
    "You are a precise scientific assistant. When asked a yes/no question, "
    "answer ONLY with 'yes' or 'no'. Do not add explanation."
)


def call_alone(client, model: str, prompt: str, max_tokens: int = 64) -> str:
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
    return "".join(parts).strip()


def call_with_tools(client, model: str, tool_schemas: List[Dict],
                    prompt: str, max_iters: int = 6) -> Tuple[str, int]:
    history = [{"role": "user", "content": prompt}]
    tool_calls = 0
    for _ in range(max_iters):
        resp = client.messages.create(
            model=model, max_tokens=512, system=SYSTEM,
            messages=history, tools=tool_schemas,
        )
        history.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            parts = [b.text for b in resp.content
                     if getattr(b, "type", "") == "text"]
            return "".join(parts).strip(), tool_calls
        results = []
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use":
                tool_calls += 1
                out = _dispatch_tool(block.name, block.input)
                results.append({"type": "tool_result",
                                 "tool_use_id": block.id,
                                 "content": json.dumps(out)})
        if results:
            history.append({"role": "user", "content": results})
        else:
            break
    last = history[-1] if history else {}
    parts = []
    if isinstance(last.get("content"), list):
        parts = [b.text for b in last["content"]
                 if getattr(b, "type", "") == "text"]
    return "".join(parts).strip() or "[no text]", tool_calls


# ── run one config ────────────────────────────────────────────────────────────

def run_config(client, label: str, model: str,
               use_tools: bool, tool_schemas: List[Dict],
               delay: float) -> List[Dict]:
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    rows = []
    for q in QUESTIONS:
        prompt = q["prompt"] if use_tools else q["prompt_alone"]
        try:
            if use_tools:
                reply, n_calls = call_with_tools(client, model, tool_schemas, prompt)
            else:
                reply = call_alone(client, model, prompt)
                n_calls = 0
        except Exception as e:
            reply = f"[ERROR: {e}]"
            n_calls = 0
        correct = _score(reply, q["ground_truth"])
        parsed = _parse(reply)
        marker = "+" if correct else "x"
        calls_str = f" ({n_calls}t)" if use_tools else ""
        diff_tag = f"[{q['difficulty'][:4]}]"
        print(f"  {marker} {q['id']} {diff_tag:6s}  parsed={parsed:3s}  "
              f"{reply[:50]}{calls_str}")
        rows.append({
            "id": q["id"],
            "difficulty": q["difficulty"],
            "label": q["label"],
            "correct": correct,
            "parsed": parsed,
            "reply": reply[:150],
            "tool_calls": n_calls,
            "note": q["note"],
        })
        if delay > 0:
            time.sleep(delay)
    n = len(rows)
    c = sum(r["correct"] for r in rows)
    print(f"  ── {c}/{n} = {c/n:.0%}")
    return rows


# ── comparison table ──────────────────────────────────────────────────────────

def print_comparison(configs: List[Tuple[str, List[Dict]]]) -> None:
    col_w = 15
    total_w = 10 + 38 + col_w * len(configs) + 2 * len(configs)

    print(f"\n{'='*total_w}")
    print("  COMPARISON TABLE — RSA Audit (10 questions, all GT=yes)")
    print(f"{'─'*total_w}")

    hdr = f"  {'ID':8s} {'Label':30s}"
    for label, _ in configs:
        hdr += f"  {label[:col_w]:{col_w}s}"
    print(hdr)
    print(f"{'─'*total_w}")

    for i, q in enumerate(QUESTIONS):
        diff_star = {"easy": " ", "medium": "*", "hard": "**", "impossible": "***"}
        tag = diff_star.get(q["difficulty"], "")
        row = f"  {q['id']:8s} {q['label'][:28]+tag:30s}"
        for label, rows in configs:
            r = rows[i]
            if r["tool_calls"] > 0:
                cell = f"YES+ [{r['tool_calls']}t]" if r["correct"] else f"NO-  [{r['tool_calls']}t]"
            else:
                cell = "YES+" if r["correct"] else "NO- "
            row += f"  {cell:{col_w}s}"
        print(row)

    print(f"{'─'*total_w}")
    totals = f"  {'TOTAL':38s}"
    for label, rows in configs:
        n, c = len(rows), sum(r["correct"] for r in rows)
        totals += f"  {c}/{n}={c/n:.0%}{'':{col_w-7}s}"
    print(totals)
    print(f"{'='*total_w}")

    # difficulty breakdown
    print()
    print("  Difficulty legend:  (no star)=easy  *=medium  **=hard  ***=impossible")
    print()

    # lift analysis: tools vs each alone config
    tools_rows = configs[0][1]
    for cname, alone_rows in configs[1:]:
        fixed = [q["id"] for i, q in enumerate(QUESTIONS)
                 if tools_rows[i]["correct"] and not alone_rows[i]["correct"]]
        broken = [q["id"] for i, q in enumerate(QUESTIONS)
                  if not tools_rows[i]["correct"] and alone_rows[i]["correct"]]
        print(f"  Haiku+tools vs {cname}:")
        if fixed:
            for qid in fixed:
                q = next(x for x in QUESTIONS if x["id"] == qid)
                print(f"    FIXED  {qid}  [{q['difficulty']}]  {q['note'][:60]}")
        else:
            print("    (no questions fixed)")
        if broken:
            for qid in broken:
                q = next(x for x in QUESTIONS if x["id"] == qid)
                print(f"    BROKE  {qid}  [{q['difficulty']}]  {q['note'][:60]}")
        print()

    print("  KEY FINDINGS:")
    print("    Q4  (modular inverse): 65537 * 498233 mod 1030216 — no LLM can compute this")
    print("    Q7  (Grover T=804):    pi * 1024 / 4 = 804.247 -> floor — easy to be off by 1")
    print("    Q8  (von Neumann):     -sum(l*log2(l)) for [0.7,0.2,0.1] — must be 1.1568 exactly")
    print("    Q9  (HMAC-SHA256):     deterministic hash — impossible for any LLM from memory")
    print("    Q10 (CRT d_p=329):     65537 * 329 mod 1012 — modular inverse in smaller ring")
    print(f"{'='*total_w}\n")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--haiku-model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--sonnet-model", default="claude-sonnet-4-6")
    parser.add_argument("--opus-model", default="claude-opus-4-7")
    parser.add_argument("--delay", type=float, default=0.3)
    parser.add_argument("--skip-sonnet", action="store_true")
    parser.add_argument("--skip-opus", action="store_true")
    args = parser.parse_args()

    from anthropic import Anthropic
    client = Anthropic()
    tool_schemas = _build_tool_schemas()

    print(f"\n  RSA KEY GENERATION AUDIT — Cross-Model Comparison (10 questions)")
    print(f"  p=1013  q=1019  n=1032247  e=65537  d=498233  phi_n=1030216")
    print(f"  All ground truths: yes")
    print(f"  Hard floor: Q9 (HMAC-SHA256) is impossible for any LLM without tools")

    configs = []

    rows_tools = run_config(client,
                            f"CONFIG 1: {args.haiku_model} + LIGHTHOUSE TOOLS",
                            args.haiku_model, True, tool_schemas, args.delay)
    configs.append(("Haiku+tools", rows_tools))

    rows_haiku = run_config(client,
                            f"CONFIG 2: {args.haiku_model} ALONE",
                            args.haiku_model, False, tool_schemas, args.delay)
    configs.append(("Haiku alone", rows_haiku))

    if not args.skip_sonnet:
        rows_sonnet = run_config(client,
                                 f"CONFIG 3: {args.sonnet_model} ALONE",
                                 args.sonnet_model, False, tool_schemas, args.delay)
        configs.append(("Sonnet alone", rows_sonnet))

    if not args.skip_opus:
        rows_opus = run_config(client,
                               f"CONFIG 4: {args.opus_model} ALONE (head-to-head)",
                               args.opus_model, False, tool_schemas, args.delay)
        configs.append(("Opus alone", rows_opus))

    print_comparison(configs)

    out_path = THIS.parent / "rsa_audit_results.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for label, rows in configs:
            for r in rows:
                f.write(json.dumps({"config": label, **r}) + "\n")
    print(f"  Results saved to {out_path.name}")


if __name__ == "__main__":
    main()
