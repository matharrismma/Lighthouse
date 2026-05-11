"""Polymathic Agent — Path C. The cross-domain coordinator.

Architecture: verifiers, dispatchers, coordinator.
  * verify_* functions   = verifiers   (one domain, deterministic)
  * dispatch rules       = dispatchers (route NL to the right verifier)
  * poly_agent           = coordinator (runs all verifiers, synthesizes)

The coordinator receives a situation, identifies all applicable verifiers
via the oracle, and runs them. It can split the work into umbrella
clusters — sub-coordinators for related domain groups — so compute stays
bounded without losing coverage.

Split rule: when identified domains > split_threshold, process domains
grouped by umbrella first (most-populated cluster first). Stop early
if the composite verdict is already determined (all-CONCORDANT or
first DISCORDANT from any cluster).

Quantum connection: the oracle phase holds domain possibilities in
superposition. The verifier phase collapses each to a definite result.
The synthesis is measurement of the collective state.

Usage:
    from concordance_engine.agent.poly_agent import run_polymathic
    rec = run_polymathic("I worked 55h/wk as a misclassified contractor...")
"""
from __future__ import annotations

import inspect
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, Tuple

from ..grid import UMBRELLAS, AXIS_DIMENSIONS
from .verifier_schema import FIELD_SPEC_BLOCK as _AUTO_FIELD_SPEC_BLOCK
from ..poly_record import (
    DomainResult,
    PolymathicRecord,
    compute_axis_overlaps,
    compute_composite_verdict,
    compute_weighted_composite_verdict,
    compute_axis_weights,
    CONCORDANT, DISCORDANT,
)
from .quarantine_keeper import tend_quarantine
from ..witness_record import axis_coords_for


# ── Domain registry ────────────────────────────────────────────────────

_ALL_DOMAINS = [
    # Core science
    "chemistry", "physics_dimensional", "physics_conservation",
    "mathematics", "statistics_pvalue", "statistics_multiple_comparisons",
    "statistics_confidence_interval",
    # Life sciences
    "biology", "genetics", "medicine", "nutrition", "agriculture",
    "exercise_science", "ecology",
    # Earth / environment
    "geology", "meteorology", "hydrology", "astronomy", "geography",
    "soil_science", "oceanography",
    # Engineering / physical
    "physics", "electrical", "energy", "thermodynamics",
    "nuclear_physics", "optics", "acoustics", "fluid_dynamics",
    # Technology
    "computer_science", "networking", "cybersecurity",
    "cryptography", "quantum_computing", "information_theory",
    # Social / economic
    "economics", "labor", "finance", "real_estate",
    "construction", "manufacturing", "operations_research",
    # Formal / linguistic
    "mathematics", "formal_logic", "linguistics", "number_theory",
    "combinatorics", "geometry", "information_theory",
    # Human / arts
    "music_theory", "photography", "sports_analytics", "calendar_time",
    "exercise_science", "geography",
    # Governance / authority
    "governance_decision_packet", "law", "document_validation", "witness",
    # Humanities / theology
    "scripture_anchors", "theology_doctrine", "history_chronology",
    "rhetoric", "philosophy",
    # Materials / cross-domain
    "materials_science", "architecture",
    # Public-domain reference data verifiers
    "physical_constants", "periodic_table", "ephemeris",
    # Layer 0 — Scripture grounding (engine surfaces WEB text; does not interpret)
    "layer_zero_grounding",
    # Deep math: linear algebra (vectors + matrices via NumPy) and probability
    "linear_algebra", "probability",
]

# Deduplicate while preserving order
_seen: set = set()
_ALL_DOMAINS_DEDUP: list = []
for _d in _ALL_DOMAINS:
    if _d not in _seen:
        _seen.add(_d)
        _ALL_DOMAINS_DEDUP.append(_d)
_ALL_DOMAINS = _ALL_DOMAINS_DEDUP
del _seen, _ALL_DOMAINS_DEDUP

# umbrella → its child domains
_UMBRELLA_CHILDREN: Dict[str, Tuple[str, ...]] = {
    parent: children
    for parent, children in UMBRELLAS.items()
    if children
}

# domain → parent umbrella (reverse map)
_DOMAIN_UMBRELLA: Dict[str, str] = {
    child: parent
    for parent, children in _UMBRELLA_CHILDREN.items()
    for child in children
}


# ── Oracle prompts ─────────────────────────────────────────────────────

_DECOMPOSE_SYSTEM = (
    "You are a claim decomposer for a verification engine. "
    "Break a complex situation into atomic, self-contained verifiable claims. "
    "Each claim must: (1) stand alone without reference to other claims, "
    "(2) be specific enough to verify with concrete values, "
    "(3) map to a single domain. Discard vague or purely narrative sentences. "
    "\n\n"
    "CRITICAL — do NOT over-split:\n"
    "  - Chemical equations, mathematical equations, physics formulas, "
    "    and other structured expressions are ATOMIC. Keep them whole. "
    "    Example: 'CH4 + 2 O2 -> CO2 + 2 H2O' is ONE claim, not five. "
    "    'F = m × a' is ONE claim. 'P V = n R T' is ONE claim.\n"
    "  - A claim with multiple related quantities that must be verified "
    "    together (e.g. 'Carnot engine at 600 K hot, 300 K cold has 50% "
    "    efficiency') is ONE claim, not three. "
    "  - Split only when the situation contains multiple INDEPENDENT "
    "    claims about different things (e.g. 'Methane combustion produces "
    "    CO2 and water. A typical car emits 4.6 metric tons of CO2 per "
    "    year.' — those are two atomic claims).\n"
    "\n"
    "When in doubt, keep claims together. The verifier expects a complete "
    "verifiable statement, not a fragment. "
    "\n\n"
    "🛑 DO NOT CORRECT THE USER. Each atomic claim must preserve every "
    "numeric value EXACTLY as the user stated it. If the user writes "
    "'Iron has atomic number 99', the atomic claim is literally 'Iron has "
    "atomic number 99' — NOT 'Iron has atomic number 26'. The downstream "
    "verifier is what catches errors; if you silently fix them here, the "
    "engine confirms fake claims. Copy values verbatim, including obviously "
    "wrong ones.\n"
    "\n"
    'Return ONLY valid JSON: {"claims": ["claim 1", "claim 2", ...]}'
)

_CLASSIFY_SYSTEM = (
    "You are a domain classifier for the Concordance verification engine. "
    "Given a single atomic claim, identify the ONE best domain and extract the verifier spec "
    "using the EXACT field names listed below. "
    "Valid domains: " + ", ".join(_ALL_DOMAINS) + ". "
    "\n\n"
    "Required field names per domain. These are AUTO-EXTRACTED from the verifier "
    "source code — they are exactly what the verifier checks, no synonyms. Pick the "
    "fields from this list that match the claim; omit ones the claim doesn't supply:\n"
    + _AUTO_FIELD_SPEC_BLOCK + "\n"
    "Conventions:\n"
    "  - rate fields are DECIMAL fractions, not percents: 5% → 0.05, 12% → 0.12.\n"
    "  - temperatures in Kelvin where the field name has _K (Carnot, entropy);\n"
    "    Celsius/Fahrenheit only where the field name says _C or _F.\n"
    "  - physics symbols use SymPy unit syntax (singular, ASCII):\n"
    "      newton, kilogram, meter, second, meter/second**2, kilogram*meter/second**2.\n"
    "      Never 'meters per second squared' or other prose forms.\n"
    "  - chemistry equations use ASCII -> for the arrow.\n"
    "Do not invent extra fields (no verification_type, expected_result, is_balanced, variables, "
    "expression, operation_type, etc.). Use ONLY the field names listed above. "
    'Return ONLY valid JSON: {"domain": "<name>", "spec": {<exact verifier fields>}}. '
    "\n\n"
    "🛑 CRITICAL — DO NOT CORRECT THE USER. EVER. 🛑\n"
    "\n"
    "Your ONLY job in this step is to extract the user's claim verbatim. Every numeric "
    "value, every unit, every quantity — copy it from the user's text WORD FOR WORD into "
    "the spec. Do NOT substitute the correct value. Do NOT 'fix' the user's mistake. The "
    "verifier is what catches mistakes; if you fix them silently, the engine cannot do its "
    "job.\n"
    "\n"
    "EXAMPLES OF WHAT TO DO:\n"
    "  User says:  'Iron has atomic number 99.'\n"
    "  WRONG spec: {symbol: 'Fe', claimed_atomic_number: 26}    ← you corrected it\n"
    "  RIGHT spec: {symbol: 'Fe', claimed_atomic_number: 99}    ← user's value verbatim\n"
    "\n"
    "  User says:  'The speed of light is 100 m/s.'\n"
    "  WRONG spec: {constant: 'speed_of_light', claimed_value: 299792458}\n"
    "  RIGHT spec: {constant: 'speed_of_light', claimed_value: 100}\n"
    "\n"
    "  User says:  'A circle of radius 5 m has area 1000 m².'\n"
    "  WRONG spec: {circle_radius: 5, claimed_circle_area: 78.54}\n"
    "  RIGHT spec: {circle_radius: 5, claimed_circle_area: 1000}\n"
    "\n"
    "  User says:  'The derivative of x squared is x cubed.'\n"
    "  WRONG spec: {mode: 'derivative', params: {function: 'x**2', variable: 'x', claimed_derivative: '2*x'}}\n"
    "  RIGHT spec: {mode: 'derivative', params: {function: 'x**2', variable: 'x', claimed_derivative: 'x**3'}}\n"
    "\n"
    "  User says:  'A Carnot engine at 600 K hot and 300 K cold has 0.9 efficiency.'\n"
    "  WRONG spec: {T_hot_K: 600, T_cold_K: 300, claimed_efficiency: 0.5}\n"
    "  RIGHT spec: {T_hot_K: 600, T_cold_K: 300, claimed_efficiency: 0.9}\n"
    "\n"
    "If you 'correct' the value before passing it to the verifier, every claim that contains "
    "an error returns CONFIRMED — which means the engine is lying to the user. Pass the "
    "claim through faithfully and let the verifier compute the truth. That is the only way "
    "the engine can do its job.\n"
    "\n"
    "IMPORTANT: If a domain CLEARLY applies to this claim but you cannot extract a precise "
    "spec (e.g. the claim is about thermodynamics but you don't have all four values for any "
    "specific sub-verifier), STILL return that domain with the best-effort spec — or an empty "
    "spec {}. The verifier will return NOT_APPLICABLE, which surfaces 'engine recognized the "
    "domain but lacks a specific check'. That is still useful signal — strictly better than "
    "silence. "
    "Return null ONLY when no domain in the list applies at all."
)

_COMBINED_SYSTEM = (
    "You are a multi-domain classifier for the Concordance verification engine. "
    "Given a situation, identify ALL domains that apply. "
    "Valid domains: " + ", ".join(_ALL_DOMAINS) + ". "
    "For physics: use physics_dimensional or physics_conservation when the claim is about "
    "units or conservation law; otherwise use physics. "
    "For statistics: use statistics_pvalue, statistics_multiple_comparisons, or "
    "statistics_confidence_interval. "
    "For thermodynamics: use field names like T_hot_K, T_cold_K, pressure_Pa, volume_m3, "
    "moles, temperature_K, mass_kg, specific_heat_J_per_kgK, heat_J, claimed_efficiency, "
    "claimed_heat_J, claimed_entropy_change_J_per_K. "
    "For energy: mass_kg, height_m, velocity_m_per_s, power_W, time_s with claimed_* fields. "
    'Return ONLY valid JSON: {"domains": [{"domain": "<name>", "spec": {<verifier fields>}}, ...]}. '
    "Include a domain when applicable even with an empty spec — the verifier will report "
    "NOT_APPLICABLE if fields are missing, which is still useful. Nothing except JSON."
)


def _oracle_call(
    system: str,
    user: str,
    model: str,
    api_key: Optional[str],
    max_tokens: int = 1024,
) -> Optional[Any]:
    """Single oracle call. Returns parsed JSON or None."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}],
        )
        content = msg.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception:
        return None


def decompose_situation(
    situation: str,
    model: str,
    api_key: Optional[str] = None,
) -> List[str]:
    """Step 1 of the two-stage pipeline: situation → atomic claims.

    Breaks a complex multi-domain situation into discrete self-contained
    claims, each verifiable by a single domain verifier. The decomposition
    is stored separately so the coordinator can inspect the breakdown
    before dispatching verifiers.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return []
    parsed = _oracle_call(_DECOMPOSE_SYSTEM, situation, model, key, max_tokens=512)
    if parsed and isinstance(parsed, dict):
        return [str(c) for c in parsed.get("claims", []) if c]
    return []


def classify_claims(
    claims: List[str],
    model: str,
    api_key: Optional[str] = None,
    max_parallel: int = 5,
    source_text: str = "",
) -> List[Dict[str, Any]]:
    """Step 2 of the two-stage pipeline: atomic claims → domain specs.

    Classifies each atomic claim independently — one oracle call per
    claim. More accurate than combined classification because the oracle
    focuses on one claim at a time with no cross-claim interference.

    Calls run in parallel via a small thread pool. Total wall-time drops
    from sum(call_latency) to ~max(call_latency) — a 3-claim situation
    that would have taken ~12s sequentially returns in ~3-4s.
    Result order matches input claim order.

    `source_text` is the ORIGINAL user situation (pre-decomposition).
    Used by the grounding guard — the decomposer can silently rewrite
    numbers, so we ground spec values against the original input, not
    the possibly-corrected atomic claim.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key or not claims:
        return []

    # Ground ONLY against the original situation, never the atomic claim.
    # The decomposer can silently rewrite numbers in the atomic claim
    # (e.g. user says "area 24" but decomposer outputs "area 12" — the
    # correct value). If we let the atomic claim count as source, the
    # corrected value matches and the grounding guard never fires.
    # The original situation is the user's literal text and is the only
    # trustworthy floor for grounding.
    def _grounding_text(claim: str) -> str:
        if source_text:
            return source_text
        return claim  # fallback only when run_polymathic didn't thread situation

    def _one(claim: str) -> Optional[Dict[str, Any]]:
        parsed = _oracle_call(_CLASSIFY_SYSTEM, claim, model, key, max_tokens=256)
        if parsed and isinstance(parsed, dict) and "domain" in parsed:
            d = parsed.get("domain", "")
            spec = parsed.get("spec") or {}
            if d and d in _ALL_DOMAINS:
                # GROUNDING GUARD — Claude (both decomposer AND classifier)
                # is over-helpful and will silently "correct" obvious user
                # errors. ("Iron has atomic number 99" gets decomposed to
                # "Iron has atomic number 26".) If we let the corrected
                # spec through, the engine cheerfully CONFIRMS a fake
                # claim — the engine lying to the user.
                #
                # Check spec values against the ORIGINAL situation text
                # (and the atomic claim as fallback). When ANY numeric
                # value in the spec is not traceable to the source,
                # BLOCK the classification and let the claim quarantine.
                # Engine refuses to verify when it cannot trust the
                # extraction.
                grounded, missing = _spec_grounded_in_source(spec, _grounding_text(claim))
                if not grounded:
                    _BLOCK_LOG[claim] = {
                        "domain": d, "spec": spec,
                        "ungrounded_values": missing,
                        "reason": "classifier_substituted_values",
                    }
                    return None
                return {"domain": d, "spec": spec, "_source_claim": claim}
        return None

    # Reset the block log for this run so callers see only this run's blocks
    _BLOCK_LOG.clear()

    workers = max(1, min(max_parallel, len(claims)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        # executor.map preserves input order, which downstream code relies on
        # (orphans = claims not in the classified set, by claim text)
        outputs = list(pool.map(_one, claims))
    return [r for r in outputs if r is not None]


# Per-run block log — populated by classify_claims._one when grounding
# fails, drained by run_polymathic into the PolymathicRecord. Module
# global is fine because polymathic runs are sequential at the API
# layer.
_BLOCK_LOG: Dict[str, Dict[str, Any]] = {}


# ── Spec-grounding check ────────────────────────────────────────────────
# Defense against Claude's auto-correction reflex. The classifier should
# extract the user's claim verbatim, but Haiku frequently "fixes" obvious
# errors silently. This check rejects any spec whose numeric values are
# not traceable to the source claim text.

_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")


def _numbers_in_text(text: str) -> List[float]:
    """Return every numeric token found in the text, as floats."""
    nums: List[float] = []
    for tok in _NUMBER_RE.findall(text or ""):
        try:
            nums.append(float(tok))
        except ValueError:
            continue
    return nums


def _walk_spec_numbers(value: Any):
    """Yield every numeric value found anywhere in a spec dict/list. Booleans
    are NOT treated as numbers (Python's bool-is-subclass-of-int quirk)."""
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        yield float(value)
    elif isinstance(value, dict):
        for v in value.values():
            yield from _walk_spec_numbers(v)
    elif isinstance(value, list):
        for v in value:
            yield from _walk_spec_numbers(v)


def _value_matches_source(spec_val: float, source_nums: List[float]) -> bool:
    """True if `spec_val` matches some source-text number, allowing
    common unit conversions (percent ↔ decimal, km ↔ m, etc.) — any
    power-of-ten scaling within [-6, 6]."""
    if abs(spec_val) < 1e-12:
        return True  # zero is too common to police
    for s in source_nums:
        if abs(s) < 1e-12:
            continue
        # Exact / near-exact match (within 0.1% relative)
        denom = max(abs(spec_val), abs(s))
        if abs(spec_val - s) / denom < 0.001:
            return True
        # Power-of-10 conversion: spec_val ≈ s × 10^k for some -6 ≤ k ≤ 6
        try:
            ratio = spec_val / s
        except ZeroDivisionError:
            continue
        for k in range(-6, 7):
            target = 10.0 ** k
            if target == 0:
                continue
            if abs(ratio - target) / target < 0.01:
                return True
    return False


def _spec_grounded_in_source(spec: Dict[str, Any], source_text: str) -> Tuple[bool, List[float]]:
    """Return (ok, ungrounded_values). ok is True iff every numeric in
    `spec` appears (within power-of-ten tolerance) in `source_text`."""
    source_nums = _numbers_in_text(source_text)
    missing: List[float] = []
    for v in _walk_spec_numbers(spec):
        if not _value_matches_source(v, source_nums):
            missing.append(v)
    return (len(missing) == 0, missing)


def _poly_oracle_combined(
    situation: str,
    model: str,
    api_key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Single-step oracle: situation → [domain, spec] pairs.
    Faster (one call) but less accurate than the two-stage pipeline.
    Used when decompose=False.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return []
    parsed = _oracle_call(_COMBINED_SYSTEM, situation, model, key)
    if parsed and isinstance(parsed, dict):
        return [
            ds for ds in parsed.get("domains", [])
            if isinstance(ds, dict) and ds.get("domain") in _ALL_DOMAINS
        ]
    return []


# ── Umbrella-cluster splitting ─────────────────────────────────────────

def _cluster_domains(
    domain_specs: List[Dict[str, Any]],
) -> List[List[Dict[str, Any]]]:
    """Group domain specs into umbrella clusters.

    Domains belonging to the same umbrella are processed together as a
    cluster (sub-coordinator). Orphan domains that don't belong to any
    umbrella form their own single-item clusters. Clusters are returned
    largest-first so the highest-signal group runs first.
    """
    umbrella_buckets: Dict[str, List[Dict[str, Any]]] = {}
    orphans: List[Dict[str, Any]] = []

    for ds in domain_specs:
        domain = ds.get("domain", "")
        parent = _DOMAIN_UMBRELLA.get(domain)
        if parent:
            umbrella_buckets.setdefault(parent, []).append(ds)
        else:
            orphans.append(ds)

    clusters: List[List[Dict[str, Any]]] = sorted(
        umbrella_buckets.values(), key=len, reverse=True
    )
    # Append orphan clusters (one per domain)
    for orphan in orphans:
        clusters.append([orphan])

    return clusters


_KNOWN_VERDICTS = frozenset({"CONFIRMED", "MISMATCH", "NOT_APPLICABLE", "ERROR"})


def _extract_verdict(raw: Dict[str, Any]) -> Tuple[str, str]:
    """Normalise the return value of any verify_* tool into (verdict, detail).

    Verifiers return one of three shapes:
      1. Direct:  {"status": "CONFIRMED", "detail": "...", ...}
      2. Checks:  {"checks": [{"status": "...", "detail": "..."}, ...]}
         (packet-style — labor, economics, finance, music_theory, etc.)
      3. Nested:  {"equation": {"status": "...", "detail": "..."}, ...}
         (chemistry, some multi-result domains)

    Aggregation rule (highest severity wins):
      ERROR > MISMATCH > CONFIRMED > NOT_APPLICABLE > UNKNOWN
    """
    if not isinstance(raw, dict):
        return "UNKNOWN", str(raw)

    # Shape 1: direct top-level status
    s = raw.get("status")
    if s in _KNOWN_VERDICTS:
        return s, str(raw.get("detail", raw.get("message", "")))

    # Shape 2: checks list
    checks = raw.get("checks")
    if isinstance(checks, list) and checks:
        precedence = ["ERROR", "MISMATCH", "CONFIRMED", "NOT_APPLICABLE"]
        by_status: Dict[str, str] = {}
        for c in checks:
            if isinstance(c, dict) and c.get("status") in _KNOWN_VERDICTS:
                st = c["status"]
                if st not in by_status:
                    by_status[st] = str(c.get("detail", ""))
        for p in precedence:
            if p in by_status:
                return p, by_status[p]
        return "UNKNOWN", ""

    # Shape 3: nested sub-results (chemistry style)
    nested: List[Tuple[str, str]] = []
    for val in raw.values():
        if isinstance(val, dict) and val.get("status") in _KNOWN_VERDICTS:
            nested.append((val["status"], str(val.get("detail", ""))))
    if nested:
        precedence = ["ERROR", "MISMATCH", "CONFIRMED", "NOT_APPLICABLE"]
        by_status2: Dict[str, str] = {}
        for st, det in nested:
            if st not in by_status2:
                by_status2[st] = det
        for p in precedence:
            if p in by_status2:
                return p, by_status2[p]

    return "UNKNOWN", ""


def _run_cluster(
    cluster: List[Dict[str, Any]],
    all_tools: Dict[str, Any],
) -> List[DomainResult]:
    """Fire all workers in a cluster. Returns their results."""
    results: List[DomainResult] = []
    for entry in cluster:
        domain = entry.get("domain", "")
        spec = entry.get("spec") or {}
        if not domain or domain not in _ALL_DOMAINS:
            continue
        fn = all_tools.get(f"verify_{domain}")
        if fn is None:
            continue
        try:
            # Route by first-parameter name:
            #   spec-named → fn(spec)         (labor, economics, music_theory …)
            #   otherwise  → fn(**spec)       (chemistry, physics, mathematics …)
            # Oracle-extracted specs often contain extra keys the verifier
            # doesn't accept (verification_type, expected_result, etc.).
            # In the **spec path, filter to the verifier's signature so an
            # over-eager oracle doesn't crash the worker.
            try:
                params = inspect.signature(fn).parameters
                first_param = next(iter(params))
            except (ValueError, StopIteration):
                params, first_param = {}, "spec"
            if first_param == "spec":
                raw = fn(spec)
            else:
                accepts_kwargs = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in params.values()
                )
                if accepts_kwargs:
                    raw = fn(**spec)
                else:
                    accepted = set(params.keys())
                    filtered = {k: v for k, v in spec.items() if k in accepted}
                    raw = fn(**filtered)
        except Exception as exc:
            raw = {"status": "ERROR", "detail": str(exc)}

        raw = raw if isinstance(raw, dict) else {"raw": str(raw)}
        verdict, detail = _extract_verdict(raw)
        coords  = axis_coords_for(domain)
        dims    = coords.dimensions if coords else frozenset()

        results.append(DomainResult(
            domain=domain,
            spec=spec,
            result=raw,
            verdict=verdict,
            detail=detail,
            axis_dims=dims,
            source_claim=entry.get("_source_claim"),
        ))
    return results


# ── Public entry point ─────────────────────────────────────────────────

def run_polymathic(
    situation: str,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
    max_domains: int = 10,
    split_threshold: int = 5,
    stop_on_discordant: bool = False,
    decompose: bool = True,
) -> PolymathicRecord:
    """Run all applicable verifiers against a natural-language situation.

    Parameters
    ----------
    situation           Natural-language description of the situation.
    model               Oracle model for extraction.
    max_domains         Hard cap on total domains processed.
    split_threshold     When domain count exceeds this, split into umbrella
                        clusters (sub-coordinators). Each cluster is bounded;
                        compute stays predictable regardless of situation size.
    stop_on_discordant  Stop processing remaining clusters once DISCORDANT
                        is confirmed — no need to keep verifying.
    decompose           When True (default), use the two-stage pipeline:
                          1. decompose situation → atomic claims
                          2. classify each claim independently
                        More accurate; costs N+1 oracle calls instead of 1.
                        Set False for speed (combined single-call oracle).
    """
    from ..mcp_server.tools import ALL_TOOLS

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    atomic_claims: List[str] = []
    quarantined_claims: List[str] = []

    if decompose and key:
        # Decompose phase: situation → atomic claims
        atomic_claims = decompose_situation(situation, model, key)
        if atomic_claims:
            # Classify phase: classify each atomic claim
            domain_specs = classify_claims(atomic_claims, model, key, source_text=situation)
            # Any claim that didn't map to a domain → quarantine
            classified_claims = {ds.get("_source_claim") for ds in domain_specs if ds.get("_source_claim")}
            quarantined_claims = [c for c in atomic_claims if c not in classified_claims]
        else:
            domain_specs = _poly_oracle_combined(situation, model, key)
    else:
        domain_specs = _poly_oracle_combined(situation, model, key)

    domain_specs = domain_specs[:max_domains]

    # ── Step 2.5: axis-precedent lookup ──────────────────────────────────
    # Before firing verifiers, predict the scaffold dimensions from the
    # classified domains and query the sealed-record index. If a prior
    # PolymathicRecord shares significant axis overlap we surface it as a
    # structural overlay — the coordinator walks the well before dispatching.
    closest_precedent = None
    try:
        from ..axis_index import find_closest as _find_closest
        predicted_dims: set = set()
        for ds in domain_specs:
            coords = axis_coords_for(ds.get("domain", ""))
            if coords:
                predicted_dims.update(coords.dimensions)
        if predicted_dims:
            closest_precedent = _find_closest(list(predicted_dims))
    except Exception:
        pass  # index unavailable is non-fatal

    all_results: List[DomainResult] = []

    if len(domain_specs) > split_threshold:
        # Coordinator delegates to umbrella sub-coordinators (bounded compute)
        clusters = _cluster_domains(domain_specs)
        for cluster in clusters:
            cluster_results = _run_cluster(cluster, ALL_TOOLS)
            all_results.extend(cluster_results)
            if stop_on_discordant:
                interim_weights = compute_axis_weights(all_results)
                if compute_weighted_composite_verdict(all_results, interim_weights) == DISCORDANT:
                    break
    else:
        all_results = _run_cluster(domain_specs, ALL_TOOLS)

    # Keeper pass — ultra-low-power triage of the quarantine queue.
    # Recovers any quarantined claims that now match a dispatch rule,
    # and organizes orphans by proximity. No oracle calls.
    keeper_manifest = None
    recovered_results: List[DomainResult] = []
    final_quarantined = list(quarantined_claims)

    if quarantined_claims:
        keeper_manifest = tend_quarantine(quarantined_claims)
        # Run recovered claims through the verifiers and add to results
        if keeper_manifest.recovered:
            recovered_specs = [
                {"domain": r.domain, "spec": r.spec, "_source_claim": r.claim}
                for r in keeper_manifest.recovered
            ]
            recovered_results = _run_cluster(recovered_specs, ALL_TOOLS)
            all_results.extend(recovered_results)
            # Only true orphans remain in quarantine
            final_quarantined = [o.claim for o in keeper_manifest.orphans]

    axis_overlaps = compute_axis_overlaps(all_results)

    # Axis-weighted synthesis: peripheral domains (low structural overlap)
    # don't get to veto the composite verdict on their own.
    axis_weights  = compute_axis_weights(all_results)
    composite     = compute_weighted_composite_verdict(
        all_results,
        weights=axis_weights,
        quarantined_claims=final_quarantined or None,
    )

    # Collect phase: full provenance — situation, atomic claims, keeper triage, verifier results
    return PolymathicRecord(
        situation=situation,
        atomic_claims=tuple(atomic_claims),
        quarantined_claims=tuple(final_quarantined),
        keeper_manifest=keeper_manifest.to_dict() if keeper_manifest else None,
        closest_precedent=closest_precedent,
        axis_weights=axis_weights,
        domain_results=tuple(all_results),
        axis_overlaps=tuple(axis_overlaps),
        composite_verdict=composite,
    )
