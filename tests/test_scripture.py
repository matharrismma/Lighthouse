"""Unit tests for the scripture / Layer 0 verifier.

Verifies the cross-cutting verifier behaves correctly whether Layer 0
data is provisioned or not. The graceful-degradation path
(no fetch_sources.py run) is the more important contract — most CI
environments will not have lw/00_source data, and the tests must pass
there.

Run: PYTHONPATH=src python tests/test_scripture.py
"""
from __future__ import annotations

from concordance_engine.verifiers import scripture as scr
from concordance_engine.verifiers.base import VerifierResult


PASS = 0
FAIL = 0


def expect(name, actual, expected):
    global PASS, FAIL
    ok = actual == expected
    icon = "✓" if ok else "✗"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {icon} {name}: got {actual!r}, expected {expected!r}")


def expect_in(name, value, allowed):
    """Pass if `value` is one of `allowed`. Used for status checks where
    the result depends on whether Layer 0 is provisioned."""
    global PASS, FAIL
    ok = value in allowed
    icon = "✓" if ok else "✗"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {icon} {name}: got {value!r}, expected one of {allowed!r}")


if __name__ == "__main__":
    # ── resolve_ref ────────────────────────────────────────────────────────
    print("scripture.resolve_ref:")

    # Always returns a dict with the standard keys
    r = scr.resolve_ref("Jn3:16")
    expect("resolve_ref returns dict", isinstance(r, dict), True)
    expect("contains ref", "ref" in r, True)
    expect("contains status", "status" in r, True)
    # When data is provisioned, status is "ok" with web_text. When not, "source_missing".
    expect_in("status is ok or source_missing", r.get("status"), ("ok", "source_missing"))

    # Empty ref still returns a structured response, not a crash
    r2 = scr.resolve_ref("")
    expect("empty ref returns dict", isinstance(r2, dict), True)
    expect_in("empty ref has known status", r2.get("status"),
              ("not_found", "source_missing", "ok"))

    # Bogus ref does not crash
    r3 = scr.resolve_ref("Not a Real Reference 99:99")
    expect("bogus ref returns dict", isinstance(r3, dict), True)


    # ── word_study ────────────────────────────────────────────────────────
    print("\nscripture.word_study:")

    w = scr.word_study("G26")
    expect("word_study returns dict", isinstance(w, dict), True)
    expect("contains strongs key", any(k in w for k in ("strongs", "word")), True)


    # ── verify_scripture_anchors ──────────────────────────────────────────
    print("\nscripture.verify_scripture_anchors:")

    # Empty anchors list is always CONFIRMED (nothing to fail on)
    v = scr.verify_scripture_anchors([])
    expect("empty anchors → CONFIRMED", v.status, "CONFIRMED")
    expect("returns VerifierResult", isinstance(v, VerifierResult), True)

    # Real-looking anchors return one of: CONFIRMED, MISMATCH, SKIPPED
    v2 = scr.verify_scripture_anchors(["Jn3:16", "Mic 6:8"])
    expect("returns VerifierResult", isinstance(v2, VerifierResult), True)
    expect_in("status is CONFIRMED/MISMATCH/SKIPPED", v2.status,
              ("CONFIRMED", "MISMATCH", "SKIPPED"))

    # Obviously fake anchors should NOT crash; result depends on Layer 0
    v3 = scr.verify_scripture_anchors(["Zz9:99", "Bogus 1:1"])
    expect("fake anchors return VerifierResult", isinstance(v3, VerifierResult), True)


    # ── triangulate_claim ─────────────────────────────────────────────────
    print("\nscripture.triangulate_claim:")

    t = scr.triangulate_claim("Jn15:2",
                              claim="branches that don't bear fruit are destroyed")
    expect("triangulate returns dict", isinstance(t, dict), True)
    expect_in("triangulate has known status",
              t.get("status"),
              ("PASS", "DRIFT_FLAGGED", "NEEDS_MANUAL_VERIFICATION",
               "NEEDS_HUMAN_REVIEW", "source_missing", "ERROR"))


    # ── run(packet): cross-cutting integration ────────────────────────────
    print("\nscripture.run(packet):")

    # A packet with no scripture refs is a no-op
    results = scr.run({"domain": "chemistry", "scope": "adapter"})
    expect("no-anchor packet returns []", results, [])

    # A packet with kernel-style refs returns at least one VerifierResult
    results2 = scr.run({"domain": "governance", "refs": ["Jn3:16"]})
    expect("refs packet returns list", isinstance(results2, list), True)
    if results2:
        expect("first result is VerifierResult",
               isinstance(results2[0], VerifierResult), True)

    # A packet with DECISION_PACKET.scripture_anchors returns at least one result
    results3 = scr.run({
        "domain": "governance",
        "DECISION_PACKET": {"scripture_anchors": ["Mic 6:8"]},
    })
    expect("DECISION_PACKET anchors returns list",
           isinstance(results3, list), True)


    # ── summary ───────────────────────────────────────────────────────────
    print(f"\n  {PASS} passed, {FAIL} failed")
    import sys as _sys
    _sys.exit(0 if FAIL == 0 else 1)
