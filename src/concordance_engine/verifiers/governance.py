"""Governance / business / household / education / church verifier.

The existing governance validator scans free text for forbidden keywords
(coercion, exploitation, deception, conflict-of-interest, idolatry,
covenant-breaking, etc.) and applies a negation pass to suppress false
matches. That layer is keyword triage — it cannot replace human judgment
on the substance of a decision.

This verifier adds a structural check: when a packet supplies a
DECISION_PACKET object claiming to be a complete proposal, the verifier
confirms the packet has the parts that a complete RED/FLOOR/WAY/EXECUTION
sheet should have. It does not judge whether each part is correct — only
whether the parts are present and well-formed.

Format expected in DECISION_PACKET:
    {
      "title": str,
      "scope": "adapter" | "mesh" | "canon",
      "red_items": [str, ...],          # forbidden categories evaluated
      "floor_items": [str, ...],        # protective categories evaluated
      "way_path": str,                  # the chosen narrow path
      "execution_steps": [str, ...],
      "witnesses": [str, ...],          # named individuals / roles
      "wait_window_seconds": int,
      "scripture_anchors": [str, ...]   # optional but recommended
    }

Required fields: title, scope, red_items, floor_items, way_path,
execution_steps, witnesses. Optional: wait_window_seconds, scripture_anchors.

A packet missing required fields rejects on structural grounds, not on
content. The engine still runs the keyword scanner over packet text.
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


_REQUIRED_FIELDS = [
    "title", "scope", "red_items", "floor_items",
    "way_path", "execution_steps", "witnesses",
]
_VALID_SCOPES = ("adapter", "mesh", "canon")
_MIN_RED_ITEMS = 1
_MIN_FLOOR_ITEMS = 1
_MIN_WITNESSES = 1
_MIN_EXECUTION_STEPS = 1


def verify_decision_packet_shape(spec: Dict[str, Any]) -> VerifierResult:
    """Structural completeness check for a decision packet."""
    if not isinstance(spec, dict):
        return error("governance.decision_packet_shape",
                     f"DECISION_PACKET must be an object, got {type(spec).__name__}")

    failures: List[str] = []

    for field in _REQUIRED_FIELDS:
        if field not in spec:
            failures.append(f"missing required field: {field}")
            continue
        value = spec[field]
        if value is None or value == "" or value == []:
            failures.append(f"required field is empty: {field}")

    # Scope must be a valid value
    scope = spec.get("scope")
    if scope is not None and scope not in _VALID_SCOPES:
        failures.append(
            f"scope={scope!r} not in {_VALID_SCOPES} — adapter/mesh/canon determine wait window"
        )

    # red_items: at least one forbidden-category check must be declared
    red_items = spec.get("red_items") or []
    if isinstance(red_items, list) and len(red_items) < _MIN_RED_ITEMS:
        failures.append(f"red_items has {len(red_items)}, need at least {_MIN_RED_ITEMS}")
    elif not isinstance(red_items, list):
        failures.append("red_items must be a list of strings")

    # floor_items: at least one protective-category check
    floor_items = spec.get("floor_items") or []
    if isinstance(floor_items, list) and len(floor_items) < _MIN_FLOOR_ITEMS:
        failures.append(f"floor_items has {len(floor_items)}, need at least {_MIN_FLOOR_ITEMS}")
    elif not isinstance(floor_items, list):
        failures.append("floor_items must be a list of strings")

    # witnesses: at least one named witness
    witnesses = spec.get("witnesses") or []
    if isinstance(witnesses, list) and len(witnesses) < _MIN_WITNESSES:
        failures.append(f"witnesses has {len(witnesses)}, need at least {_MIN_WITNESSES}")
    elif not isinstance(witnesses, list):
        failures.append("witnesses must be a list of names or roles")

    # execution_steps: at least one
    steps = spec.get("execution_steps") or []
    if isinstance(steps, list) and len(steps) < _MIN_EXECUTION_STEPS:
        failures.append(f"execution_steps has {len(steps)}, need at least {_MIN_EXECUTION_STEPS}")
    elif not isinstance(steps, list):
        failures.append("execution_steps must be a list of strings")

    # way_path: must be a non-empty string explanation of the chosen path
    way_path = spec.get("way_path")
    if way_path is not None and not isinstance(way_path, str):
        failures.append("way_path must be a string describing the chosen narrow path")
    elif isinstance(way_path, str) and len(way_path.strip()) < 10:
        failures.append("way_path is too short to describe the chosen path "
                        "(state the path in at least one full sentence)")

    if failures:
        return mismatch("governance.decision_packet_shape",
                        "; ".join(failures),
                        {"failures": failures})

    return confirm("governance.decision_packet_shape",
                   f"complete decision packet: {len(red_items)} red, {len(floor_items)} floor, "
                   f"{len(witnesses)} witnesses, {len(steps)} steps, "
                   f"scripture_anchors={'present' if spec.get('scripture_anchors') else 'absent'}",
                   {"red_count": len(red_items), "floor_count": len(floor_items),
                    "witness_count": len(witnesses), "step_count": len(steps),
                    "has_scripture": bool(spec.get("scripture_anchors"))})


def verify_witness_count_consistency(spec: Dict[str, Any], packet: Dict[str, Any]) -> VerifierResult:
    """If both DECISION_PACKET.witnesses and top-level witness_count exist, they must agree."""
    dp_witnesses = spec.get("witnesses")
    top_count = packet.get("witness_count")
    if dp_witnesses is None or top_count is None:
        return na("governance.witness_count_consistency")
    if not isinstance(dp_witnesses, list):
        return error("governance.witness_count_consistency",
                     "DECISION_PACKET.witnesses is not a list")
    n_named = len(dp_witnesses)
    try:
        n_top = int(top_count)
    except (ValueError, TypeError):
        return error("governance.witness_count_consistency",
                     f"witness_count is non-integer: {top_count!r}")
    if n_named == n_top:
        return confirm("governance.witness_count_consistency",
                       f"DECISION_PACKET.witnesses count ({n_named}) matches top-level witness_count")
    return mismatch("governance.witness_count_consistency",
                    f"DECISION_PACKET names {n_named} witnesses but top-level witness_count={n_top}")


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    dp = packet.get("DECISION_PACKET")

    if dp is not None:
        results.append(verify_decision_packet_shape(dp))
        results.append(verify_witness_count_consistency(dp, packet))

    if not results:
        results.append(na("governance", "no DECISION_PACKET artifact present"))
    return results


# ---------------------------------------------------------------------
# V7: per-domain decision-packet profiles
# ---------------------------------------------------------------------

_DOMAIN_PROFILES = {
    "governance": {
        # Already covered by base shape; kept for explicitness.
        "required": [],
        "recommended": ["scripture_anchor"],
    },
    "business": {
        # Officers signing off, fiduciary clarity, dollar amount.
        "required": ["officers", "fiduciary_basis"],
        "recommended": ["dollar_amount", "risk_assessment"],
    },
    "household": {
        # A household decision should name affected dependents, budget category, and time horizon.
        "required": ["budget_category", "affected_dependents"],
        "recommended": ["time_horizon", "alternatives_considered"],
    },
    "education": {
        # Affected students/cohort, learning objective, policy alignment.
        "required": ["affected_cohort", "learning_objective"],
        "recommended": ["accommodation_plan", "policy_reference"],
    },
    "church": {
        # Elder/leader sign-off, scripture anchor, congregation impact.
        "required": ["elder_signoff", "scripture_anchor"],
        "recommended": ["congregation_impact", "prayer_record"],
    },
}


def verify_domain_profile(domain, decision_packet):
    """Verify a decision packet against per-domain required-field profile.

    The base shape check is independent; this layer adds domain semantics.
    """
    domain_key = (domain or "").lower()
    profile = _DOMAIN_PROFILES.get(domain_key)
    if profile is None:
        return na("governance.domain_profile",
                  f"no profile registered for domain {domain!r}")
    if not isinstance(decision_packet, dict):
        return error("governance.domain_profile", "decision_packet must be an object")
    missing_required = [k for k in profile["required"]
                        if k not in decision_packet or decision_packet[k] in (None, "", [], {})]
    missing_recommended = [k for k in profile["recommended"]
                           if k not in decision_packet]
    data = {"domain": domain_key,
            "required": profile["required"],
            "recommended": profile["recommended"],
            "missing_required": missing_required,
            "missing_recommended": missing_recommended}
    if missing_required:
        return mismatch("governance.domain_profile",
                        f"{domain} packet missing required: {missing_required}",
                        data)
    if missing_recommended:
        # Recommended fields are advisory, not blocking. Confirm but flag in detail.
        return confirm("governance.domain_profile",
                       f"{domain} required fields present; recommended missing: {missing_recommended}",
                       data)
    return confirm("governance.domain_profile",
                   f"{domain} required + recommended fields all present", data)
