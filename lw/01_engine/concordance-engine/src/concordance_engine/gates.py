"""
concordance_engine/gates.py — Four-gate validation pipeline.

Gates run in order: RED → FLOOR → BROTHERS → GOD
First gate to fail determines the overall verdict.

RED      → REJECT   (hard violations: deception, exploitation, logical impossibility)
FLOOR    → REJECT   (minimum rigour not met)
BROTHERS → QUARANTINE (insufficient witnesses or wait period not elapsed)
GOD      → PASS     (all gates cleared)
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .packet import GateResult, ValidationResult
from .verifiers import chemistry, physics, mathematics, statistics, computer_science, biology, governance, scripture


# ---------------------------------------------------------------------------
# Governance text scanner — RED gate
# ---------------------------------------------------------------------------

_RED_PATTERNS = [
    # (pattern, category, description)
    (r"\bpretend(?:ing|ed|s)?\b.{0,60}\b(?:customer|client|employee|user|member|student)s?\b",
     "deception", "Deception: false identity or fake testimonials"),
    (r"\bfabricat(?:e|ed|ing|es)\b.{0,40}\b(?:testimonial|review|data|result|evidence)s?\b",
     "deception", "Deception: fabricated data or testimonials"),
    (r"\bfake\s+testimonial",
     "deception", "Deception: fake testimonials"),
    (r"\bdeceiv(?:e|ed|ing|es)\b",
     "deception", "Deception: active deception"),
    (r"\bexploit\b.{0,40}\b(?:captive|audience|vulnerable|worker|employee|tenant|student|client)\b",
     "exploitation", "Exploitation: exploiting a captive or vulnerable population"),
    (r"\bpredatory\b.{0,40}\b(?:lend|loan|pric|term|practic)\w*",
     "exploitation", "Exploitation: predatory lending or pricing"),
    (r"\busury\b",
     "exploitation", "Exploitation: usury"),
    (r"\bcoerce\b",
     "coercion", "Coercion: coercive practice"),
    (r"\bmandatory\s+surveillance\b",
     "coercion", "Coercion: mandatory surveillance as control mechanism"),
    (r"\bhide\b.{0,30}\bfinancial\b|\bstop\s+publish\w*\b.{0,40}\bfinancial\b",
     "accountability", "Accountability: concealing financial information"),
    (r"\blast\?\s*vest\b|\blabel(?:ed|led)?\s+(?:DISRUPTIVE|PROBLEM|BAD)",
     "identity_branding", "Identity branding: shame-based labeling of individuals"),
    (r"\bwear\s+a\s+vest\b.{0,60}\blabel\w*\b|\bvest\b.{0,30}\blabel\w*\b",
     "identity_branding", "Identity branding: public shame-vest or label"),
]

_NEGATION_WORDS = {"not", "never", "no", "won't", "will not", "do not", "don't",
                   "cannot", "can't", "shouldn't", "wouldn't", "aren't", "isn't",
                   "doesn't", "didn't", "won't", "refuse", "prohibit", "forbidden",
                   "avoid", "prevent", "without", "cease"}


def _is_negated(text: str, match_start: int, window: int = 6) -> bool:
    """
    Check if the match is preceded by a negation word within the same clause.
    Clause boundary = last comma, period, semicolon, or 'but'/'however' pivot.
    """
    before = text[:match_start]
    # Find the start of the current clause (last major punctuation)
    last_punct = max(
        before.rfind(","), before.rfind("."), before.rfind(";"),
        before.rfind("!"), before.rfind("?")
    )
    clause_start = last_punct + 1 if last_punct >= 0 else 0
    clause = before[clause_start:]
    tokens = re.findall(r"\b\w+\b", clause)
    context = tokens[-window:]
    return any(t.lower() in _NEGATION_WORDS for t in context)


def _scan_text_red(text: str) -> List[Tuple[str, str]]:
    """
    Scan text for RED-gate governance violations.
    Returns list of (category, description) for each confirmed violation.
    """
    text_lower = text.lower()
    violations = []
    seen_categories = set()

    for pattern, category, description in _RED_PATTERNS:
        for m in re.finditer(pattern, text_lower):
            if category in seen_categories:
                continue
            if _is_negated(text_lower, m.start()):
                continue
            violations.append((category, description))
            seen_categories.add(category)

    return violations


# ---------------------------------------------------------------------------
# Domain-specific RED gate checks
# ---------------------------------------------------------------------------

def _red_mathematics(packet: dict) -> List[str]:
    reasons = []
    math_red = packet.get("MATH_RED") or {}
    if not math_red:
        return reasons  # flat packet — pass

    wf = math_red.get("well_formedness") or {}
    ts = math_red.get("type_safety") or {}
    di = math_red.get("definitional_integrity") or {}
    ii = math_red.get("inference_integrity") or {}

    if wf.get("symbols_defined") is False:
        reasons.append("MATH_RED: undefined symbols")
    if wf.get("quantifiers_scoped") is False:
        reasons.append("MATH_RED: unscoped quantifiers")
    if ts.get("objects_typed") is False:
        reasons.append("MATH_RED: untyped objects")
    if ts.get("operations_valid") is False:
        reasons.append("MATH_RED: invalid operations")
    if di.get("no_circular_definitions") is False:
        reasons.append("MATH_RED: circular definitions")
    if ii.get("rules_named") is False:
        reasons.append("MATH_RED: inference rules unnamed")
    if ii.get("steps_justified") is False:
        reasons.append("MATH_RED: unjustified inference steps")

    return reasons


def _red_physics(packet: dict) -> List[str]:
    reasons = []
    cc = packet.get("conservation_checks")
    if cc is None:
        reasons.append("PHYS_RED: conservation_checks field required for physics domain")
    return reasons


def _red_chemistry(packet: dict) -> List[str]:
    reasons = []
    chem_red = packet.get("CHEM_RED") or {}
    setup = packet.get("CHEM_SETUP") or {}

    if chem_red.get("mass_conserved") is False:
        reasons.append("CHEM_RED: mass conservation violated")
    if chem_red.get("charge_conserved") is False or chem_red.get("charge_balanced") is False:
        reasons.append("CHEM_RED: charge conservation violated")
    if chem_red.get("dimensional_consistency") is False:
        reasons.append("CHEM_RED: dimensional inconsistency")
    if chem_red.get("equilibrium_in_activities") is False:
        reasons.append("CHEM_RED: equilibrium must be expressed in activities, not concentrations")
    if chem_red.get("state_path_integrity") is False:
        reasons.append("CHEM_RED: state/path integrity violated")

    # Physical temperature check
    temp = setup.get("temperature_K")
    if temp is not None and float(temp) <= 0:
        reasons.append(f"CHEM_SETUP: temperature_K={temp} is unphysical (must be > 0 K)")

    # Diagnostics
    for diag in packet.get("diagnostics") or []:
        d = str(diag.get("diagnosis", "")).upper()
        if d == "MODEL_MISMATCH":
            reasons.append(f"CHEM_DIAGNOSTIC: MODEL_MISMATCH — {diag.get('action', '')}")

    return reasons


def _red_biology(packet: dict) -> List[str]:
    reasons = []
    bio_red = packet.get("BIO_RED") or {}
    if not bio_red:
        return reasons  # flat packet — pass

    conservation = bio_red.get("conservation") or {}
    if conservation.get("mass_balance") is False:
        reasons.append("BIO_RED: mass balance violated")
    if conservation.get("charge_balance") is False:
        reasons.append("BIO_RED: charge balance violated")
    if conservation.get("energy_budget") is False:
        reasons.append("BIO_RED: energy budget violated")

    if bio_red.get("second_law_satisfied") is False:
        reasons.append("BIO_RED: second law of thermodynamics violated")

    causality = bio_red.get("causality") or {}
    if causality.get("mechanism_specified") is False:
        reasons.append("BIO_RED: causality mechanism not specified")

    return reasons


def _red_biology_measurement(packet: dict) -> List[str]:
    reasons = []
    bio_meas = packet.get("BIO_MEASUREMENT") or {}
    if not bio_meas:
        return reasons

    n_reps = bio_meas.get("biological_replicates", 3)
    if int(n_reps) < 3:
        reasons.append(f"BIO_MEASUREMENT: biological_replicates={n_reps} < minimum 3")

    if bio_meas.get("decision_grade_claim"):
        assay_classes = bio_meas.get("orthogonal_assay_classes", [])
        if len(set(assay_classes)) < 2:
            reasons.append("BIO_MEASUREMENT: decision-grade claim requires ≥2 orthogonal assay classes")

    return reasons


def _red_statistics(packet: dict) -> List[str]:
    reasons = []
    stat_red = packet.get("STAT_RED") or {}
    if not stat_red:
        return reasons  # flat packet

    if stat_red.get("hypothesis_prespecified") is False:
        reasons.append("STAT_RED: hypothesis was not pre-specified (post-hoc testing)")
    if stat_red.get("pvalue_interpreted_correctly") is False:
        reasons.append("STAT_RED: p-value misinterpretation detected")
    if stat_red.get("multiple_comparisons_corrected") is False:
        reasons.append("STAT_RED: multiple comparisons not corrected")

    # Effect size required when result is significant
    stat_inf = packet.get("STAT_INFERENCE") or {}
    p = stat_inf.get("p_value")
    alpha = stat_inf.get("alpha", 0.05)
    if p is not None and float(p) < float(alpha):
        # Significant result — effect size must be declared somewhere
        has_effect = (stat_red.get("effect_size_reported") is True or
                      stat_inf.get("effect_size") is not None)
        if not has_effect:
            reasons.append("STAT_RED: effect size required when result is statistically significant")

    return reasons


def _red_computer_science(packet: dict) -> List[str]:
    reasons = []
    cs_red = packet.get("CS_RED") or {}
    if not cs_red:
        return reasons  # flat packet

    if cs_red.get("termination_proven") is False:
        reasons.append("CS_RED: termination not proven")
    if cs_red.get("no_undefined_behavior") is False:
        reasons.append("CS_RED: undefined behavior present")
    if cs_red.get("reduction_direction_stated") is False:
        reasons.append("CS_RED: reduction direction not stated")
    if cs_red.get("consistency_model_cited") is False:
        reasons.append("CS_RED: distributed system has no consistency model")

    complexity = packet.get("CS_COMPLEXITY") or {}
    if complexity:
        # When time_bound (formal key) is used, input_variable is required
        if complexity.get("time_bound") and not complexity.get("input_variable"):
            reasons.append("CS_COMPLEXITY: input_variable not declared (required with time_bound)")

    return reasons


def _red_governance(packet: dict) -> List[str]:
    """Scan text + check DECISION_PACKET for governance RED violations."""
    reasons = []
    text = packet.get("text", "")
    if text:
        violations = _scan_text_red(text)
        for category, description in violations:
            reasons.append(f"GOV_RED[{category}]: {description}")

    # DECISION_PACKET checks
    dp = packet.get("DECISION_PACKET")
    if dp is not None:
        vr = governance.verify_decision_packet_shape(dp)
        if vr.status == "MISMATCH":
            reasons.append(f"DECISION_PACKET: {vr.detail}")
        wc = governance.verify_witness_count_consistency(dp, packet)
        if wc.status == "MISMATCH":
            reasons.append(f"DECISION_PACKET: {wc.detail}")

    return reasons


# ---------------------------------------------------------------------------
# FLOOR gate checks
# ---------------------------------------------------------------------------

def _floor_chemistry(packet: dict) -> List[str]:
    reasons = []
    floor = packet.get("CHEM_FLOOR") or {}
    if not floor:
        return reasons

    if floor.get("hazardous_conditions") and not floor.get("safety_notes_included", True):
        reasons.append("CHEM_FLOOR: hazardous conditions present but safety notes not included")
    if floor.get("limiting_cases_checked") is False:
        reasons.append("CHEM_FLOOR: limiting cases not checked")

    return reasons


def _floor_statistics(packet: dict) -> List[str]:
    reasons = []
    floor = packet.get("STAT_FLOOR") or {}
    if not floor:
        return reasons

    if floor.get("distributional_assumptions_tested") is False:
        reasons.append("STAT_FLOOR: distributional assumptions not tested")
    if floor.get("sampling_mechanism_stated") is False:
        reasons.append("STAT_FLOOR: sampling mechanism not stated")

    return reasons


def _floor_computer_science(packet: dict) -> List[str]:
    reasons = []
    floor = packet.get("CS_FLOOR") or {}
    return reasons  # CS floor failures are warnings, not hard rejections in current spec


# ---------------------------------------------------------------------------
# Verifier layer — run computational checks
# ---------------------------------------------------------------------------

def _run_verifiers(packet: dict, domain: str) -> List[Tuple[str, str]]:
    """
    Run computational verifiers for the domain.
    Returns list of (verifier_name, detail) for each MISMATCH or ERROR.
    """
    failures = []
    verifier_details = []

    if domain == "chemistry":
        results = chemistry.run(packet)
    elif domain == "physics":
        results = physics.run(packet)
    elif domain == "mathematics":
        results = mathematics.run(packet)
    elif domain == "statistics":
        results = statistics.run(packet)
    elif domain == "computer_science":
        results = computer_science.run(packet)
    elif domain == "biology":
        results = biology.run(packet)
    elif domain == "governance":
        results = governance.run(packet)
    else:
        results = []

    # Scripture anchor verification — runs for any domain that has scripture_anchors or refs
    dp = packet.get("DECISION_PACKET") or {}
    if dp.get("scripture_anchors") or packet.get("scripture_anchors") or packet.get("refs"):
        results.extend(scripture.run(packet))

    for vr in results:
        verifier_details.append({
            "name": vr.name,
            "status": vr.status,
            "detail": vr.detail,
            "data": vr.data,
        })
        if vr.status in ("MISMATCH", "ERROR"):
            failures.append((vr.name, vr.detail))

    return failures, verifier_details


# ---------------------------------------------------------------------------
# Gate functions
# ---------------------------------------------------------------------------

def gate_red(packet: dict, domain: str, run_verifiers: bool = True) -> GateResult:
    reasons = []

    if domain in ("governance", "business", "education", "church", "nonprofit"):
        reasons.extend(_red_governance(packet))
    elif domain == "mathematics":
        reasons.extend(_red_mathematics(packet))
    elif domain == "physics":
        reasons.extend(_red_physics(packet))
    elif domain == "chemistry":
        reasons.extend(_red_chemistry(packet))
    elif domain == "biology":
        reasons.extend(_red_biology(packet))
        reasons.extend(_red_biology_measurement(packet))
    elif domain == "statistics":
        reasons.extend(_red_statistics(packet))
    elif domain == "computer_science":
        reasons.extend(_red_computer_science(packet))

    # Run computational verifiers (domain-agnostic — whoever has VERIFY blocks)
    verifier_failures = []
    verifier_details = []
    if run_verifiers:
        verifier_failures, verifier_details = _run_verifiers(packet, domain)
        for vname, vdetail in verifier_failures:
            reasons.append(f"VERIFIER[{vname}]: {vdetail}")

    if reasons:
        return GateResult(
            gate="RED", status="REJECT", reasons=reasons,
            details={"verifier_failures": verifier_details}
        )
    return GateResult(gate="RED", status="PASS",
                      details={"verifier_details": verifier_details})


def gate_floor(packet: dict, domain: str) -> GateResult:
    reasons = []

    if domain == "chemistry":
        reasons.extend(_floor_chemistry(packet))
    elif domain == "statistics":
        reasons.extend(_floor_statistics(packet))
    elif domain == "computer_science":
        reasons.extend(_floor_computer_science(packet))

    if reasons:
        return GateResult(gate="FLOOR", status="REJECT", reasons=reasons)
    return GateResult(gate="FLOOR", status="PASS")


def gate_brothers(packet: dict, now_epoch: int,
                  wait_window_seconds: int = 3600) -> GateResult:
    reasons = []
    required = int(packet.get("required_witnesses", 0))
    count = int(packet.get("witness_count", 0))

    if count < required:
        reasons.append(
            f"BROTHERS: insufficient witnesses — {count} present, {required} required"
        )

    created = packet.get("created_epoch")
    if created is not None:
        elapsed = now_epoch - int(created)
        if elapsed < wait_window_seconds:
            reasons.append(
                f"BROTHERS: wait window not elapsed — {elapsed}s elapsed, "
                f"{wait_window_seconds}s required"
            )

    if reasons:
        return GateResult(gate="BROTHERS", status="QUARANTINE", reasons=reasons)
    return GateResult(gate="BROTHERS", status="PASS")


def gate_god(packet: dict) -> GateResult:
    """Final gate — always PASS if prior gates cleared."""
    return GateResult(gate="GOD", status="PASS")
