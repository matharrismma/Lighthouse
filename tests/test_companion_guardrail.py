"""Regression guard for the companion's load-bearing guardrail and its surfaces.

The companion (the work area + tutor + advisor) could become someone's whole window
outward, so its assistant voice MUST point to Christ and refuse the idol's seat. That
guardrail lives in the generative system prompts in api/app.py. This test makes sure it
cannot be silently removed -- and that the balance (genuinely useful, not preachy on
ordinary questions) stays intact. Source-level (no heavy import), fully deterministic.

Run: python -m pytest tests/test_companion_guardrail.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_APP = (_ROOT / "api" / "app.py").read_text(encoding="utf-8")


def test_intake_anti_idol_guardrail_present():
    """The intake router's prompt must point to Christ and refuse the idol's seat."""
    for phrase in ["never become an idol", "Jesus Christ", "Scripture",
                   "not the final authority", "conduit, never the source"]:
        assert phrase in _APP, f"anti-idol guardrail missing the phrase: {phrase!r}"


def test_guardrail_points_to_real_people_and_crisis_help():
    """On ultimate weight it must point OUTWARD to real people, not enclose."""
    low = _APP.lower()
    assert "pastor" in low and "church" in low, "must point to real human community"
    assert "prayer" in low, "must point to prayer"


def test_guardrail_is_not_coercive_on_ordinary_questions():
    """It must NOT preach on ordinary questions (generous, never coercive)."""
    assert "do NOT preach on ordinary questions" in _APP or "not preach on ordinary" in _APP.lower()


def test_decrease_metric_present():
    """Success inverts: leave the person needing the tool LESS, nearer to Christ."""
    low = _APP.lower()
    assert "needing this tool less" in low or "needing the tool less" in low


def test_lesson_prompt_points_to_christ_on_ultimate_topics():
    """A drafted lesson touching ultimate questions points to Christ + Scripture as source."""
    # within the lesson system prompt block
    assert "point toward Christ and Scripture as the source" in _APP
    assert "never positioning this lesson or this tool as the final word" in _APP


def test_generative_surfaces_registered():
    """The companion's generative endpoints must exist (the surfaces the guardrail governs)."""
    for ep in ('@app.post("/workspace/intake"', '@app.post("/tutor/lesson"',
               '@app.post("/derivation/solve"'):
        assert ep in _APP, f"missing generative endpoint: {ep}"


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
