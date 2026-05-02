"""Tests for the formal_logic verifier."""
from __future__ import annotations

from concordance_engine.verifiers import formal_logic as fl


# ── satisfiability ─────────────────────────────────────────────────────

def test_satisfiable_simple_conjunction():
    r = fl.verify_satisfiability({
        "variables": ["p", "q"],
        "formula": "p & q",
        "claimed_satisfiable": True,
    })
    assert r.status == "CONFIRMED"


def test_satisfiable_unsatisfiable_claimed_correctly():
    r = fl.verify_satisfiability({
        "variables": ["p"],
        "formula": "p & ~p",
        "claimed_satisfiable": False,
    })
    assert r.status == "CONFIRMED"


def test_satisfiable_wrong_claim():
    r = fl.verify_satisfiability({
        "variables": ["p"],
        "formula": "p & ~p",
        "claimed_satisfiable": True,
    })
    assert r.status == "MISMATCH"


def test_satisfiable_invalid_formula_is_na():
    r = fl.verify_satisfiability({
        "variables": ["p"],
        "formula": "this is not a formula",
        "claimed_satisfiable": True,
    })
    assert r.status == "NOT_APPLICABLE"  # parse failure → abstain


# ── tautology ──────────────────────────────────────────────────────────

def test_tautology_law_of_excluded_middle():
    r = fl.verify_tautology({
        "variables": ["p"],
        "formula": "p | ~p",
        "claimed_tautology": True,
    })
    assert r.status == "CONFIRMED"


def test_tautology_de_morgan_via_equivalence_form():
    # ~(p & q) ≡ (~p | ~q) — but as a single formula:
    # ~(p & q) | ~(~p | ~q) is equivalent to True (tautology)
    r = fl.verify_tautology({
        "variables": ["p", "q"],
        "formula": "Equivalent(~(p & q), ~p | ~q)",
        "claimed_tautology": True,
    })
    assert r.status == "CONFIRMED"


def test_tautology_non_tautology_caught():
    r = fl.verify_tautology({
        "variables": ["p", "q"],
        "formula": "p & q",
        "claimed_tautology": True,
    })
    assert r.status == "MISMATCH"


# ── contradiction ──────────────────────────────────────────────────────

def test_contradiction_correctly_claimed():
    r = fl.verify_contradiction({
        "variables": ["p"],
        "formula": "p & ~p",
        "claimed_contradiction": True,
    })
    assert r.status == "CONFIRMED"


def test_contradiction_satisfiable_formula_not_contradiction():
    r = fl.verify_contradiction({
        "variables": ["p", "q"],
        "formula": "p | q",
        "claimed_contradiction": False,
    })
    assert r.status == "CONFIRMED"


def test_contradiction_wrong_claim():
    r = fl.verify_contradiction({
        "variables": ["p", "q"],
        "formula": "p | q",
        "claimed_contradiction": True,
    })
    assert r.status == "MISMATCH"


# ── entailment ─────────────────────────────────────────────────────────

def test_entailment_modus_ponens():
    # {p, p->q} ⊨ q
    r = fl.verify_entailment({
        "variables": ["p", "q"],
        "premises": ["p", "Implies(p, q)"],
        "conclusion": "q",
        "claimed_entailment": True,
    })
    assert r.status == "CONFIRMED"


def test_entailment_modus_tollens():
    # {p->q, ~q} ⊨ ~p
    r = fl.verify_entailment({
        "variables": ["p", "q"],
        "premises": ["Implies(p, q)", "~q"],
        "conclusion": "~p",
        "claimed_entailment": True,
    })
    assert r.status == "CONFIRMED"


def test_entailment_invalid_argument_caught():
    # {p, q} does NOT entail (p & ~q)
    r = fl.verify_entailment({
        "variables": ["p", "q"],
        "premises": ["p", "q"],
        "conclusion": "p & ~q",
        "claimed_entailment": True,
    })
    assert r.status == "MISMATCH"


def test_entailment_correctly_claims_invalid():
    # {p, q} does NOT entail r — claim is False, actual False, agree
    r = fl.verify_entailment({
        "variables": ["p", "q", "r"],
        "premises": ["p", "q"],
        "conclusion": "r",
        "claimed_entailment": False,
    })
    assert r.status == "CONFIRMED"


# ── equivalence ────────────────────────────────────────────────────────

def test_equivalence_de_morgan():
    # ~(p & q) ≡ (~p | ~q)
    r = fl.verify_equivalence({
        "variables": ["p", "q"],
        "formula_a": "~(p & q)",
        "formula_b": "~p | ~q",
        "claimed_equivalent": True,
    })
    assert r.status == "CONFIRMED"


def test_equivalence_distinct_formulas_not_equivalent():
    r = fl.verify_equivalence({
        "variables": ["p", "q"],
        "formula_a": "p & q",
        "formula_b": "p | q",
        "claimed_equivalent": True,
    })
    assert r.status == "MISMATCH"


def test_equivalence_correctly_distinct():
    r = fl.verify_equivalence({
        "variables": ["p", "q"],
        "formula_a": "p & q",
        "formula_b": "p | q",
        "claimed_equivalent": False,
    })
    assert r.status == "CONFIRMED"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = fl.run({"domain": "formal_logic"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    packet = {
        "domain": "formal_logic",
        "LOGIC_VERIFY": {
            "variables": ["p", "q"],
            "formula": "p | ~p",
            "claimed_satisfiable": True,
            "claimed_tautology": True,
            "claimed_contradiction": False,
            "premises": ["p", "Implies(p, q)"],
            "conclusion": "q",
            "claimed_entailment": True,
            "formula_a": "~(p & q)",
            "formula_b": "~p | ~q",
            "claimed_equivalent": True,
        },
    }
    results = fl.run(packet)
    statuses = [(r.name, r.status) for r in results]
    # 5 checks dispatched
    assert len(results) == 5, statuses
    confirmed = [s for (_, s) in statuses if s == "CONFIRMED"]
    assert len(confirmed) == 5, statuses


def test_engine_dispatches_formal_logic_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "formal_logic",
        "LOGIC_VERIFY": {
            "variables": ["p"],
            "formula": "p | ~p",
            "claimed_tautology": True,
        },
    }
    results = run_for_domain("formal_logic", packet)
    fl_results = [r for r in results if r.name.startswith("formal_logic.")]
    assert len(fl_results) == 1
    assert fl_results[0].status == "CONFIRMED"
