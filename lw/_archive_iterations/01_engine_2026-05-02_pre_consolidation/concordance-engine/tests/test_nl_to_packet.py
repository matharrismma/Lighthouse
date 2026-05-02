"""Smoke tests for nl_to_packet — deterministic NL→packet templates.

Run with:
    PYTHONPATH=src python -m pytest tests/test_nl_to_packet.py -v
or, without pytest:
    PYTHONPATH=src python tests/test_nl_to_packet.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly: python tests/test_nl_to_packet.py
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from concordance_engine.nl_to_packet import parse  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers

def _expect(text: str, *, domain: str, template: str):
    r = parse(text)
    assert r is not None, f"No parse for: {text!r}"
    assert r.domain == domain, f"Domain mismatch for {text!r}: got {r.domain}, want {domain}"
    assert r.template == template, f"Template mismatch for {text!r}: got {r.template}, want {template}"
    return r


# ---------------------------------------------------------------------------
# Chemistry

def test_chemistry_propane_combustion():
    r = _expect(
        "is C3H8 + 5 O2 -> 3 CO2 + 4 H2O balanced?",
        domain="chemistry",
        template="chem.equation",
    )
    assert r.packet["CHEM_VERIFY"]["equation"] == "C3H8 + 5 O2 -> 3 CO2 + 4 H2O"


def test_chemistry_unicode_arrow():
    r = _expect(
        "balance Cu + 2 HCl → CuCl2 + H2",
        domain="chemistry",
        template="chem.equation",
    )
    assert "Cu + 2 HCl" in r.packet["CHEM_VERIFY"]["equation"]
    assert "CuCl2 + H2" in r.packet["CHEM_VERIFY"]["equation"]


def test_chemistry_with_temperature():
    r = _expect(
        "Fe + Cl2 -> FeCl3 at temperature = 298 K",
        domain="chemistry",
        template="chem.equation",
    )
    assert r.packet["CHEM_VERIFY"]["temperature_K"] == 298.0


# ---------------------------------------------------------------------------
# Statistics

def test_stat_one_sample_t_terse():
    r = _expect(
        "p = 0.282 from a one-sample t-test, n=30, mean=5.2, sd=1.0, mu0=5.0",
        domain="statistics",
        template="stat.one_sample_t",
    )
    sv = r.packet["STAT_VERIFY"]
    assert sv["test"] == "one_sample_t"
    assert sv["n"] == 30
    assert sv["mean"] == 5.2
    assert sv["sd"] == 1.0
    assert sv["mu0"] == 5.0
    assert sv["claimed_p"] == 0.282
    assert sv["tail"] == "two-sided"


def test_stat_one_sided():
    r = _expect(
        "t-test (one-sided): n=12, mean=4.7, sd=0.8, mu0=5, p-value 0.21",
        domain="statistics",
        template="stat.one_sample_t",
    )
    assert r.packet["STAT_VERIFY"]["tail"] == "one-sided"


def test_stat_missing_field_returns_none():
    # Missing sd
    assert parse("t-test n=30 mean=5 mu0=5 p=0.1") is None


# ---------------------------------------------------------------------------
# Physics

def test_physics_dimensional_basic():
    r = _expect(
        "F = m * a where F in N, m in kg, a in m/s^2",
        domain="physics",
        template="phys.dimensional",
    )
    pv = r.packet["PHYS_VERIFY"]
    assert "F" in pv["units"]
    assert "m" in pv["units"]
    assert "a" in pv["units"]
    assert pv["units"]["F"].lower().startswith("n")


# ---------------------------------------------------------------------------
# Mathematics

def test_math_derivative():
    r = _expect(
        "d/dx(x^2) = 2x",
        domain="mathematics",
        template="math.derivative",
    )
    d = r.packet["MATH_VERIFY"]["derivative"]
    assert d["function"] == "x^2"
    assert d["variable"] == "x"
    assert d["claimed"] == "2x"


def test_math_equality_simplification():
    r = _expect(
        "x^2 + 2x + 1 simplifies to (x+1)^2",
        domain="mathematics",
        template="math.equality",
    )
    eq = r.packet["MATH_VERIFY"]["equality"]
    assert "x^2" in eq["left"]
    assert "(x+1)^2" in eq["right"]


# ---------------------------------------------------------------------------
# Computer science

def test_cs_complexity():
    r = _expect(
        "binary search is O(log n)",
        domain="computer_science",
        template="cs.complexity",
    )
    assert r.packet["CS_VERIFY"]["complexity"]["claimed"] == "O(log n)"


# ---------------------------------------------------------------------------
# No match

def test_no_match_returns_none():
    assert parse("Hello, what is the meaning of life?") is None
    assert parse("") is None
    assert parse(None) is None  # type: ignore


# ---------------------------------------------------------------------------
# CLI runner

if __name__ == "__main__":
    import inspect
    failures = []
    tests = [(n, fn) for n, fn in globals().items() if n.startswith("test_") and callable(fn)]
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            failures.append(name)
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            failures.append(name)
    print()
    print(f"{len(tests) - len(failures)}/{len(tests)} passed")
    sys.exit(1 if failures else 0)
