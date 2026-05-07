"""Polymathic Agent — Path C. The Hive.

Architecture: workers, drones, queens.
  * verify_* functions   = workers  (one domain, deterministic)
  * dispatch rules       = drones   (carry NL to the right worker)
  * poly_agent           = queen    (coordinates all workers, synthesizes)

The queen receives a situation, identifies all applicable workers via
the oracle, and fires them. She can split the work into umbrella
clusters — sub-queens for related domain groups — so compute stays
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
from typing import Any, Dict, List, Optional, Tuple

from ..grid import UMBRELLAS, AXIS_DIMENSIONS
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
    'Return ONLY valid JSON: {"claims": ["claim 1", "claim 2", ...]}'
)

_CLASSIFY_SYSTEM = (
    "You are a domain classifier for the Concordance verification engine. "
    "Given a single atomic claim, identify the ONE best domain and extract the verifier spec. "
    "Valid domains: " + ", ".join(_ALL_DOMAINS) + ". "
    "For physics: use physics_dimensional (equation + symbol units) or physics_conservation "
    "(before/after quantities). For statistics: use statistics_pvalue, "
    "statistics_multiple_comparisons, or statistics_confidence_interval. "
    "For governance decisions: use governance_decision_packet. "
    'Return ONLY valid JSON: {"domain": "<name>", "spec": {<verifier fields>}}. '
    "If no domain matches with enough specificity, return null."
)

_COMBINED_SYSTEM = (
    "You are a multi-domain classifier for the Concordance verification engine. "
    "Given a situation, identify ALL domains that are concretely applicable "
    "AND for which you can extract a verifiable spec from the text. "
    "Valid domains: " + ", ".join(_ALL_DOMAINS) + ". "
    "For physics: use physics_dimensional or physics_conservation. "
    "For statistics: use statistics_pvalue, statistics_multiple_comparisons, or "
    "statistics_confidence_interval. "
    'Return ONLY valid JSON: {"domains": [{"domain": "<name>", "spec": {<verifier fields>}}, ...]}. '
    "Include a domain only if the text contains enough concrete detail. Nothing except JSON."
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
    claims, each verifiable by a single domain worker. The decomposition
    is stored separately so the queen can inspect the breakdown before
    dispatching workers.
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
) -> List[Dict[str, Any]]:
    """Step 2 of the two-stage pipeline: atomic claims → domain specs.

    Classifies each atomic claim independently — one oracle call per
    claim. More accurate than combined classification because the oracle
    focuses on one claim at a time with no cross-claim interference.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return []
    results: List[Dict[str, Any]] = []
    for claim in claims:
        parsed = _oracle_call(_CLASSIFY_SYSTEM, claim, model, key, max_tokens=256)
        if parsed and isinstance(parsed, dict) and "domain" in parsed:
            d = parsed.get("domain", "")
            spec = parsed.get("spec") or {}
            if d and d in _ALL_DOMAINS:
                results.append({"domain": d, "spec": spec, "_source_claim": claim})
    return results


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
    cluster (sub-queen). Orphan domains that don't belong to any umbrella
    form their own single-item clusters. Clusters are returned largest-first
    so the highest-signal group runs first.
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
            try:
                first_param = next(iter(inspect.signature(fn).parameters))
            except (ValueError, StopIteration):
                first_param = "spec"
            if first_param == "spec":
                raw = fn(spec)
            else:
                raw = fn(**spec)
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
                        clusters (sub-queens). Each cluster is bounded;
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
        # Strip phase: situation → atomic claims
        atomic_claims = decompose_situation(situation, model, key)
        if atomic_claims:
            # Send phase: classify each stripped claim
            domain_specs = classify_claims(atomic_claims, model, key)
            # Any claim that didn't map to a domain → quarantine (airlock)
            classified_claims = {ds.get("_source_claim") for ds in domain_specs if ds.get("_source_claim")}
            quarantined_claims = [c for c in atomic_claims if c not in classified_claims]
        else:
            domain_specs = _poly_oracle_combined(situation, model, key)
    else:
        domain_specs = _poly_oracle_combined(situation, model, key)

    domain_specs = domain_specs[:max_domains]

    # ── Step 2.5: axis-precedent lookup ──────────────────────────────────
    # Before firing workers, predict the scaffold dimensions from the
    # classified domains and query the sealed-record index. If a prior
    # PolymathicRecord shares significant axis overlap we surface it as a
    # structural overlay — the queen walks the well before dispatching.
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
        # Queen delegates to umbrella sub-queens (bounded compute)
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

    # Keeper pass — ultra-low-power triage of the airlock
    # Recovers any quarantined claims that now match a dispatch rule,
    # and organizes orphans by proximity. No oracle calls.
    keeper_manifest = None
    recovered_results: List[DomainResult] = []
    final_quarantined = list(quarantined_claims)

    if quarantined_claims:
        keeper_manifest = tend_quarantine(quarantined_claims)
        # Run recovered claims as workers and add to results
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

    # Wrap phase: full provenance — situation, strips, keeper triage, results
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
