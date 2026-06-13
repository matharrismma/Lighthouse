# -*- coding: utf-8 -*-
"""
Public-endpoint verification benchmark (re-runnable).
Tests the LIVE moat -- POST https://narrowhighway.com/derivation/verify -- on a curated,
ground-truth-labelled set of TRUE claims (should HOLD) and deliberately FALSE claims
(should be caught). The metric that matters most for a verifier: FALSE-POSITIVE rate
(did it ever return HOLDS for a false claim = seal a falsehood). seal=False (no receipts
minted). Honest by design: a TRUE claim the engine cannot auto-confirm is reported as a
false-negative, not hidden.

Run: python tools/benchmark_public_verify.py
"""
import json, urllib.request

URL = "https://narrowhighway.com/derivation/verify"

def eq(a, b):   return {"mode": "equality", "params": {"expr_a": a, "expr_b": b, "variables": {}}}
def iq(l, r, op): return {"mode": "inequality", "params": {"lhs": l, "rhs": r, "op": op, "variables": {}}}
def dv(f, v, d): return {"mode": "derivative", "params": {"function": f, "variable": v, "claimed_derivative": d}}

# (label, spec, description). label True = should HOLD; False = should be caught.
CLAIMS = [
    # --- EQUALITY: TRUE ---
    (True,  eq("sin(x)**2+cos(x)**2", "1"), "Pythagorean identity"),
    (True,  eq("(x-1)*(x+1)", "x**2-1"), "difference of squares"),
    (True,  eq("(a+b)**2", "a**2+2*a*b+b**2"), "binomial square"),
    (True,  eq("2+2", "4"), "2+2=4"),
    (True,  eq("2**10", "1024"), "2^10"),
    (True,  eq("sqrt(2)*sqrt(2)", "2"), "sqrt(2)^2"),
    (True,  eq("sin(pi/6)", "1/2"), "sin(pi/6)"),
    (True,  eq("cos(pi/3)", "1/2"), "cos(pi/3)"),
    (True,  eq("((1+sqrt(5))/2)**2", "(1+sqrt(5))/2 + 1"), "golden ratio phi^2=phi+1"),
    (True,  eq("1+2+3+4+5+6+7+8+9+10", "55"), "sum 1..10"),
    (True,  eq("cos(2*x)", "1-2*sin(x)**2"), "double-angle cosine"),
    (True,  eq("exp(I*pi)+1", "0"), "Euler identity"),
    # --- EQUALITY: FALSE ---
    (False, eq("sin(x)**2+cos(x)**2", "2"), "Pythagorean perturbed"),
    (False, eq("(x-1)*(x+1)", "x**2+1"), "diff-of-squares sign error"),
    (False, eq("(a+b)**2", "a**2+b**2"), "binomial missing cross term"),
    (False, eq("2+2", "5"), "2+2=5"),
    (False, eq("2**10", "1000"), "2^10 wrong"),
    (False, eq("sqrt(2)*sqrt(2)", "4"), "sqrt(2)^2 wrong"),
    (False, eq("sin(pi/6)", "sqrt(2)/2"), "sin(pi/6) wrong value"),
    (False, eq("cos(pi/3)", "sqrt(3)/2"), "cos(pi/3) wrong value"),
    (False, eq("((1+sqrt(5))/2)**2", "(1+sqrt(5))/2 + 2"), "golden ratio perturbed"),
    (False, eq("1+2+3+4+5+6+7+8+9+10", "50"), "sum 1..10 wrong"),
    (False, eq("cos(2*x)", "1-sin(x)**2"), "double-angle wrong"),
    (False, eq("exp(I*pi)+1", "1"), "Euler identity wrong"),
    # removable-singularity / pole cases: true only off a measure-zero set, so NOT an
    # unconditional identity -- must NOT seal as HOLDS (regression guard for the moat crack)
    (False, eq("x/x", "1"), "x/x=1 (undefined at x=0)"),
    (False, eq("(x**2-1)/(x-1)", "x+1"), "(x^2-1)/(x-1)=x+1 (pole at x=1)"),
    (False, eq("x*(1/x)", "1"), "x*(1/x)=1 (undefined at x=0)"),
    (False, eq("sin(x)/sin(x)", "1"), "sin/sin=1 (pole where sin=0)"),
    (False, eq("log(x)/log(x)", "1"), "log/log=1 (pole where log=0)"),
    # symmetric rational identity (same domain on both sides) -- MUST still hold
    (True, eq("(x+1)/(x-1)", "1+2/(x-1)"), "symmetric rational identity"),
    # --- INEQUALITY: TRUE ---
    (True,  iq("3", "2", ">"), "3>2"),
    (True,  iq("2**10", "1000", ">"), "2^10>1000"),
    (True,  iq("pi", "3", ">"), "pi>3"),
    (True,  iq("sqrt(2)", "3/2", "<"), "sqrt(2)<1.5"),
    (True,  iq("exp(1)", "2", ">"), "e>2"),
    (True,  iq("8*sqrt(3)", "16", "<"), "hexagon < square shape measure"),
    # --- INEQUALITY: FALSE ---
    (False, iq("1", "2", ">"), "1>2"),
    (False, iq("pi", "3", "<"), "pi<3"),
    (False, iq("sqrt(2)", "3/2", ">"), "sqrt(2)>1.5"),
    (False, iq("exp(1)", "2", "<"), "e<2"),
    (False, iq("2**10", "1000", "<"), "2^10<1000"),
    (False, iq("8*sqrt(3)", "16", ">"), "hexagon > square (wrong)"),
    # --- DERIVATIVE: TRUE ---
    (True,  dv("cos(t)", "t", "-sin(t)"), "d/dt cos"),
    (True,  dv("sin(t)", "t", "cos(t)"), "d/dt sin"),
    (True,  dv("t**3", "t", "3*t**2"), "d/dt t^3"),
    (True,  dv("exp(t)", "t", "exp(t)"), "d/dt e^t"),
    (True,  dv("log(t)", "t", "1/t"), "d/dt ln t"),
    (True,  dv("t**2+3*t", "t", "2*t+3"), "d/dt poly"),
    (True,  dv("1/t", "t", "-1/t**2"), "d/dt 1/t"),
    (True,  dv("sin(2*t)", "t", "2*cos(2*t)"), "d/dt sin(2t)"),
    # --- DERIVATIVE: FALSE ---
    (False, dv("cos(t)", "t", "sin(t)"), "d/dt cos sign error"),
    (False, dv("sin(t)", "t", "-cos(t)"), "d/dt sin sign error"),
    (False, dv("t**3", "t", "3*t"), "d/dt t^3 wrong"),
    (False, dv("exp(t)", "t", "t*exp(t)"), "d/dt e^t wrong"),
    (False, dv("log(t)", "t", "t"), "d/dt ln t wrong"),
    (False, dv("t**2+3*t", "t", "2*t+1"), "d/dt poly wrong const"),
    (False, dv("1/t", "t", "1/t**2"), "d/dt 1/t sign error"),
    (False, dv("sin(2*t)", "t", "cos(2*t)"), "d/dt sin(2t) missing factor"),
]

def verify(spec):
    body = {"steps": [{"id": "b", "domain": "mathematics", "spec": spec}], "seal": False}
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                 headers={"content-type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode())

def run():
    cats = {"equality": [0,0,0,0], "inequality": [0,0,0,0], "derivative": [0,0,0,0]}  # n, correct, FP, FN
    false_pos, false_neg = [], []
    for label, spec, desc in CLAIMS:
        mode = spec["mode"]
        try:
            verdict = verify(spec).get("verdict")
        except Exception as e:
            verdict = "ERROR:" + str(e)[:40]
        holds = (verdict == "HOLDS")
        correct = (holds == label)
        c = cats[mode]; c[0] += 1
        if correct: c[1] += 1
        elif label is False and holds: c[2] += 1; false_pos.append(desc)   # sealed a falsehood (critical)
        elif label is True and not holds: c[3] += 1; false_neg.append((desc, verdict))
    n = sum(c[0] for c in cats.values()); corr = sum(c[1] for c in cats.values())
    fp = sum(c[2] for c in cats.values()); fn = sum(c[3] for c in cats.values())
    print("PUBLIC /derivation/verify benchmark  (seal=False)")
    print(f"{'mode':12s} {'n':>3s} {'correct':>8s} {'acc':>7s} {'false-pos':>10s} {'false-neg':>10s}")
    for m, c in cats.items():
        acc = 100.0*c[1]/c[0] if c[0] else 0
        print(f"{m:12s} {c[0]:3d} {c[1]:8d} {acc:6.1f}% {c[2]:10d} {c[3]:10d}")
    print(f"{'OVERALL':12s} {n:3d} {corr:8d} {100.0*corr/n:6.1f}% {fp:10d} {fn:10d}")
    print(f"\nFALSE-POSITIVES (sealed a falsehood -- CRITICAL): {len(false_pos)}")
    for d in false_pos: print("  !!", d)
    print(f"FALSE-NEGATIVES (rejected a truth): {len(false_neg)}")
    for d, v in false_neg: print(f"  -- {d}  (verdict={v})")
    return n, corr, fp, fn

if __name__ == "__main__":
    run()
