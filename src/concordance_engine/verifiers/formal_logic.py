"""Formal Logic verifier.

Deterministic checks of propositional-logic claims against SymPy's
satisfiability solver. The five canonical predicate-logic questions
are decidable mechanically; this verifier wraps that decision into
the engine's CONFIRMED / MISMATCH / NA / ERROR shape.

Why SymPy and not Z3: SymPy is already a hard dependency of the
mathematics verifier, and propositional satisfiability is well within
its `sympy.logic.boolalg` capabilities. SMT-grade (first-order with
theories) is a future addition; for V1 the propositional fragment
covers the Z3/SymPy slot in the BIBLE P1 punch list.

Checks performed:

  * formal_logic.satisfiability
      formula has a satisfying assignment (or doesn't), matches claim.
  * formal_logic.tautology
      formula is true under every assignment (¬formula is unsat).
  * formal_logic.contradiction
      formula is false under every assignment (formula itself is unsat).
  * formal_logic.entailment
      premises ⊨ conclusion ⟺ premises ∧ ¬conclusion is unsat.
  * formal_logic.equivalence
      formula_a ≡ formula_b ⟺ ¬(formula_a ↔ formula_b) is unsat.

Formula syntax (Python-flavored Boolean operators, parsed by SymPy):
  &   = AND
  |   = OR
  ~   = NOT
  >>  = implies (p >> q)
  Equivalent(p, q) for biconditional, or use ~(p ^ q)

LOGIC_VERIFY packet shape (any subset of fields):
    {
      "variables": ["p", "q", "r"],          # propositional symbol names
      "formula": "p & q",                    # satisfiability/tautology/contradiction
      "claimed_satisfiable": true,
      "claimed_tautology": false,
      "claimed_contradiction": false,
      "premises": ["p", "p >> q"],           # entailment
      "conclusion": "q",
      "claimed_entailment": true,
      "formula_a": "p | q",                  # equivalence
      "formula_b": "~(~p & ~q)",
      "claimed_equivalent": true,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .base import VerifierResult, na, confirm, mismatch, error


# Lazy-import sympy at call time so the module loads even in stripped envs.
def _parse(formula: str, var_names: List[str]):
    """Parse a Boolean formula string into a SymPy expression."""
    import sympy
    from sympy.logic.boolalg import (
        And, Or, Not, Implies, Equivalent, Xor, true as Sym_True, false as Sym_False
    )
    locals_ = {n: sympy.symbols(n) for n in (var_names or [])}
    locals_.update({
        "Implies": Implies, "Equivalent": Equivalent,
        "And": And, "Or": Or, "Not": Not, "Xor": Xor,
        "true": Sym_True, "false": Sym_False,
        "True": Sym_True, "False": Sym_False,
    })
    return sympy.sympify(formula, locals=locals_)


def _satisfiable(expr) -> bool:
    """True iff there's a model. Wraps sympy.logic.inference.satisfiable."""
    from sympy.logic.inference import satisfiable
    result = satisfiable(expr)
    return result is not False


# Same kind of parse-error tuple as the math verifier uses.
def _parse_errors():
    from sympy.core.sympify import SympifyError
    return (SympifyError, SyntaxError, TypeError, ValueError, NotImplementedError)


def verify_satisfiability(spec: Dict[str, Any]) -> VerifierResult:
    name = "formal_logic.satisfiability"
    formula = spec.get("formula")
    claimed = spec.get("claimed_satisfiable")
    if formula is None or claimed is None:
        return na(name)
    var_names = spec.get("variables") or []
    try:
        expr = _parse(formula, var_names)
        actual = _satisfiable(expr)
    except _parse_errors() as e:
        return na(name, f"cannot parse formula: {e}")
    except Exception as e:
        return error(name, f"computation failure: {type(e).__name__}: {e}")
    claimed_b = bool(claimed)
    if actual == claimed_b:
        return confirm(name,
                       f"formula {formula!r} satisfiable={actual}, matches claim",
                       {"formula": formula, "actual": actual, "claimed": claimed_b})
    return mismatch(name,
                    f"formula {formula!r} satisfiable={actual}, claimed {claimed_b}",
                    {"formula": formula, "actual": actual, "claimed": claimed_b})


def verify_tautology(spec: Dict[str, Any]) -> VerifierResult:
    name = "formal_logic.tautology"
    formula = spec.get("formula")
    claimed = spec.get("claimed_tautology")
    if formula is None or claimed is None:
        return na(name)
    var_names = spec.get("variables") or []
    try:
        from sympy.logic.boolalg import Not
        expr = _parse(formula, var_names)
        # tautology iff Not(expr) is unsatisfiable.
        is_taut = not _satisfiable(Not(expr))
    except _parse_errors() as e:
        return na(name, f"cannot parse formula: {e}")
    except Exception as e:
        return error(name, f"computation failure: {type(e).__name__}: {e}")
    claimed_b = bool(claimed)
    if is_taut == claimed_b:
        return confirm(name,
                       f"formula {formula!r} tautology={is_taut}, matches claim",
                       {"formula": formula, "actual": is_taut, "claimed": claimed_b})
    return mismatch(name,
                    f"formula {formula!r} tautology={is_taut}, claimed {claimed_b}",
                    {"formula": formula, "actual": is_taut, "claimed": claimed_b})


def verify_contradiction(spec: Dict[str, Any]) -> VerifierResult:
    name = "formal_logic.contradiction"
    formula = spec.get("formula")
    claimed = spec.get("claimed_contradiction")
    if formula is None or claimed is None:
        return na(name)
    var_names = spec.get("variables") or []
    try:
        expr = _parse(formula, var_names)
        is_contradiction = not _satisfiable(expr)
    except _parse_errors() as e:
        return na(name, f"cannot parse formula: {e}")
    except Exception as e:
        return error(name, f"computation failure: {type(e).__name__}: {e}")
    claimed_b = bool(claimed)
    if is_contradiction == claimed_b:
        return confirm(name,
                       f"formula {formula!r} contradiction={is_contradiction}, matches claim",
                       {"formula": formula, "actual": is_contradiction, "claimed": claimed_b})
    return mismatch(name,
                    f"formula {formula!r} contradiction={is_contradiction}, claimed {claimed_b}",
                    {"formula": formula, "actual": is_contradiction, "claimed": claimed_b})


def verify_entailment(spec: Dict[str, Any]) -> VerifierResult:
    name = "formal_logic.entailment"
    premises = spec.get("premises")
    conclusion = spec.get("conclusion")
    claimed = spec.get("claimed_entailment")
    if not premises or conclusion is None or claimed is None:
        return na(name)
    var_names = spec.get("variables") or []
    try:
        from sympy.logic.boolalg import And, Not
        prem_exprs = [_parse(str(p), var_names) for p in premises]
        conc_expr = _parse(str(conclusion), var_names)
        # premises ⊨ conclusion iff (And(premises) ∧ ¬conclusion) is unsat.
        check = And(And(*prem_exprs), Not(conc_expr))
        entails = not _satisfiable(check)
    except _parse_errors() as e:
        return na(name, f"cannot parse formula: {e}")
    except Exception as e:
        return error(name, f"computation failure: {type(e).__name__}: {e}")
    claimed_b = bool(claimed)
    if entails == claimed_b:
        return confirm(name,
                       f"premises ⊨ conclusion = {entails}, matches claim",
                       {"premises": list(premises), "conclusion": conclusion,
                        "actual": entails, "claimed": claimed_b})
    return mismatch(name,
                    f"premises ⊨ conclusion = {entails}, claimed {claimed_b}",
                    {"premises": list(premises), "conclusion": conclusion,
                     "actual": entails, "claimed": claimed_b})


def verify_equivalence(spec: Dict[str, Any]) -> VerifierResult:
    name = "formal_logic.equivalence"
    a = spec.get("formula_a")
    b = spec.get("formula_b")
    claimed = spec.get("claimed_equivalent")
    if a is None or b is None or claimed is None:
        return na(name)
    var_names = spec.get("variables") or []
    try:
        from sympy.logic.boolalg import Equivalent, Not
        ea = _parse(a, var_names)
        eb = _parse(b, var_names)
        # ea ≡ eb iff ¬(ea ↔ eb) is unsat.
        is_equiv = not _satisfiable(Not(Equivalent(ea, eb)))
    except _parse_errors() as e:
        return na(name, f"cannot parse formula: {e}")
    except Exception as e:
        return error(name, f"computation failure: {type(e).__name__}: {e}")
    claimed_b = bool(claimed)
    if is_equiv == claimed_b:
        return confirm(name,
                       f"{a!r} ≡ {b!r} = {is_equiv}, matches claim",
                       {"a": a, "b": b, "actual": is_equiv, "claimed": claimed_b})
    return mismatch(name,
                    f"{a!r} ≡ {b!r} = {is_equiv}, claimed {claimed_b}",
                    {"a": a, "b": b, "actual": is_equiv, "claimed": claimed_b})


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch every applicable formal-logic check for the LOGIC_VERIFY block."""
    results: List[VerifierResult] = []
    lv = packet.get("LOGIC_VERIFY") or {}

    has_formula = "formula" in lv
    if has_formula and "claimed_satisfiable" in lv:
        results.append(verify_satisfiability(lv))
    if has_formula and "claimed_tautology" in lv:
        results.append(verify_tautology(lv))
    if has_formula and "claimed_contradiction" in lv:
        results.append(verify_contradiction(lv))
    if "premises" in lv and "conclusion" in lv and "claimed_entailment" in lv:
        results.append(verify_entailment(lv))
    if "formula_a" in lv and "formula_b" in lv and "claimed_equivalent" in lv:
        results.append(verify_equivalence(lv))

    if not results:
        results.append(na("formal_logic", "no LOGIC_VERIFY artifacts present"))
    return results
