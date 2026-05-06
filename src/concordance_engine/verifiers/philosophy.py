"""Philosophy verifier (grid axes: reasoning/information/authority-trust).

Deterministic checks on modal logic, ethical framework classification,
epistemic claim type, and Leibniz's identity principle. All criteria are
drawn from standard analytic philosophy (public-domain).

Checks:
  * philosophy.modal_logic_validity  — K-axiom: necessity implies possibility
  * philosophy.ethical_framework     — deontological / consequentialist / virtue_ethics / contractarian
  * philosophy.epistemic_claim_type  — a priori vs. a posteriori
  * philosophy.identity_principle    — Leibniz's law: identical iff same property set

PHIL_VERIFY packet shape (any subset):
    {
      "is_necessarily_true": true,
      "is_possibly_true": true,
      "claimed_consistent": true,

      "framework_name": "consequentialist",
      "claimed_focuses_on_outcomes": true,

      "claim_requires_observation": false,
      "claimed_is_a_priori": true,

      "object_a_properties": ["red", "round", "heavy"],
      "object_b_properties": ["round", "red", "heavy"],
      "claimed_are_identical": true,
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Set

from .base import VerifierResult, na, confirm, mismatch, error


# ---------------------------------------------------------------------------
# Modal logic — K axiom consistency check
# ---------------------------------------------------------------------------

def verify_modal_logic_validity(spec: Dict[str, Any]) -> VerifierResult:
    """K axiom: □P → ◇P  (necessarily-true ⟹ possibly-true).

    A set of modal claims is *consistent* iff it does not assert both
    □P = True and ◇P = False simultaneously.
    """
    name = "philosophy.modal_logic_validity"
    is_nec = spec.get("is_necessarily_true")
    is_pos = spec.get("is_possibly_true")
    claimed = spec.get("claimed_consistent")
    if any(v is None for v in (is_nec, is_pos, claimed)):
        return na(name)

    nec = bool(is_nec)
    pos = bool(is_pos)
    # Inconsistent iff □P and ¬◇P simultaneously.
    actual_consistent = not (nec and not pos)
    claimed_b = bool(claimed)

    data = {
        "is_necessarily_true": nec,
        "is_possibly_true":    pos,
        "actual_consistent":   actual_consistent,
        "claimed_consistent":  claimed_b,
        "rule": "K axiom: if □P then ◇P must hold; □P ∧ ¬◇P is a modal contradiction",
    }
    if actual_consistent == claimed_b:
        return confirm(
            name,
            f"modal claims consistent={actual_consistent} (matches claim)",
            data,
        )
    return mismatch(
        name,
        f"modal claims consistent={actual_consistent}, claimed {claimed_b}",
        data,
    )


# ---------------------------------------------------------------------------
# Ethical framework classification
# ---------------------------------------------------------------------------

# framework → (focuses_on_outcomes, definition)
_FRAMEWORKS: Dict[str, tuple] = {
    "deontological": (
        False,
        "Moral worth of an action is determined by rules/duties, not consequences",
    ),
    "consequentialist": (
        True,
        "Moral worth of an action is determined solely by its outcomes/consequences",
    ),
    "virtue_ethics": (
        False,
        "Moral worth is determined by the character and virtues of the agent",
    ),
    "contractarian": (
        False,
        "Moral principles are grounded in hypothetical social contracts among rational agents",
    ),
}

def verify_ethical_framework(spec: Dict[str, Any]) -> VerifierResult:
    """Check whether a named ethical framework focuses on outcomes."""
    name = "philosophy.ethical_framework"
    fw_name = spec.get("framework_name")
    claimed = spec.get("claimed_focuses_on_outcomes")
    if fw_name is None or claimed is None:
        return na(name)

    key = str(fw_name).strip().lower()
    entry = _FRAMEWORKS.get(key)
    if entry is None:
        return na(name, f"framework {fw_name!r} not in known catalogue "
                        f"(known: {', '.join(_FRAMEWORKS)})")

    actual_focuses, definition = entry
    claimed_b = bool(claimed)
    data = {
        "framework_name":            fw_name,
        "definition":                definition,
        "actual_focuses_on_outcomes":  actual_focuses,
        "claimed_focuses_on_outcomes": claimed_b,
        "rule": "Only consequentialism primarily evaluates actions by their outcomes",
    }
    if actual_focuses == claimed_b:
        return confirm(
            name,
            f"{fw_name!r} focuses_on_outcomes={actual_focuses} (matches claim)",
            data,
        )
    return mismatch(
        name,
        f"{fw_name!r} focuses_on_outcomes={actual_focuses}, claimed {claimed_b}",
        data,
    )


# ---------------------------------------------------------------------------
# Epistemic claim type — a priori vs. a posteriori
# ---------------------------------------------------------------------------

def verify_epistemic_claim_type(spec: Dict[str, Any]) -> VerifierResult:
    """A priori claims are knowable by reason alone; a posteriori require observation."""
    name = "philosophy.epistemic_claim_type"
    requires_obs = spec.get("claim_requires_observation")
    claimed      = spec.get("claimed_is_a_priori")
    if requires_obs is None or claimed is None:
        return na(name)

    obs = bool(requires_obs)
    actual_a_priori = not obs
    claimed_b = bool(claimed)

    data = {
        "claim_requires_observation": obs,
        "actual_is_a_priori":  actual_a_priori,
        "claimed_is_a_priori": claimed_b,
        "rule": "a priori = knowable by reason alone (no observation required); "
                "a posteriori = requires empirical observation",
    }
    if actual_a_priori == claimed_b:
        kind = "a priori" if actual_a_priori else "a posteriori"
        return confirm(name, f"claim is {kind} (matches claim)", data)
    actual_kind = "a priori" if actual_a_priori else "a posteriori"
    return mismatch(
        name,
        f"claim is {actual_kind}, claimed {'a priori' if claimed_b else 'a posteriori'}",
        data,
    )


# ---------------------------------------------------------------------------
# Leibniz's identity principle
# ---------------------------------------------------------------------------

def verify_identity_principle(spec: Dict[str, Any]) -> VerifierResult:
    """Leibniz's law: A = B iff they share all properties (same property set)."""
    name = "philosophy.identity_principle"
    props_a = spec.get("object_a_properties")
    props_b = spec.get("object_b_properties")
    claimed = spec.get("claimed_are_identical")
    if props_a is None or props_b is None or claimed is None:
        return na(name)

    if not isinstance(props_a, list) or not isinstance(props_b, list):
        return error(name, "object_a_properties and object_b_properties must be lists of strings")

    set_a: Set[str] = {str(p).strip().lower() for p in props_a}
    set_b: Set[str] = {str(p).strip().lower() for p in props_b}
    actual_identical = (set_a == set_b)
    claimed_b = bool(claimed)

    only_in_a = sorted(set_a - set_b)
    only_in_b = sorted(set_b - set_a)

    data = {
        "object_a_properties": list(props_a),
        "object_b_properties": list(props_b),
        "set_a":               sorted(set_a),
        "set_b":               sorted(set_b),
        "only_in_a":           only_in_a,
        "only_in_b":           only_in_b,
        "actual_are_identical":  actual_identical,
        "claimed_are_identical": claimed_b,
        "rule": "Leibniz's law: ∀F(Fa ↔ Fb) ⟹ a = b; identical iff property sets are equal",
    }
    if actual_identical == claimed_b:
        return confirm(
            name,
            f"are_identical={actual_identical} (matches claim)",
            data,
        )
    detail = f"are_identical={actual_identical}, claimed {claimed_b}"
    if only_in_a:
        detail += f"; properties only in A: {only_in_a}"
    if only_in_b:
        detail += f"; properties only in B: {only_in_b}"
    return mismatch(name, detail, data)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch all applicable philosophy checks for the PHIL_VERIFY block."""
    results: List[VerifierResult] = []
    pv = packet.get("PHIL_VERIFY") or {}

    if ("is_necessarily_true" in pv and "is_possibly_true" in pv
            and "claimed_consistent" in pv):
        results.append(verify_modal_logic_validity(pv))

    if "framework_name" in pv and "claimed_focuses_on_outcomes" in pv:
        results.append(verify_ethical_framework(pv))

    if "claim_requires_observation" in pv and "claimed_is_a_priori" in pv:
        results.append(verify_epistemic_claim_type(pv))

    if ("object_a_properties" in pv and "object_b_properties" in pv
            and "claimed_are_identical" in pv):
        results.append(verify_identity_principle(pv))

    if not results:
        results.append(na("philosophy", "no PHIL_VERIFY artifacts present"))
    return results
