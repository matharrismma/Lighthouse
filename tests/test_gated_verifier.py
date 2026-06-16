"""Tests for the derivation verifier wired into the gated-generation pipeline.

Brings the full deterministic verifier stack to bear on generated output: a false
quantitative claim in the answer must become MISMATCH and be rejected by the FLOOR gate,
while honest/unstructurable prose degrades gracefully to NOT_APPLICABLE (no over-rejection,
no crash, no oracle key required for the safe path).

Run: PYTHONPATH=src python -m pytest tests/test_gated_verifier.py
     PYTHONPATH=src python tests/test_gated_verifier.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import generate_gated as G  # noqa: E402
from api import derivation as D  # noqa: E402

_TRUE = [{"id": "s0", "domain": "mathematics",
          "spec": {"mode": "derivative", "params": {"function": "x**2", "variable": "x",
                                                    "claimed_derivative": "2*x"}}}]
_FALSE = [{"id": "s0", "domain": "mathematics",
           "spec": {"mode": "derivative", "params": {"function": "x**2", "variable": "x",
                                                     "claimed_derivative": "3*x"}}}]


def test_derivation_verifier_registered():
    # available in the registry and in the opt-in DEEP set, but NOT the default
    # (it calls the paid oracle, so it is opt-in -- see DEFAULT_VERIFIERS comment).
    assert "derivation" in G.VERIFIERS
    assert "derivation" in G.DEEP_VERIFIERS
    assert "derivation" not in G.DEFAULT_VERIFIERS


def test_graceful_without_oracle():
    """No key / nothing structurable -> NOT_APPLICABLE, never a crash or false reject."""
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        vr = G.run_derivation_verifier("A purely prose answer with no formal claims.")
        assert vr.verdict == "NOT_APPLICABLE"
        assert vr.verifier == "derivation"
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


def test_false_claim_in_output_is_mismatch_and_rejected():
    """A false quantitative claim in the answer -> MISMATCH -> FLOOR gate rejects."""
    orig = D.structure_prose
    D.structure_prose = lambda _t: {"ok": True, "steps": _FALSE}
    try:
        vr = G.run_derivation_verifier("the derivative of x**2 is 3x")
        assert vr.verdict == "MISMATCH", f"false claim not caught: {vr.verdict}"

        class _Gen:
            text = "x" * 40
        fr = G.run_floor_gate(_Gen(), [vr])
        assert fr.decision == "reject", "floor gate did not reject a MISMATCH"
    finally:
        D.structure_prose = orig


def test_true_claim_in_output_confirms():
    orig = D.structure_prose
    D.structure_prose = lambda _t: {"ok": True, "steps": _TRUE}
    try:
        vr = G.run_derivation_verifier("the derivative of x**2 is 2x")
        assert vr.verdict == "CONFIRMED"
    finally:
        D.structure_prose = orig


def test_empty_structuring_is_not_applicable():
    orig = D.structure_prose
    D.structure_prose = lambda _t: {"ok": True, "steps": []}
    try:
        assert G.run_derivation_verifier("anything").verdict == "NOT_APPLICABLE"
    finally:
        D.structure_prose = orig


if __name__ == "__main__":
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
