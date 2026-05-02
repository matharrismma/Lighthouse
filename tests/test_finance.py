"""Tests for the finance verifier."""
from __future__ import annotations

from concordance_engine.verifiers import finance as fin


# ── accounting identity ────────────────────────────────────────────────

def test_accounting_balanced():
    r = fin.verify_accounting_identity({
        "assets": 1000, "liabilities": 600, "equity": 400,
    })
    assert r.status == "CONFIRMED"


def test_accounting_unbalanced_caught():
    r = fin.verify_accounting_identity({
        "assets": 1000, "liabilities": 600, "equity": 500,
    })
    assert r.status == "MISMATCH"


def test_accounting_floating_point_within_tolerance():
    r = fin.verify_accounting_identity({
        "assets": 1000.001, "liabilities": 600, "equity": 400,
    })
    assert r.status == "CONFIRMED"


def test_accounting_non_numeric_error():
    r = fin.verify_accounting_identity({
        "assets": "lots", "liabilities": 600, "equity": 400,
    })
    assert r.status == "ERROR"


# ── compound interest ──────────────────────────────────────────────────

def test_compound_interest_annual_compounding_5pct_10yrs():
    # 1000 * (1.05)^10 ≈ 1628.89
    r = fin.verify_compound_interest({
        "principal": 1000, "rate": 0.05, "years": 10,
        "compounding_per_year": 1, "claimed_future_value": 1628.89,
    })
    assert r.status == "CONFIRMED"


def test_compound_interest_monthly_compounding():
    # 1000 * (1 + 0.05/12)^120 ≈ 1647.0095
    r = fin.verify_compound_interest({
        "principal": 1000, "rate": 0.05, "years": 10,
        "compounding_per_year": 12, "claimed_future_value": 1647.0095,
    })
    assert r.status == "CONFIRMED"


def test_compound_interest_wrong_claim():
    r = fin.verify_compound_interest({
        "principal": 1000, "rate": 0.05, "years": 10,
        "compounding_per_year": 1, "claimed_future_value": 5000,
    })
    assert r.status == "MISMATCH"


def test_compound_interest_negative_principal_error():
    r = fin.verify_compound_interest({
        "principal": -1000, "rate": 0.05, "years": 10,
        "claimed_future_value": -1628.89,
    })
    assert r.status == "ERROR"


# ── NPV ────────────────────────────────────────────────────────────────

def test_npv_simple_project():
    # CF=[-1000, 300, 400, 500, 200], r=0.10
    # NPV = -1000 + 300/1.1 + 400/1.21 + 500/1.331 + 200/1.4641
    #     ≈ -1000 + 272.73 + 330.58 + 375.66 + 136.60 = 115.57
    r = fin.verify_npv({
        "cashflows": [-1000, 300, 400, 500, 200],
        "discount_rate": 0.10,
        "claimed_npv": 115.57,
    })
    assert r.status == "CONFIRMED"


def test_npv_zero_rate_is_simple_sum():
    r = fin.verify_npv({
        "cashflows": [-100, 50, 50, 50],
        "discount_rate": 0.0,
        "claimed_npv": 50,  # -100+50+50+50 = 50
    })
    assert r.status == "CONFIRMED"


def test_npv_wrong_claim_caught():
    r = fin.verify_npv({
        "cashflows": [-1000, 300, 400, 500, 200],
        "discount_rate": 0.10, "claimed_npv": 0,
    })
    assert r.status == "MISMATCH"


def test_npv_empty_cashflows_error():
    r = fin.verify_npv({"cashflows": [], "discount_rate": 0.05, "claimed_npv": 0})
    assert r.status == "ERROR"


def test_npv_invalid_rate_error():
    r = fin.verify_npv({
        "cashflows": [-100, 50], "discount_rate": -2.0, "claimed_npv": 0,
    })
    assert r.status == "ERROR"


# ── present value ──────────────────────────────────────────────────────

def test_pv_basic_one_period():
    # PV = 1100 / 1.10 = 1000
    r = fin.verify_present_value({
        "future_value": 1100, "pv_discount_rate": 0.10, "pv_periods": 1,
        "claimed_present_value": 1000,
    })
    assert r.status == "CONFIRMED"


def test_pv_multi_period():
    # PV = 1000 / 1.05^5 ≈ 783.526
    r = fin.verify_present_value({
        "future_value": 1000, "pv_discount_rate": 0.05, "pv_periods": 5,
        "claimed_present_value": 783.526,
    })
    assert r.status == "CONFIRMED"


def test_pv_wrong_claim():
    r = fin.verify_present_value({
        "future_value": 1100, "pv_discount_rate": 0.10, "pv_periods": 1,
        "claimed_present_value": 1100,
    })
    assert r.status == "MISMATCH"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = fin.run({"domain": "finance"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "finance",
        "FIN_VERIFY": {
            "assets": 1000, "liabilities": 600, "equity": 400,
            "principal": 1000, "rate": 0.05, "years": 10,
            "compounding_per_year": 1, "claimed_future_value": 1628.89,
            "cashflows": [-1000, 300, 400, 500, 200],
            "discount_rate": 0.10, "claimed_npv": 115.57,
            "future_value": 1100, "pv_discount_rate": 0.10,
            "pv_periods": 1, "claimed_present_value": 1000,
        },
    }
    results = fin.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 4, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_finance_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "finance",
        "FIN_VERIFY": {"assets": 1000, "liabilities": 600, "equity": 400},
    }
    results = run_for_domain("finance", packet)
    fin_results = [r for r in results if r.name.startswith("finance.")]
    assert len(fin_results) == 1
    assert fin_results[0].status == "CONFIRMED"
