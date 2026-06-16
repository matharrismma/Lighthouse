"""Offline unit tests for the verification TRUST PATH -- the check/derivation pipeline.

This is the engine's single most load-bearing surface: `check` and the public
/derivation/verify route both funnel through api/derivation.py. Before this file it
had ZERO offline tests -- it was exercised only live, over HTTP, by a math-only
benchmark. That is exactly the gap that let the `def scripture` module-shadowing
regression through.

These tests assert the CARDINAL guarantee directly: a false or unverifiable claim is
never crowned HOLDS, and every failure mode is fail-closed (ERROR/BROKEN), never a
silent pass or a crash. They are fully offline and deterministic -- no network, no
oracle key required (the one Anthropic call is the prose->steps *structurer*, never
the judge; its no-key path is tested here too).

Run either way:
  PYTHONPATH=src python -m pytest tests/test_derivation_pipeline.py
  PYTHONPATH=src python tests/test_derivation_pipeline.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import derivation as D  # noqa: E402


def _deriv(fn, var, claimed):
    return {"mode": "derivative", "params": {"function": fn, "variable": var,
                                             "claimed_derivative": claimed}}


# ── the cardinal guarantee: a true chain HOLDS, a false one never does ──────────

def test_true_single_step_holds():
    r = D.verify_derivation([{"id": "s0", "domain": "mathematics",
                              "spec": _deriv("x**2", "x", "2*x")}])
    assert r["verdict"] == "HOLDS"
    assert r["confirmed_steps"] == 1
    assert r["broken_at"] is None and r["gap_at"] is None


def test_true_multi_step_chain_holds():
    steps = [
        {"id": "s0", "domain": "mathematics", "spec": _deriv("x**2", "x", "2*x")},
        {"id": "s1", "domain": "mathematics", "spec": _deriv("x**3", "x", "3*x**2"),
         "uses": ["s0"]},
    ]
    r = D.verify_derivation(steps)
    assert r["verdict"] == "HOLDS"
    assert r["confirmed_steps"] == 2


def test_false_single_step_breaks():
    r = D.verify_derivation([{"id": "s0", "domain": "mathematics",
                              "spec": _deriv("x**2", "x", "3*x")}])
    assert r["verdict"] == "BROKEN"
    assert r["broken_at"] == "s0"
    assert r["verdict"] != "HOLDS"


def test_no_false_claim_ever_holds():
    """The cardinal promise, across domains: a FALSE claim is never crowned HOLDS.
    Each spec encodes a deliberately false assertion; the verdict must not be HOLDS
    (BROKEN or INCOMPLETE are both acceptable -- only HOLDS is forbidden)."""
    false_steps = [
        # math: d/dx x^2 is 2x, not 3x
        {"domain": "mathematics", "spec": _deriv("x**2", "x", "3*x")},
        # number theory: 15 is not prime
        {"domain": "number_theory", "spec": {"n_prime": 15, "claimed_prime": True}},
        # geometry: 3-4-6 is not a right triangle
        {"domain": "geometry", "spec": {"pyth_a": 3, "pyth_b": 4, "pyth_c": 6,
                                        "claimed_right_triangle": True}},
        # music: 440->880 Hz is an octave, not a fifth
        {"domain": "music_theory", "spec": {"freq_a": 440, "freq_b": 880,
                                            "claimed_interval": "fifth"}},
    ]
    for step in false_steps:
        r = D.verify_derivation([dict(step, id="s0")])
        assert r["verdict"] != "HOLDS", f"FALSE claim crowned HOLDS: {step}"


def test_pole_guard_removable_singularity():
    """The 'moat crack': x/x simplifies to 1 but differs at the pole x=0, so the
    equality verifier must return MISMATCH, not CONFIRMED. Regression guard."""
    sr = D.verify_step("mathematics", {"mode": "equality",
                                       "params": {"expr_a": "x/x", "expr_b": "1",
                                                  "variables": ["x"]}})
    assert sr["status"] == "MISMATCH"


# ── fail-closed: every failure path is ERROR/BROKEN, never a pass or a crash ────

def test_unknown_domain_fails_closed():
    assert D.verify_step("totally_made_up_domain", {})["status"] == "ERROR"


def test_empty_domain_fails_closed():
    assert D.verify_step("", {"anything": 1})["status"] == "ERROR"


def test_malformed_spec_fails_closed_not_crash():
    """A malformed spec (mode set, params empty) used to raise KeyError out of the
    chain runner (a 500). It must now fail closed to ERROR and the chain to BROKEN."""
    sr = D.verify_step("mathematics", {"mode": "derivative", "params": {}})
    assert sr["status"] == "ERROR"  # no exception escapes
    r = D.verify_derivation([{"id": "s0", "domain": "mathematics",
                              "spec": {"mode": "derivative", "params": {}}}])
    assert r["verdict"] == "BROKEN"  # the runner did not crash


def test_broken_link_breaks_even_when_step_confirms():
    """A step whose own math CONFIRMS still breaks the chain if it 'uses' a step that
    does not exist -- the link integrity is part of the trust."""
    r = D.verify_derivation([{"id": "s1", "domain": "mathematics",
                              "spec": _deriv("x**3", "x", "3*x**2"), "uses": ["ghost"]}])
    assert r["verdict"] == "BROKEN"
    assert r["broken_at"] == "s1"
    assert r["trail"][0]["status"] == "CONFIRMED"      # the step itself is fine
    assert r["trail"][0].get("missing_refs") == ["ghost"]


def test_builds_on_unconfirmed_breaks():
    """A later step may not build on an earlier step that failed."""
    steps = [
        {"id": "s0", "domain": "mathematics", "spec": _deriv("x**2", "x", "9*x")},  # false
        {"id": "s1", "domain": "mathematics", "spec": _deriv("x**3", "x", "3*x**2"),
         "uses": ["s0"]},
    ]
    r = D.verify_derivation(steps)
    assert r["verdict"] == "BROKEN"


def test_empty_steps_is_error():
    assert D.verify_derivation([])["verdict"] == "ERROR"
    assert D.verify_derivation("not a list")["verdict"] == "ERROR"


# ── the oracle boundary: no key -> structurer fails closed, never fabricates ────

def test_structure_prose_fails_closed_without_key():
    """structure_prose only FORMALIZES prose; with no API key it must return ok:False
    (and solve_prose must report structured:False), never a fabricated verdict."""
    import os
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        assert D.structure_prose("the derivative of x squared")["ok"] is False
        sp = D.solve_prose("the derivative of x squared")
        assert sp["ok"] is False and sp["structured"] is False
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


def test_structure_prose_empty_problem():
    assert D.structure_prose("")["ok"] is False


if __name__ == "__main__":  # script mode (no pytest required)
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
