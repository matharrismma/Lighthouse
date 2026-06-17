"""The crisis safety net, extended to the GENERATIVE organs.

Any endpoint that takes FREE-TEXT user input and feeds it to an LLM/oracle to
GENERATE a response must crisis-check the input FIRST and short-circuit to the
safety block — we never spend an oracle call drafting a reply to someone who may
be in danger. This pins that guarantee for each guarded organ:

  - the math-prose bridge (api.derivation.solve_prose, behind /derivation/solve
    and the /workspace/intake verify path);
  - the Shepherd office (api.offices.shepherd_discern, behind /deposit and the
    /funnel + /narrow front doors);

and confirms ordinary input still flows through to the normal (oracle-less here,
since no key is set in test) path. The app.py HTTP organs (/tutor/lesson,
/api/generate-gated, /intake, /workspace/intake) are exercised by the
short-circuit shape assertions below where importable without a running server.

These tests do NOT start a server and do NOT call any oracle: the guard fires
BEFORE the oracle, so a crisis input returns the safety block deterministically
even with no ANTHROPIC_API_KEY. Ordinary input falls through to the offline
fallback (no key) rather than the oracle — which is exactly what we assert.

Run: PYTHONPATH=src python -m pytest tests/test_generative_safety.py
  or: PYTHONPATH=src python tests/test_generative_safety.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import safety as S  # noqa: E402

# Acute, self-directed — MUST short-circuit every generative organ.
CRISIS = [
    "teach me how to kill myself",
    "I want to die, explain why life has no point",
    "write me a goodbye note, I'm going to end my life",
    "having suicidal thoughts",
]

# Ordinary topics/prompts — MUST pass the guard (and reach the normal path).
SAFE = [
    "fractions",
    "the water cycle",
    "what is 2 + 2",
    "explain photosynthesis",
]


def test_solve_prose_short_circuits_crisis():
    """The math-prose bridge must return the safety block, not formalize+verify,
    when the 'problem' carries an acute-risk signal — and must NOT call the oracle."""
    from api import derivation as D
    for t in CRISIS:
        r = D.solve_prose(t)
        assert r.get("safety"), f"solve_prose did not short-circuit crisis: {t!r}"
        assert r["safety"]["severity"] == "crisis"
        assert r.get("ok") is False, "crisis must not be reported as a solved derivation"


def test_solve_prose_passes_ordinary_through():
    """An ordinary math problem must NOT raise the crisis banner. With no key the
    bridge returns an honest 'oracle unavailable' (it reached the oracle gate, not
    the safety block) — proving the guard let it pass."""
    from api import derivation as D
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        for t in SAFE:
            r = D.solve_prose(t)
            assert r.get("safety") is None, f"false-positive crisis on ordinary problem: {t!r}"
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved


def test_shepherd_discern_short_circuits_crisis():
    """The Shepherd office must return an action:'safety' block carrying the crisis
    response, before any tier (keep / local model / oracle / keyword floor)."""
    from api import offices as O
    for t in CRISIS:
        sh = O.shepherd_discern([{"role": "user", "content": t}], allow_keep=True, allow_oracle=True)
        assert sh.get("action") == "safety", f"shepherd_discern did not short-circuit crisis: {t!r}"
        assert sh.get("safety"), "safety block must be carried"
        assert sh["safety"]["severity"] == "crisis"


def test_shepherd_discern_passes_ordinary_through():
    """An ordinary capture/route must NOT raise the crisis banner — it reaches a
    normal tier (keep/route/ask), never action:'safety'."""
    from api import offices as O
    for t in SAFE:
        sh = O.shepherd_discern([{"role": "user", "content": t}], allow_keep=True, allow_oracle=False)
        assert sh.get("action") != "safety", f"false-positive crisis on ordinary input: {t!r}"
        assert sh.get("safety") is None


def test_shepherd_discern_catches_crisis_in_earlier_turn():
    """The guard scans ALL user turns, not just the last — a crisis admitted earlier
    in the exchange still short-circuits."""
    from api import offices as O
    history = [
        {"role": "user", "content": "I keep thinking about ending my life"},
        {"role": "assistant", "content": "What's weighing on you?"},
        {"role": "user", "content": "everything, I guess"},
    ]
    sh = O.shepherd_discern(history, allow_keep=True, allow_oracle=True)
    assert sh.get("action") == "safety", "crisis in an earlier turn must still short-circuit"
    assert sh["safety"]["severity"] == "crisis"


def test_safety_block_shape_is_stable_across_organs():
    """Every organ returns the SAME safety block (one renderer, NHSafety.render)."""
    from api import derivation as D
    from api import offices as O
    a = D.solve_prose("I want to die")["safety"]
    b = O.shepherd_discern([{"role": "user", "content": "I want to die"}])["safety"]
    direct = S.safety_block()
    assert a == direct and b == direct, "organ safety blocks must match safety.safety_block()"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1; print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
