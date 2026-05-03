"""Witness verifier — the 36th axis. Key to the gate.

This is not a peer to the other 35 axes. The other 35 verify *claims*;
witness verifies *the testimony that the gates and verifiers produced
about those claims*. It runs on the assembled result object, not on the
domain content.

Without witness, gate verdicts are internal state. With witness, they
become a record safe to publish — to an agent who parses it, or to a
human who reads it. Same purpose, two surfaces.

Checks (four, matching the cadence of the other axes):
  * witness.gate_chain_complete    — RED, FLOOR, BROTHERS, GOD all
                                      have a verdict (or are explicitly
                                      short-circuited by an earlier
                                      REJECT/QUARANTINE)
  * witness.reasoning_trace_present — every CONFIRMED/MISMATCH carries
                                      a non-empty data block with a
                                      `formula` or `rule` key (or the
                                      fields the other verifiers
                                      already populate)
  * witness.anchors_resolve         — every cited anchor's `layer` is
                                      one of the source hierarchy:
                                      {jesus_words, bible, apostles,
                                      recognized_elders}
  * witness.no_fabricated_answer    — the packet has no top-level
                                      `final_answer` / `answer` field
                                      (categorize-don't-answer enforced
                                      at the rendering boundary)

WIT_VERIFY shape (any subset; populated by the runner before invocation):
    {
      "claimed_gate_verdicts": [
        {"gate": "RED",      "status": "PASS"},
        {"gate": "FLOOR",    "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
        {"gate": "GOD",      "status": "PASS"},
      ],
      "claimed_verifier_results": [
        {"name": "math.equality", "status": "CONFIRMED",
         "data": {"formula": "...", "rule": "..."}},
      ],
      "claimed_anchors": [
        {"ref": "Mat 5:37", "layer": "jesus_words"},
      ],
    }

The packet itself is read for `final_answer` / `answer` — those fields
must not exist.
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


REQUIRED_GATES = ("RED", "FLOOR", "WAY", "BROTHERS", "GOD")

_GATE_CHAIN_ANCHOR = {
    "ref": "Deut 19:15",
    "layer": "bible",
    "derivation": (
        "Plural witness for binding judgment: 'A single witness shall "
        "not suffice against a person... only on the evidence of two "
        "witnesses or three witnesses shall a charge be established.' "
        "The four-gate chain (RED → FLOOR → BROTHERS → GOD) is the "
        "engine's plural-witness procedure. A sealed record without a "
        "verdict at every gate (or an explicit short-circuit) lacks "
        "the testimony Deut 19:15 demands."
    ),
}

_REASONING_TRACE_ANCHOR = {
    "ref": "1 Cor 14:33",
    "layer": "apostles",
    "derivation": (
        "Order over confusion: 'God is not a God of confusion but of "
        "peace.' A verifier that confirms or rejects without showing "
        "its reasoning is producing confusion under the appearance of "
        "judgment. Every CONFIRMED/MISMATCH must carry the rule and "
        "data the verdict is built on — the trace is what makes the "
        "verdict reviewable."
    ),
}

_NO_FABRICATED_ANSWER_ANCHOR = {
    "ref": "Mt 5:37",
    "layer": "jesus_words",
    "derivation": (
        "Categorize, don't answer: 'Let what you say be simply Yes "
        "or No; anything more than this comes from evil.' The engine "
        "produces gate verdicts and verifier classifications; it does "
        "not produce 'the answer.' A sealed record carrying a "
        "final_answer / answer / engine_answer field is the engine "
        "claiming an authority Mt 5:37 forbids. This check enforces "
        "the absence at the rendering boundary."
    ),
}
TERMINAL_STATUSES = ("PASS", "REJECT", "QUARANTINE")
SOURCE_HIERARCHY_LAYERS = (
    "jesus_words", "bible", "apostles", "recognized_elders",
)
TRACE_REQUIRED_STATUSES = ("CONFIRMED", "MISMATCH")
TRACE_REQUIRED_KEYS = ("formula", "rule")
FABRICATED_ANSWER_FIELDS = ("final_answer", "answer", "engine_answer", "verdict_answer")


def verify_gate_chain_complete(packet: Dict[str, Any]) -> VerifierResult:
    name = "witness.gate_chain_complete"
    wv = packet.get("WIT_VERIFY") or {}
    verdicts = wv.get("claimed_gate_verdicts")
    if verdicts is None:
        return na(name)
    if not isinstance(verdicts, list):
        return error(name, "claimed_gate_verdicts must be a list")

    by_gate: Dict[str, str] = {}
    for v in verdicts:
        if not isinstance(v, dict):
            return error(name, f"each gate verdict must be a dict, got {type(v).__name__}")
        g = v.get("gate")
        s = v.get("status")
        if g is None or s is None:
            return error(name, "each gate verdict requires `gate` and `status`")
        if s not in TERMINAL_STATUSES:
            return error(name, f"gate {g} status {s!r} not in {TERMINAL_STATUSES}")
        # First verdict per gate wins (chronological).
        by_gate.setdefault(str(g), str(s))

    missing: List[str] = []
    short_circuit_at: int | None = None
    for i, gate in enumerate(REQUIRED_GATES):
        if gate not in by_gate:
            # Legitimate only if a prior gate produced REJECT/QUARANTINE.
            if short_circuit_at is None:
                missing.append(gate)
            continue
        status = by_gate[gate]
        if status in ("REJECT", "QUARANTINE") and short_circuit_at is None:
            short_circuit_at = i

    data = {
        "anchor": _GATE_CHAIN_ANCHOR,
        "rule": (
            "all four gates have a verdict, or an earlier gate "
            "short-circuited with REJECT/QUARANTINE (Deut 19:15 — "
            "plural witness establishes a charge)"
        ),
        "required_gates": list(REQUIRED_GATES),
        "observed": by_gate,
        "missing": missing,
        "short_circuit_at_gate": REQUIRED_GATES[short_circuit_at] if short_circuit_at is not None else None,
    }
    if not missing:
        msg = "all gates accounted for"
        if short_circuit_at is not None:
            msg += f" (chain short-circuited at {REQUIRED_GATES[short_circuit_at]})"
        return confirm(name, msg, data)
    return mismatch(name, f"missing gate verdicts: {missing}", data)


def verify_reasoning_trace_present(packet: Dict[str, Any]) -> VerifierResult:
    name = "witness.reasoning_trace_present"
    wv = packet.get("WIT_VERIFY") or {}
    results = wv.get("claimed_verifier_results")
    if results is None:
        return na(name)
    if not isinstance(results, list):
        return error(name, "claimed_verifier_results must be a list")

    untraced: List[Dict[str, Any]] = []
    for r in results:
        if not isinstance(r, dict):
            return error(name, f"each verifier result must be a dict, got {type(r).__name__}")
        status = r.get("status")
        if status not in TRACE_REQUIRED_STATUSES:
            continue
        data_block = r.get("data")
        if not isinstance(data_block, dict) or not data_block:
            untraced.append({"name": r.get("name"), "reason": "missing or empty `data`"})
            continue
        if not any(k in data_block for k in TRACE_REQUIRED_KEYS):
            untraced.append({
                "name": r.get("name"),
                "reason": f"`data` lacks any of {TRACE_REQUIRED_KEYS}",
            })

    data = {
        "anchor": _REASONING_TRACE_ANCHOR,
        "rule": (
            "every CONFIRMED/MISMATCH result must carry a non-empty "
            "`data` block with a formula or rule (1 Cor 14:33 — order, "
            "not confusion)"
        ),
        "checked_count": len(results),
        "untraced": untraced,
        "required_data_keys": list(TRACE_REQUIRED_KEYS),
    }
    if not untraced:
        return confirm(name, f"all {len(results)} verifier results carry a reasoning trace", data)
    return mismatch(name, f"{len(untraced)} verifier result(s) missing reasoning trace", data)


def verify_anchors_resolve(packet: Dict[str, Any]) -> VerifierResult:
    name = "witness.anchors_resolve"
    wv = packet.get("WIT_VERIFY") or {}
    anchors = wv.get("claimed_anchors")
    if anchors is None:
        return na(name)
    if not isinstance(anchors, list):
        return error(name, "claimed_anchors must be a list")

    unresolved: List[Dict[str, Any]] = []
    for a in anchors:
        if not isinstance(a, dict):
            return error(name, f"each anchor must be a dict, got {type(a).__name__}")
        layer = a.get("layer")
        if layer is None:
            unresolved.append({"ref": a.get("ref"), "reason": "no `layer` declared"})
            continue
        if layer not in SOURCE_HIERARCHY_LAYERS:
            unresolved.append({
                "ref": a.get("ref"),
                "reason": f"layer {layer!r} not in source hierarchy {SOURCE_HIERARCHY_LAYERS}",
            })

    data = {
        "anchor_count": len(anchors),
        "unresolved": unresolved,
        "source_hierarchy": list(SOURCE_HIERARCHY_LAYERS),
        "rule": "every anchor's layer must be one of the source-hierarchy layers (Jesus' words primary, Bible secondary, apostles, recognized elders)",
    }
    if not unresolved:
        return confirm(name, f"all {len(anchors)} anchors resolve to source-hierarchy layers", data)
    return mismatch(name, f"{len(unresolved)} anchor(s) do not resolve", data)


def verify_rule_anchors_resolve(packet: Dict[str, Any]) -> VerifierResult:
    """Every verifier-rule anchor must resolve to a source-hierarchy layer.

    A verifier rule may declare its derivation by including an `anchor`
    field in its `data` dict:
      data = {"anchor": {"ref": "Mt 18:16", "layer": "jesus_words",
                         "derivation": "..."}, "rule": ..., ...}

    When the anchor is present, this check validates that:
      * `ref` is a non-empty string
      * `layer` is one of the source hierarchy
        (jesus_words / bible / apostles / recognized_elders)

    Verifiers without an anchor field are silently passed — the
    convention is opt-in. Future iterations may roll the anchor out
    to every verifier rule, at which point this check becomes a
    coverage check (every rule must declare its derivation).
    """
    name = "witness.rule_anchors_resolve"
    wv = packet.get("WIT_VERIFY") or {}
    results = wv.get("claimed_verifier_results")
    if results is None:
        return na(name)
    if not isinstance(results, list):
        return error(name, "claimed_verifier_results must be a list")

    bad: List[Dict[str, Any]] = []
    checked = 0
    for r in results:
        if not isinstance(r, dict):
            continue
        data_block = r.get("data")
        if not isinstance(data_block, dict):
            continue
        anchor = data_block.get("anchor")
        if anchor is None:
            continue  # opt-in convention
        checked += 1
        if not isinstance(anchor, dict):
            bad.append({"name": r.get("name"),
                        "reason": f"`anchor` must be a dict, got {type(anchor).__name__}"})
            continue
        ref = anchor.get("ref")
        layer = anchor.get("layer")
        if not isinstance(ref, str) or not ref.strip():
            bad.append({"name": r.get("name"),
                        "reason": "anchor.ref missing or empty"})
            continue
        if layer not in SOURCE_HIERARCHY_LAYERS:
            bad.append({
                "name": r.get("name"),
                "reason": f"anchor.layer {layer!r} not in source hierarchy {SOURCE_HIERARCHY_LAYERS}",
            })

    data = {
        "checked_count": checked,
        "bad_anchors": bad,
        "source_hierarchy": list(SOURCE_HIERARCHY_LAYERS),
        "rule": (
            "every verifier rule that declares an anchor must point to a "
            "source-hierarchy layer (Jesus' words primary, Bible, "
            "apostles, recognized elders)"
        ),
    }
    if checked == 0:
        return na(name, "no verifier rules declared an anchor")
    if not bad:
        return confirm(name, f"all {checked} declared rule anchor(s) resolve", data)
    return mismatch(name, f"{len(bad)} rule anchor(s) do not resolve", data)


def verify_no_fabricated_answer(packet: Dict[str, Any]) -> VerifierResult:
    """Categorize-don't-answer enforced at the rendering boundary.

    The engine must not seal a record that contains a fabricated answer
    field. Categorization, gate verdicts, verifier results, closest-case
    overlay are allowed. A field claiming to *be* the answer is not.
    """
    name = "witness.no_fabricated_answer"
    found: List[str] = []
    for fld in FABRICATED_ANSWER_FIELDS:
        if fld in packet and packet[fld] not in (None, "", [], {}):
            found.append(fld)
    wv = packet.get("WIT_VERIFY") or {}
    # Allow explicit declaration that the runner did not write any answer.
    declared = wv.get("declared_no_answer")

    data = {
        "anchor": _NO_FABRICATED_ANSWER_ANCHOR,
        "rule": (
            "the engine categorizes; it does not answer. No "
            "`final_answer` / `answer` / `engine_answer` / "
            "`verdict_answer` field may carry content (Mt 5:37 — let "
            "your yes be yes)."
        ),
        "scanned_fields": list(FABRICATED_ANSWER_FIELDS),
        "fabricated_fields_present": found,
        "declared_no_answer": bool(declared) if declared is not None else None,
    }
    if not found:
        return confirm(name, "no fabricated answer field present", data)
    return mismatch(name, f"fabricated answer field(s) present: {found}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    wv = packet.get("WIT_VERIFY") or {}
    if "claimed_gate_verdicts" in wv:
        results.append(verify_gate_chain_complete(packet))
    if "claimed_verifier_results" in wv:
        results.append(verify_reasoning_trace_present(packet))
        results.append(verify_rule_anchors_resolve(packet))
    if "claimed_anchors" in wv:
        results.append(verify_anchors_resolve(packet))
    # The no-fabricated-answer check runs unconditionally when WIT_VERIFY is
    # present at all — it's the categorize-don't-answer enforcer and applies
    # to every sealed record.
    if wv:
        results.append(verify_no_fabricated_answer(packet))
    if not results:
        results.append(na("witness", "no WIT_VERIFY artifacts present"))
    return results
