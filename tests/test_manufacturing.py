"""Tests for the manufacturing verifier."""
from __future__ import annotations

from concordance_engine.verifiers import manufacturing as mfg


# ── sigma level ────────────────────────────────────────────────────────

def test_sigma_level_5_sigma_dpmo():
    # 5σ ↔ 233 DPMO
    r = mfg.verify_sigma_level({"dpmo": 233, "claimed_sigma": 5.0})
    assert r.status == "CONFIRMED"


def test_sigma_level_6_sigma_dpmo():
    r = mfg.verify_sigma_level({"dpmo": 3.4, "claimed_sigma": 6.0})
    assert r.status == "CONFIRMED"


def test_sigma_level_3_sigma_dpmo():
    r = mfg.verify_sigma_level({"dpmo": 66807, "claimed_sigma": 3.0})
    assert r.status == "CONFIRMED"


def test_sigma_level_wrong_claim():
    r = mfg.verify_sigma_level({"dpmo": 233, "claimed_sigma": 3.0})
    assert r.status == "MISMATCH"


def test_sigma_level_negative_dpmo_error():
    r = mfg.verify_sigma_level({"dpmo": -1, "claimed_sigma": 5.0})
    assert r.status == "ERROR"


# ── SPC control limits ─────────────────────────────────────────────────

def test_spc_limits_default_3sigma():
    # mean=100, sigma=2 → UCL=106, LCL=94
    r = mfg.verify_spc_control_limits({
        "mean": 100, "sigma": 2,
        "claimed_ucl": 106, "claimed_lcl": 94,
    })
    assert r.status == "CONFIRMED"


def test_spc_limits_custom_k_2sigma():
    r = mfg.verify_spc_control_limits({
        "mean": 100, "sigma": 2, "k": 2,
        "claimed_ucl": 104, "claimed_lcl": 96,
    })
    assert r.status == "CONFIRMED"


def test_spc_limits_wrong_claim():
    r = mfg.verify_spc_control_limits({
        "mean": 100, "sigma": 2,
        "claimed_ucl": 200, "claimed_lcl": 0,
    })
    assert r.status == "MISMATCH"


def test_spc_limits_zero_sigma_error():
    r = mfg.verify_spc_control_limits({
        "mean": 100, "sigma": 0,
        "claimed_ucl": 100, "claimed_lcl": 100,
    })
    assert r.status == "ERROR"


# ── process capability ────────────────────────────────────────────────

def test_capability_capable_centered_process():
    # USL=110, LSL=90, μ=100, σ=2 → Cp = 20/12 = 1.667, Cpk = 10/6 = 1.667
    # threshold 1.33 → capable
    r = mfg.verify_process_capability({
        "usl": 110, "lsl": 90, "process_mean": 100, "process_sigma": 2,
        "claimed_cp_capable": True,
    })
    assert r.status == "CONFIRMED"


def test_capability_not_capable_off_centered():
    # USL=110, LSL=90, μ=108, σ=2: Cp=1.667 but Cpk=(110-108)/6=0.333
    # → not capable per 1.33 threshold
    r = mfg.verify_process_capability({
        "usl": 110, "lsl": 90, "process_mean": 108, "process_sigma": 2,
        "claimed_cp_capable": False,
    })
    assert r.status == "CONFIRMED"


def test_capability_wrong_claim():
    r = mfg.verify_process_capability({
        "usl": 110, "lsl": 90, "process_mean": 108, "process_sigma": 2,
        "claimed_cp_capable": True,  # wrong; off-centered
    })
    assert r.status == "MISMATCH"


def test_capability_inverted_spec_error():
    r = mfg.verify_process_capability({
        "usl": 90, "lsl": 110, "process_mean": 100, "process_sigma": 2,
        "claimed_cp_capable": False,
    })
    assert r.status == "ERROR"


# ── tolerance stack RSS ────────────────────────────────────────────────

def test_rss_two_tolerances():
    # sqrt(0.01² + 0.02²) = sqrt(0.0005) ≈ 0.02236
    r = mfg.verify_tolerance_stack_rss({
        "tolerances": [0.01, 0.02], "claimed_rss": 0.02236,
    })
    assert r.status == "CONFIRMED"


def test_rss_three_tolerances():
    # sqrt(0.01² + 0.02² + 0.015²) = sqrt(0.000725) ≈ 0.02693
    r = mfg.verify_tolerance_stack_rss({
        "tolerances": [0.01, 0.02, 0.015], "claimed_rss": 0.02693,
    })
    assert r.status == "CONFIRMED"


def test_rss_wrong_claim():
    r = mfg.verify_tolerance_stack_rss({
        "tolerances": [0.01, 0.02], "claimed_rss": 0.5,
    })
    assert r.status == "MISMATCH"


def test_rss_empty_list_error():
    r = mfg.verify_tolerance_stack_rss({
        "tolerances": [], "claimed_rss": 0,
    })
    assert r.status == "ERROR"


def test_rss_negative_tolerance_error():
    r = mfg.verify_tolerance_stack_rss({
        "tolerances": [0.01, -0.01], "claimed_rss": 0.014,
    })
    assert r.status == "ERROR"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = mfg.run({"domain": "manufacturing"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "manufacturing",
        "MFG_VERIFY": {
            "dpmo": 233, "claimed_sigma": 5.0,
            "mean": 100, "sigma": 2, "claimed_ucl": 106, "claimed_lcl": 94,
            "usl": 110, "lsl": 90, "process_mean": 100, "process_sigma": 2,
            "claimed_cp_capable": True,
            "tolerances": [0.01, 0.02], "claimed_rss": 0.02236,
        },
    }
    results = mfg.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 4, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_manufacturing_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "manufacturing",
        "MFG_VERIFY": {"dpmo": 3.4, "claimed_sigma": 6.0},
    }
    results = run_for_domain("manufacturing", packet)
    mfg_results = [r for r in results if r.name.startswith("manufacturing.")]
    assert len(mfg_results) == 1
    assert mfg_results[0].status == "CONFIRMED"
