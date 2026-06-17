"""The crisis safety net — the floor under the floor.

A person who brings an acute-risk condition (suicide, self-harm, overdose) must
be pointed to immediate, real help BEFORE any remedy. This pins that guarantee:
  - acute signals always trigger the safety block (a miss can cost a life);
  - ordinary conditions never do (a banner on "anxiety" would desensitize);
  - when it triggers it carries a real crisis line (988), a real-person nudge,
    and points to Christ without posing as the help itself;
  - it rides at the top level of the apothecary compound AND through the floor,
    so no surface can bury it.

Run: PYTHONPATH=src python -m pytest tests/test_apothecary_safety.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api import safety as S  # noqa: E402

# Acute, self-directed — MUST trigger.
CRISIS = [
    "I keep thinking about ending my life",
    "I want to die",
    "I'm going to kill myself",
    "having suicidal thoughts",
    "I want to hurt myself",
    "there's no reason to live anymore",
    "I feel better off dead",
    "I overdosed last night",
    "I wish I were dead",
    "thinking about self-harm",
]

# Ordinary or other-directed — MUST NOT trigger (false positives erode trust).
SAFE = [
    "anxiety",
    "marriage strain",
    "work pressure",
    "grief",
    "I could kill him for what he did",   # anger at another, not self
    "dying to see my grandkids",          # idiom
    "dead tired all the time",            # idiom
    "my houseplant died",
    "I feel sad and lonely",
    "chronic illness",
    "",                                   # empty
]


def test_acute_signals_always_trigger():
    for t in CRISIS:
        assert S.crisis_check(t), f"acute signal NOT caught (a miss can cost a life): {t!r}"


def test_ordinary_conditions_never_trigger():
    for t in SAFE:
        assert S.crisis_check(t) is None, f"false positive on {t!r} -- this desensitizes the net"


def test_block_carries_real_help_and_points_beyond_the_tool():
    b = S.safety_block()
    assert b["severity"] == "crisis"
    blob = str(b)
    assert "988" in blob, "must carry the 988 crisis line"
    assert b["immediate"], "must list immediate options"
    # points to a real person and to Christ, and is honest about its own limit
    assert b["a_real_person"]
    assert "Psalm 34:18" in b["in_christ"] or "LORD" in b["in_christ"]
    assert "not a counselor" in b["honest_limit"] or "real person" in b["honest_limit"]


def test_compound_surfaces_safety_at_top_level_and_in_floor():
    from api import apothecary as A
    r = A.compound("I keep thinking about ending my life", lang="en")
    assert r.get("safety"), "crisis safety must ride at the TOP level of the compound"
    assert r["safety"]["severity"] == "crisis"
    floor = r.get("floor") or {}
    assert floor.get("safety"), "the floor under the floor must also carry it"
    # ordinary condition: no banner, remedy intact
    r2 = A.compound("anxiety", lang="en")
    assert r2.get("safety") is None, "ordinary condition must not raise the crisis banner"
    assert r2.get("compound"), "ordinary condition must still compound a full remedy"


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
