"""The 7 domain verifiers the MCP was missing -- now exposed, and held to the guarantee.

atomic, molecular_geometry, periodic_table, probability, physical_constants,
linear_algebra, ephemeris each had a tested verifier MODULE but no MCP `verify_*` tool, so
agents could not reach them. They are wired now (tools.verify_X -> module.run with the
right artifact key). This pins the same cardinal guarantee on them: a true claim CONFIRMS,
a false claim is NEVER confirmed. Offline; no network, no oracle.

Run: PYTHONPATH=src python -m pytest tests/test_mcp_domain_catchup.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from concordance_engine.mcp_server import tools as T  # noqa: E402

# domain -> (verify fn name, TRUE spec, deliberately-FALSE spec)
CASES = {
    "atomic": ("verify_atomic",
               {"atomic_number": 6, "claimed_configuration": "1s2 2s2 2p2"},
               {"atomic_number": 6, "claimed_configuration": "1s2 2s2 2p4"}),
    "molecular_geometry": ("verify_molecular_geometry",
               {"bonding_domains": 4, "lone_pairs": 0, "claimed_geometry": "tetrahedral", "claimed_bond_angle_deg": 109.47},
               {"bonding_domains": 4, "lone_pairs": 0, "claimed_geometry": "octahedral", "claimed_bond_angle_deg": 109.47}),
    "periodic_table": ("verify_periodic_table",
               {"symbol": "O", "claimed_atomic_number": 8},
               {"symbol": "O", "claimed_atomic_number": 9}),
    "probability": ("verify_probability",
               {"outcomes": [1, 2, 3, 4, 5, 6], "probabilities": [1 / 6] * 6, "claimed_expected_value": 3.5},
               {"outcomes": [1, 2, 3, 4, 5, 6], "probabilities": [1 / 6] * 6, "claimed_expected_value": 4.0}),
    "physical_constants": ("verify_physical_constants",
               {"constant": "speed_of_light", "claimed_value": 299792458, "claimed_unit": "m/s"},
               {"constant": "speed_of_light", "claimed_value": 3.5e8, "claimed_unit": "m/s"}),
    "linear_algebra": ("verify_linear_algebra",
               {"vec_a": [1, 2, 3], "vec_b": [4, 5, 6], "claimed_dot_product": 32},
               {"vec_a": [1, 2, 3], "vec_b": [4, 5, 6], "claimed_dot_product": 30}),
    "ephemeris": ("verify_ephemeris",
               {"iso_date": "2024-06-20", "claimed_julian_day": 2460481.5},
               {"iso_date": "2024-06-20", "claimed_julian_day": 2460400}),
}


def _status(result):
    checks = result.get("checks", []) if isinstance(result, dict) else []
    return checks[0].get("status") if checks else "NA"


def test_true_claims_confirm():
    for domain, (fn, true_spec, _f) in CASES.items():
        st = _status(getattr(T, fn)(true_spec))
        assert st == "CONFIRMED", f"{domain}: true claim returned {st}, expected CONFIRMED"


def test_false_claims_never_confirm():
    """THE CARDINAL GUARANTEE, on the newly-exposed domains."""
    for domain, (fn, _t, false_spec) in CASES.items():
        st = _status(getattr(T, fn)(false_spec))
        assert st != "CONFIRMED", f"{domain}: a FALSE claim was CONFIRMED -- a false positive!"


def test_all_seven_are_exposed_as_mcp_tools():
    from concordance_engine.mcp_server.server import mcp
    td = mcp._tool_manager._tools
    for domain in CASES:
        assert ("verify_" + domain) in td, f"verify_{domain} not exposed as an MCP tool"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn(); print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1; print("FAIL", fn.__name__); traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed | {len(CASES)} newly-exposed domains")
    sys.exit(1 if failed else 0)
