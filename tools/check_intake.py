#!/usr/bin/env python3
"""Front-door router smoke test -- does /workspace/intake still route what you bring?

The engine has deterministic tests; the intake router is oracle-classified, so it has
none -- yet a broken prompt could silently send everything to "ask". This posts a few
UNAMBIGUOUS canonical inputs (the ones on the work-area chips) and checks each lands on
the intent it should. Classification of these is stable, so a mismatch is a real
regression, not oracle noise.

COSTS ORACLE CALLS: ~6 per run, and the endpoint is rate/budget gated. Run sparingly --
this is an on-demand diagnostic, NOT the frequent health check (see check_surfaces.py for
the cheap, oracle-free door check).

    python tools/check_intake.py [--base https://narrowhighway.com]

Exits 0 if every input routes as expected, 1 otherwise.
"""
import argparse
import json
import sys
import urllib.request

# (input text, expected intent) -- unambiguous on purpose, so routing is stable.
CASES = [
    ("milk, eggs, bread and a dozen apples", "list"),
    ("tell Sarah I'll be 15 minutes late for dinner tonight", "draft"),
    ("remember the wifi password is sunflower42", "note"),
    ("I want to learn about fractions", "learn"),
    ("17 is a prime number", "verify"),
    ("what is the capital of France", "ask"),
]


def post(base, text, timeout=35):
    data = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/workspace/intake", data=data,
        headers={"Content-Type": "application/json", "User-Agent": "nh-intake-check/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://narrowhighway.com")
    args = ap.parse_args()

    print("expected  got       input")
    print("-" * 60)
    ok_all = True
    for text, want in CASES:
        try:
            got = (post(args.base, text) or {}).get("intent", "?")
        except Exception as e:  # noqa: BLE001
            got = "ERR:" + type(e).__name__
        ok = got == want
        ok_all = ok_all and ok
        mark = "ok " if ok else ">> "
        print("%s%-9s %-9s %s" % (mark, want, got, text[:38]))
    print("-" * 60)
    print("ROUTER OK" if ok_all else "ROUTER MISROUTED -- check _INTAKE_SYS in api/app.py")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
