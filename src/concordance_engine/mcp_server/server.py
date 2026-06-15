"""MCP server exposing the Concordance Engine verifier layer.

Run as:
    python -m concordance_engine.mcp_server
or after install:
    concordance-mcp

Configure Claude Desktop with:
{
  "mcpServers": {
    "concordance": {
      "command": "concordance-mcp"
    }
  }
}

Or for development from the source tree:
{
  "mcpServers": {
    "concordance": {
      "command": "python",
      "args": ["-m", "concordance_engine.mcp_server"],
      "env": {"PYTHONPATH": "/path/to/Lighthouse/lw/01_engine/concordance-engine/src"}
    }
  }
}

This file requires the `mcp` package (mcp >= 1.0.0). Install via:
    pip install -e ".[mcp]"

Environment variables:
    CONCORDANCE_API_URL   - Hosted API base URL (no default). When set
                            with CONCORDANCE_API_KEY, validate_packet
                            calls the hosted ledger first.
    CONCORDANCE_API_KEY   - API key for authenticated endpoints. Both
                            URL and key must be set for the hosted
                            path; otherwise local-only.
"""
from __future__ import annotations

import json
import os
import re
import time as _time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as e:
    raise ImportError(
        "MCP SDK not installed. Run: pip install -e \".[mcp]\" "
        "from the concordance-engine directory."
    ) from e

from . import tools
from .. import IDENTITY_SHORT

# FastMCP carries an instructions block that's surfaced to MCP clients
# during initialize(). Use it to plainly state what this engine serves.
# Per Matt 2026-05-03: "we don't want to completely block agents.
# However we are clear that we serve Jesus Christ." Agents can call any
# tool here; the engine flows for legitimate use. The doctrine is
# stated up front so callers know.
_MCP_INSTRUCTIONS = (
    "Concordance / Lighthouse — Serves Jesus Christ. "
    "START HERE: to verify anything, call ONE tool — `check`. It takes a math "
    "claim, a multi-step derivation, or a plain-language statement, and returns "
    "the verdict, the WORKED MATH (the trail, step by step), and a permanent, "
    "re-checkable seal (cite_url) you can show a user. The many domain-specific "
    "`verify_*` tools are its internals; reach for them only for a single narrow "
    "domain check. "
    "Conduit, not source. The engine eliminates what is not the answer "
    "so the narrow path is illuminated by what survives. Good fruit is "
    "the measure. The keeping is the substrate. Tools here categorize, "
    "verify, and surface precedent — they do not generate answers or "
    "render verdicts. Read the elimination trail; the trail is the "
    "reasoning. Full statement: GET https://narrowhighway.com/identity"
)

mcp = FastMCP("concordance", instructions=_MCP_INSTRUCTIONS)

# Hosted API. Both URL and key come from the environment — the source
# carries no defaults so a deployment without env vars fails closed
# (skips the API path entirely and uses local computation), and a
# rotated key isn't sitting as a literal in the codebase. Set
# CONCORDANCE_API_URL and CONCORDANCE_API_KEY to enable the hosted path.
CONCORDANCE_API_URL: Optional[str] = os.environ.get("CONCORDANCE_API_URL")
CONCORDANCE_API_KEY: Optional[str] = os.environ.get("CONCORDANCE_API_KEY")


# ---------------------------------------------------------------------------
# Full engine
# ---------------------------------------------------------------------------

@mcp.tool()
def validate_packet(packet: Dict[str, Any], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """Run all four gates against a decision or claim packet: RED, FLOOR, BROTHERS, GOD.

    RED     -- Rejects coercion, unilateral authority, rights violations, hard computational failures.
    FLOOR   -- Rejects structurally incomplete or internally inconsistent packets.
    BROTHERS -- Quarantines if insufficient witnesses or review window has not elapsed.
    GOD     -- Records permanently in the append-only ledger if all prior gates pass.

    Attempts the hosted API first (writes to the Audit Chain) when
    both CONCORDANCE_API_URL and CONCORDANCE_API_KEY are configured;
    falls back to local computation otherwise. With no API config, the
    local path is the only path — no environment-dependent default
    URL, no embedded key.

    Returns: {overall: PASS|QUARANTINE|REJECT, gate_results: [...]}.
    """
    # Hosted path requires BOTH url and key — refuse to authenticate
    # against an unconfigured API or send unauthenticated requests to
    # a configured one.
    if CONCORDANCE_API_URL and CONCORDANCE_API_KEY:
        try:
            pkt = {**packet}
            if "created_epoch" not in pkt:
                pkt["created_epoch"] = now_epoch or int(_time.time())
            payload = json.dumps({"packet": pkt}).encode()
            headers = {
                "Content-Type": "application/json",
                "x-api-key": CONCORDANCE_API_KEY,
            }
            req = urllib.request.Request(
                f"{CONCORDANCE_API_URL.rstrip('/')}/validate",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                api_result = json.loads(resp.read().decode())
            api_result["_source"] = "api"
            return api_result
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            pass
    out = tools.validate_packet(packet, now_epoch)
    out["_source"] = "local"
    return out


# ---------------------------------------------------------------------------
# Sealed records — agent + human surfaces over the same WitnessRecord
# ---------------------------------------------------------------------------

@mcp.tool()
def seal_packet(
    packet: Dict[str, Any],
    now_epoch: Optional[int] = None,
    auto_precedent: bool = False,
) -> Dict[str, Any]:
    """Run a packet through the four gates and return the sealed
    WitnessRecord as JSON.

    The canonical agent surface: every gate verdict, every verifier
    result, axis coordinates on the dimensional scaffold, citations
    with source-hierarchy `layer`, optional closest-case overlay. No
    `final_answer` field anywhere — the engine categorizes, it does
    not answer.

    auto_precedent: when True, look up the closest comparable
    precedent in the Audit Chain and seal it into the record.
    Honors discovery-not-design: empty ledger and zero-overlap both
    return precedent_id=None rather than fabricating a match.
    """
    return tools.seal_packet(packet, now_epoch=now_epoch,
                              auto_precedent=auto_precedent)


@mcp.tool()
def walkthrough_packet(
    packet: Dict[str, Any],
    now_epoch: Optional[int] = None,
    format: str = "markdown",
    expand_traces: bool = False,
    auto_precedent: bool = False,
) -> str:
    """Run a packet and return a human-readable walkthrough.

    format: "markdown" (Socratic walk, default) | "compact" (one-screen
    status) | "html" (self-contained HTML page).

    expand_traces=True adds the verifier trace section to markdown and
    HTML outputs — formula, rule, and full data payload per check.

    auto_precedent=True pulls the closest comparable precedent before
    sealing, so the walkthrough's closest-case section renders an
    actual precedent rather than being omitted.

    The walkthrough always ends on a Socratic question. No fabricated
    answer field appears in any format.
    """
    return tools.walkthrough_packet(
        packet,
        now_epoch=now_epoch,
        fmt=format,
        expand_traces=expand_traces,
        auto_precedent=auto_precedent,
    )


# ---------------------------------------------------------------------------
# Chemistry
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_chemistry(
    equation: Optional[str] = None,
    temperature_K: Optional[float] = None,
    pH: Optional[float] = None,
    claimed_classification: Optional[str] = None,
    neutral_tolerance: Optional[float] = None,
    delta_H_kJ_mol: Optional[float] = None,
    delta_S_J_mol_K: Optional[float] = None,
    claimed_spontaneous: Optional[bool] = None,
) -> Dict[str, Any]:
    """Verify chemistry claims. Three independent checks, any subset may be supplied.

    1. Equation balance (atoms and charge) + optional physical temperature:
       equation='2 H2 + O2 -> 2 H2O', temperature_K=298. Supports nested groups
       (Cu(OH)2), charges (Fe^2+, MnO4^-), and ionic forms. On MISMATCH, returns
       the correctly balanced coefficients in data.balanced_lhs / balanced_rhs.
    2. pH classification: pH=3, claimed_classification='acid'|'base'|'neutral'
       (optional neutral_tolerance, default 0.5 around pH 7).
    3. Thermodynamic feasibility (Gibbs ΔG = ΔH - TΔS): delta_H_kJ_mol,
       delta_S_J_mol_K, temperature_K, claimed_spontaneous (a reaction is
       spontaneous iff ΔG < 0).

    Returns a dict keyed by check name, each value carrying status/detail/data.
    """
    return tools.verify_chemistry(
        equation,
        temperature_K,
        pH=pH,
        claimed_classification=claimed_classification,
        neutral_tolerance=neutral_tolerance,
        delta_H_kJ_mol=delta_H_kJ_mol,
        delta_S_J_mol_K=delta_S_J_mol_K,
        claimed_spontaneous=claimed_spontaneous,
    )


# ---------------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_physics_dimensional(equation: str, symbols: Dict[str, str]) -> Dict[str, Any]:
    """Verify both sides of a physics equation reduce to the same SI dimensions.

    symbols maps each variable to its named unit
    (e.g. {"F": "newton", "m": "kilogram", "a": "meter/second**2"}).
    Both sides are converted to base SI units and compared.
    """
    return tools.verify_physics_dimensional(equation, symbols)


@mcp.tool()
def verify_physics_conservation(
    before: Dict[str, float],
    after: Dict[str, float],
    tolerance_relative: float = 1e-6,
    tolerance_absolute: float = 0.0,
) -> Dict[str, Any]:
    """Verify each named conserved quantity is preserved within tolerance.

    before and after are dicts of quantity_name -> numeric_value.
    A quantity passes if its relative change <= tolerance_relative OR
    its absolute change <= tolerance_absolute.
    """
    return tools.verify_physics_conservation(before, after, tolerance_relative, tolerance_absolute)


# ---------------------------------------------------------------------------
# Mathematics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_mathematics(mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Sympy-based math verification across nine modes.

    mode: equality | derivative | integral | limit | solve | matrix | inequality | series | ode

    params per mode:
      equality:    {expr_a, expr_b, variables: [...]}
      derivative:  {function, variable, claimed_derivative}
      integral:    {integrand, variable, claimed_antiderivative}
      limit:       {function, variable, point, claimed_limit}
      solve:       {equation, variable, claimed_solutions: [...]}
    """
    return tools.verify_mathematics(mode, params)


# ---------------------------------------------------------------------------
# THE one tool — start here
# ---------------------------------------------------------------------------

@mcp.tool()
def check(
    claim: Optional[str] = None,
    steps: Optional[List[Dict[str, Any]]] = None,
    mode: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
    domain: str = "mathematics",
    seal: bool = True,
) -> Dict[str, Any]:
    """THE verification tool — start here. One tool for every kind of check; it
    always shows the WORKED MATH and gives a permanent, re-checkable seal.

    Give exactly one of:
      - steps: a multi-step derivation, list of {id, domain, spec, uses?, claim?}
        (each step's spec is that domain's structured claim; math spec is {mode, params}).
      - mode + params (+ domain): a single claim. Math modes:
        equality|derivative|integral|limit|solve|matrix|inequality|series|ode.
        e.g. mode='equality',
        params={'expr_a':'(x+1)**2','expr_b':'x**2+2*x+1','variables':['x']}.
      - claim: a plain-language statement; the oracle structures it, the engine judges.

    Returns {verdict (HOLDS/BROKEN/INCOMPLETE), confirmed_steps,
             trail:[{id, domain, status, detail = THE WORKED MATH, uses}],
             seal:{cite_url, content_hash}}. The engine verifies a PROVIDED claim;
    it never generates the answer. The trail is the proof — open the cite_url to
    see it rendered and re-check it without trusting anyone.
    """
    return tools.check(claim=claim, steps=steps, mode=mode, params=params,
                       domain=domain, seal=seal)


@mcp.tool()
def verify_giving(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Conservation of a giving / value-transfer chain -- prove every dollar is
    accounted for from the donor all the way to the END USER, with no leakage or
    skim. The conservation law (a balanced equation; a closed system) applied to
    money: what goes in must come out as fees + what is delivered.

    spec = {
      "source": 1000.00,                 # what the donor gave
      "links": [{"name":"platform","fee":30}, {"name":"charity","fee":120}],
      "delivered": 800.00,               # what reached the end user
      "claimed_delivered_fraction": 0.80,# optional efficiency to check
      "tolerance": 0.01                  # optional, default one penny
    }

    CONFIRMED iff source == sum(fees) + delivered (within tolerance). On a
    shortfall it reports the UNACCOUNTED leak; it always reports what fraction
    reached the end user. "Never trust, always verify" for giving -- the giver
    gets a result re-checkable without trusting any middleman.
    """
    return tools.verify_giving(spec)


@mcp.tool()
def language_data(query: str) -> Dict[str, Any]:
    """Phoneme inventory + language family + world region for a language, from the
    offline PHOIBLE 2.0 + Glottolog index (external Layer-0 source, attributed --
    CC-BY-SA PHOIBLE / CC-BY Glottolog).

    query = a language name ("Korean"), an ISO 639-3 code ("kor"), or a Glottocode
    ("kore1280"). Returns {name, glottocode, iso, family, macroarea, lat, lon,
    n_phonemes, n_consonants, n_vowels, n_tones, consonants[], vowels[], tones[]}.
    Covers ~2,177 languages. Use it to ground a claim about a language's sounds or
    its place in the family tree (the phoneme half of the dispersal map).
    """
    return tools.language_data(query)


@mcp.tool()
def wikidata(query: str) -> Dict[str, Any]:
    """Look up an entity on Wikidata (CC0 public domain) by label and return key facts.

    query = an entity label ("Photosynthesis", "Mount Everest", "Koine Greek").
    Returns {qid, label, description, instance_of[], facts:[{property, value}], url}.
    Live SPARQL/API query, cached offline so common lookups survive without a network.
    External Layer-0 -- attributed, crowd-sourced (CONCORDANT-grade, NOT a HOLDS): a
    starting reference to verify against the deterministic sources, never proof itself.
    """
    return tools.wikidata(query)


@mcp.tool()
def word_meaning(word: str) -> Dict[str, Any]:
    """English lexical semantics from the offline Princeton WordNet 3.1 database
    (external Layer-0 source, attributed).

    word -> {senses: [{pos, definition, synonyms[], hypernyms[]}]}. The hypernyms
    are the is-a parents (the semantic 'tree'). This is the SEMANTICS level of the
    language tree -- it pairs with word_study (original Greek/Hebrew morphology) and
    language_data (phoneme inventories). 147,478 lemmas, queried offline from SQLite.
    """
    return tools.word_meaning(word)


@mcp.tool()
def place_lookup(name: str, limit: int = 8) -> Dict[str, Any]:
    """Gazetteer lookup from the offline GeoNames cities5000 database (external
    Layer-0 source, attributed).

    name -> {matches: [{name, admin1, country, lat, lon, population, feature,
    timezone}]}, ordered by population so the most prominent place is first and
    same-named places are disambiguated by size. Serves the local-community layer
    ("group you by your area") and basic geography. 69,133 populated places with
    population >= 5000, queried offline from SQLite. Data (c) GeoNames.org, CC-BY 4.0.
    """
    return tools.place_lookup(name, limit)


@mcp.tool()
def timezone_offset(zone: str, when: str = "") -> Dict[str, Any]:
    """UTC offset + daylight-saving state for an IANA time zone at an instant,
    from the offline IANA Time Zone Database (external Layer-0, PUBLIC DOMAIN).

    zone = an IANA name like "Asia/Tokyo" or "America/New_York" (use place_lookup
    to get a place's zone name from its 'timezone' field). when = optional ISO
    date or datetime (default: now). Returns {utc_offset, offset_seconds,
    abbreviation, is_dst} -- a deterministic rule fact computed from the tzdb
    rules, not invented. Completes the calendar_time grounding and pairs with
    place_lookup (place -> zone -> offset) for "what time is it in X".
    """
    return tools.timezone_offset(zone, when or None)


@mcp.tool()
def unit_convert(value: float, from_unit: str, to_unit: str = "") -> Dict[str, Any]:
    """Deterministic unit conversion via the offline UCUM table (external Layer-0,
    royalty-free, attributed).

    from_unit / to_unit are UCUM codes or expressions: "km", "m/s", "kg.m/s2",
    "[mi_i]" (international mile), "[lb_av]" (pound), "Cel", "[degF]". Omit
    to_unit to get the value in canonical base units. Affine temperatures (Cel,
    [degF], [degR], K) are handled with offsets. Incommensurable units are
    REPORTED, not forced; an unparseable or non-linear unit returns 'unsupported'
    -- the converter FAILS CLOSED rather than guess (a wrong conversion is worse
    than none). This is the units substrate beneath every dimensional check.
    """
    return tools.unit_convert(value, from_unit, to_unit or None)


@mcp.tool()
def sequence_lookup(anum: str = "", terms: list = None, limit: int = 8) -> Dict[str, Any]:
    """Identify or look up an integer sequence in the offline OEIS index (external
    Layer-0, attributed, CC BY-SA).

    Either anum (e.g. "A000045" or 45) -> {name, terms}; or terms (a list like
    [1,1,2,3,5,8], at least 3) -> the OEIS sequences whose terms contain that run,
    lowest A-number (most canonical) first. OEIS is a curated/crowd-sourced
    reference: a term match IDENTIFIES a sequence (CONCORDANT-grade) -- it does
    not PROVE the defining property. Grounds number_theory / combinatorics claims.
    """
    return tools.sequence_lookup(anum or None, terms, limit)


@mcp.tool()
def word_pronunciation(word: str) -> Dict[str, Any]:
    """Pronunciation of an English word from the offline CMU Pronouncing
    Dictionary (external Layer-0, attributed, BSD-2).

    word -> each pronunciation variant as {arpabet, ipa, syllable_count,
    stress_pattern}. ARPABET is CMU's authoritative transcription; IPA is a
    deterministic segmental transliteration; stress_pattern lists the vowel
    stresses (1 primary, 2 secondary, 0 none). This is the PHONICS level of the
    language tree -- it pairs with language_data (phoneme inventories),
    word_meaning (semantics), and word_study (original-language morphology).
    ~126,000 words, queried offline from SQLite.
    """
    return tools.word_pronunciation(word)


@mcp.tool()
def port_lookup(query: str, protocol: str = "") -> Dict[str, Any]:
    """Look up an internet port or service in the offline IANA Service Name and
    Transport Protocol Port Number Registry (external Layer-0, public domain).

    query = a port NUMBER (e.g. 443 -> the services on it, like https) OR a
    service NAME (e.g. "ssh" -> port 22). Optional protocol filters to
    tcp/udp/sctp/dccp. The authoritative "what runs on port N" / "what port does
    X use" for the networking verifier.
    """
    return tools.port_lookup(query, protocol or None)


@mcp.tool()
def rfc_lookup(number: str) -> Dict[str, Any]:
    """Look up an RFC in the offline RFC Index (external Layer-0, public domain).

    number = an RFC number (9113, "RFC9113", "rfc 9113") -> {doc_id, title,
    current_status, date, obsoletes, obsoleted_by, updates, updated_by, url}. If
    the RFC has been obsoleted, 'superseded_by' is set prominently so a dead RFC
    is never cited as current (e.g. RFC 7540 -> superseded by RFC 9113). The
    authoritative "which RFC defines X" for networking / cryptography.
    """
    return tools.rfc_lookup(number)


@mcp.tool()
def star_lookup(name: str = "", constellation: str = "", limit: int = 6) -> Dict[str, Any]:
    """Look up a star in the offline HYG stellar catalog (external Layer-0,
    attributed, CC BY-SA).

    name = a proper name (e.g. "Betelgeuse") -> its constellation, apparent/
    absolute magnitude, spectral type, distance (ly + pc), and position; OR
    constellation = a name or IAU abbreviation (e.g. "Orion" or "Ori") -> the
    brightest stars in it (lowest apparent magnitude first). Grounds astronomy
    claims like "Betelgeuse is in Orion" or "Sirius is the brightest star".
    Measurements are reported as the HYG catalog (Hipparcos/Yale/Gliese) gives
    them. 119,626 stars, queried offline.
    """
    return tools.star_lookup(name or None, constellation or None, limit)


@mcp.tool()
def fluid_property(fluid: str, output: str, input1_name: str = "",
                   input1_value: float = 0.0, input2_name: str = "",
                   input2_value: float = 0.0) -> Dict[str, Any]:
    """Thermophysical property of a fluid, computed deterministically by CoolProp
    (IAPWS-IF97 for water + Helmholtz-energy equations of state for 100+ fluids;
    external, MIT-licensed, attributed).

    Two-state form: fluid_property("Water","T","P",101325,"Q",0) = the boiling
    point at 1 atm (373.12 K). Trivial form (omit the state inputs):
    fluid_property("Water","Tcrit") = critical temperature. Property codes (SI):
    T=K, P=Pa, D=density kg/m^3, H=J/kg, S=J/kg/K, Q=vapor quality 0..1, C=cp,
    Tcrit/Pcrit, M=molar mass kg/mol, V=viscosity Pa*s, L=conductivity W/m/K,
    A=speed of sound m/s. FAILS CLOSED: an unknown fluid, unsupported state, or
    out-of-range input returns 'unsupported' (never a guess).
    """
    return tools.fluid_property(fluid, output, input1_name or None, input1_value,
                                input2_name or None, input2_value)


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_statistics_pvalue(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute a p-value from raw inputs and verify against claimed_p.

    Supports twelve test types — pass spec.test as one of:
      two_sample_t, one_sample_t, paired_t, z, chi2, f,
      one_proportion_z, two_proportion_z, fisher_exact,
      mannwhitney, wilcoxon_signed_rank, regression_coefficient_t.

    Plus the corresponding inputs. Optional: claimed_p (to verify),
    tolerance (default 1e-3), tail ("one"|"two").

    Examples:
      Paired t:  spec={"test":"paired_t","n":20,"mean_diff":0.5,"sd_diff":1.0,"tail":"two","claimed_p":0.0375}
      Fisher:    spec={"test":"fisher_exact","table":[[8,2],[1,9]],"claimed_p":0.005}
      MW-U:      spec={"test":"mannwhitney","x":[1,2,3,4],"y":[3,4,5,6,7],"claimed_p":0.111}
      Reg coef:  spec={"test":"regression_coefficient_t","beta":2.5,"se":0.8,"n":50,"k":3,"claimed_p":0.003}
    """
    return tools.verify_statistics_pvalue(spec)


@mcp.tool()
def verify_statistics_multiple_comparisons(
    raw_p_values: List[float],
    method: str,
    alpha: float = 0.05,
    claimed_rejected_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Apply a multiple-comparisons correction to a vector of raw p-values
    and verify the rejection set at alpha matches the claim, if provided.

    method: "bonferroni" | "holm" | "bh" (Benjamini-Hochberg FDR).
    Returns the corrected p-values and the indices the method rejects.

    Example:
      raw_p_values=[0.001, 0.012, 0.04, 0.5], method="bh", alpha=0.05,
      claimed_rejected_indices=[0, 1, 2]
    """
    return tools.verify_statistics_multiple_comparisons(
        raw_p_values, method, alpha, claimed_rejected_indices
    )


@mcp.tool()
def verify_statistics_confidence_interval(
    estimate: float, ci_low: float, ci_high: float
) -> Dict[str, Any]:
    """Verify a CI is well-formed (low <= high) and contains the point estimate."""
    return tools.verify_statistics_confidence_interval(estimate, ci_low, ci_high)


# ---------------------------------------------------------------------------
# Computer Science
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_computer_science(
    code: str,
    function_name: Optional[str] = None,
    test_cases: Optional[List[Dict[str, Any]]] = None,
    input_generator: Optional[str] = None,
    claimed_class: Optional[str] = None,
    sizes: Optional[List[int]] = None,
    tolerance: float = 0.40,
) -> Dict[str, Any]:
    """Verify Python code: static termination, functional correctness, runtime complexity.

    Always runs static termination scan. If function_name + test_cases are
    given, executes each test case in a restricted namespace and compares
    outputs. If function_name + input_generator + claimed_class are given,
    times the function at log-spaced sizes and verifies the O() class.

    Code runs in a restricted namespace: no __import__, open, eval, exec.
    """
    return tools.verify_computer_science(
        code, function_name, test_cases, input_generator,
        claimed_class, sizes, tolerance
    )


# ---------------------------------------------------------------------------
# Biology (standard + nested health control systems)
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_biology(
    n_replicates: Optional[int] = None,
    min_replicates: int = 3,
    assay_classes: Optional[List[str]] = None,
    min_assay_classes: int = 2,
    dose_response: Optional[Dict[str, Any]] = None,
    power_analysis: Optional[Dict[str, Any]] = None,
    bio_control: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run biology checks: replicate count, assay diversity, dose-response
    monotonicity, sample-size power, and nested health control systems.

    Standard checks (any combination):
      n_replicates + min_replicates -- replicate count adequacy
      assay_classes + min_assay_classes -- orthogonal assay diversity
      dose_response -- {doses, responses, expected_direction}
      power_analysis -- {effect_size, alpha, n_per_group, [target_power]}

    Health control systems check (bio_control dict):
      failure_mode: setpoint_drift | loop_saturation | compensation_collapse |
                    cross_layer_override | sensor_failure
      failure_layer: L1 | L2 | L3 | L4 | L5 | L6
      intervention_layers: [L1, L3, ...]
      upper_layer_driver_addressed: bool  (required for cross_layer_override)
      setpoint_shift_mechanism_stated: bool  (required for setpoint_drift)
      sensor_recalibration_plan: bool  (required for sensor_failure)

    Returns: {checks: [{status, detail, data}, ...]}
    """
    return tools.verify_biology(
        n_replicates, min_replicates, assay_classes, min_assay_classes,
        dose_response, power_analysis, bio_control=bio_control
    )


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_governance_decision_packet(
    decision_packet: Dict[str, Any],
    witness_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Verify a governance / business / household / education / church decision packet.

    Required fields: title, scope (adapter|local|mesh|canon|kernel), red_items,
    floor_items, way_path, execution_steps, witnesses.

    Optional: scripture_anchors, wait_window_seconds.

    If witness_count is provided, also checks DECISION_PACKET.witnesses length matches.
    """
    return tools.verify_governance_decision_packet(decision_packet, witness_count)


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_energy(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Verify energy-system claims at the system scale: off-grid sizing,
    power balance, battery + solar yield, voltage drop, efficiency, runtime.

    Per kingdom-economy substrate doctrine: those refusing the mark may
    need off-grid power. This verifier turns napkin arithmetic into
    deterministic verification.

    `spec` is the contents of ENERGY_VERIFY (see verifiers/energy.py for
    the full field reference). Provide whichever subset you want checked;
    unsupplied checks return NOT_APPLICABLE.

    Sub-checks:
      energy.power_balance         — gen − cons − losses = balance
      energy.battery_sizing        — Ah from kWh × days / (V × DoD)
      energy.solar_daily_yield     — kWh/day from panel × PSH × η
      energy.wire_voltage_drop     — DC drop across length at I
      energy.kwh_wh_consistency    — kWh × 1000 = Wh
      energy.efficiency            — η = output/input (≤1.0 unless heat pump)
      energy.runtime               — battery_Wh / load_W
      energy.peak_load_vs_inverter — peak ≤ inverter continuous rating
    """
    return tools.verify_energy(spec)


# ---------------------------------------------------------------------------
# Extended domain verifiers (all 37 domains now wired)
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_acoustics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Wave speed/frequency/wavelength (v=fλ), decibel ratios (dB SPL/IL),
    Doppler shift, harmonic frequency series.
    Pass spec as ACOUS_VERIFY contents.
    Wave: spec={"frequency_hz":440,"wavelength_m":0.78,"claimed_speed_m_per_s":343}
    dB:   spec={"intensity_W_per_m2":1e-4,"claimed_dB_SPL":80}
    Doppler: spec={"source_freq_hz":500,"velocity_source_m_per_s":30,"observer_stationary":true,"claimed_observed_hz":548.7}"""
    return tools.verify_acoustics(spec)


@mcp.tool()
def verify_agriculture(spec: Dict[str, Any]) -> Dict[str, Any]:
    """USDA plant hardiness zone lookup, soil pH range for named crops,
    crop rotation compatibility, livestock stocking density.
    Pass spec as AG_VERIFY contents."""
    return tools.verify_agriculture(spec)


@mcp.tool()
def verify_astronomy(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Kepler's third law (T²∝a³), Newton gravitational force, stellar
    parallax distance, distance modulus (m-M=5log₁₀(d/10pc)).
    Pass spec as ASTRO_VERIFY contents."""
    return tools.verify_astronomy(spec)


@mcp.tool()
def verify_calendar_time(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Gregorian leap-year rule, ISO 8601 datetime validity,
    day-of-week computation (Zeller/Tomohiko), duration addition.
    Pass spec as CAL_VERIFY contents."""
    return tools.verify_calendar_time(spec)


@mcp.tool()
def verify_combinatorics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Permutations P(n,k), combinations C(n,k), derangements D(n),
    multinomial coefficients.
    Pass spec as COMB_VERIFY contents."""
    return tools.verify_combinatorics(spec)


@mcp.tool()
def verify_cryptography(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Hash match, hash strength (NIST), HMAC, base64/hex encoding roundtrip, key-length strength.
    Pass spec as CRYPTO_VERIFY contents.
    Hash match:    spec={"hash_algorithm":"sha256","data":"hello","claimed_hash_hex":"2cf24dba..."}
    Hash strength: spec={"hash_strength_algorithm":"md5","claimed_hash_strength":"broken"}
    HMAC:          spec={"hmac_algorithm":"sha256","hmac_key":"secret","hmac_data":"hello","claimed_hmac_hex":"..."}
    Key strength:  spec={"cipher":"AES","key_bits":256,"claimed_key_strength":"strong"}"""
    return tools.verify_cryptography(spec)


@mcp.tool()
def verify_document_validation(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Governance document structural check: required fields present,
    date ordering valid, signatory consistency.
    Pass spec as DOC_VERIFY contents."""
    return tools.verify_document_validation(spec)


@mcp.tool()
def verify_electrical(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Ohm's law (V=IR), power equations (P=VI/I²R/V²/R),
    Kirchhoff voltage loop sum, RC time constant (τ=RC).
    Pass spec as ELEC_VERIFY contents."""
    return tools.verify_electrical(spec)


@mcp.tool()
def verify_exercise_science(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Energy expenditure (MET×kg×hours×0.0175), max heart rate (220−age),
    target HR zone (Karvonen), MET activity lookup.
    Pass spec as EX_VERIFY contents."""
    return tools.verify_exercise_science(spec)


@mcp.tool()
def verify_finance(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Accounting identity (Assets=Liabilities+Equity), compound interest
    A=P(1+r/n)^(nt), NPV, present value PV=FV/(1+r)^t.
    Pass spec as FIN_VERIFY contents."""
    return tools.verify_finance(spec)


@mcp.tool()
def verify_formal_logic(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Propositional logic: satisfiability, tautology, contradiction,
    entailment (premises→conclusion), logical equivalence.
    Pass spec as LOGIC_VERIFY contents (formula + claimed_*)."""
    return tools.verify_formal_logic(spec)


@mcp.tool()
def verify_genetics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """DNA/RNA base complementarity, reverse complement, GC content,
    codon→amino-acid translation, ORF start/stop bounds.
    Pass spec as GENETICS_VERIFY contents."""
    return tools.verify_genetics(spec)


@mcp.tool()
def verify_geography(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Lat/lon range validity, Haversine great-circle distance,
    initial bearing, UTM zone assignment.
    Pass spec as GEO_LOC_VERIFY contents."""
    return tools.verify_geography(spec)


@mcp.tool()
def verify_geology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Radiometric decay dating (N=N₀·e^(−λt)), Mohs hardness scratch test,
    Richter scale amplitude ratio between magnitudes.
    Pass spec as GEO_VERIFY contents.
    Dating: spec={"half_life_years":5730,"sample_fraction_remaining":0.5,"claimed_age_years":5730}
    Mohs:   spec={"mineral_a":"quartz","mineral_b":"calcite","claimed_a_scratches_b":true}
    Richter: spec={"magnitude_a":7.0,"magnitude_b":5.0,"claimed_amplitude_ratio":100}"""
    return tools.verify_geology(spec)


@mcp.tool()
def verify_geometry(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Areas and volumes of standard shapes, Pythagorean theorem,
    circle/sphere relationships, triangle angle sum.
    Pass spec as GEOM_VERIFY contents."""
    return tools.verify_geometry(spec)


@mcp.tool()
def verify_hydrology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Manning's equation (open channel flow), Darcy's law (porous media),
    continuity equation Q=Av.
    Pass spec as HYD_VERIFY contents.
    Manning: spec={"roughness_n":0.013,"hydraulic_radius_m":0.5,"slope":0.001,"claimed_velocity_m_per_s":1.21}
    Darcy:   spec={"hydraulic_conductivity_m_per_s":1e-4,"hydraulic_gradient":0.01,"claimed_seepage_velocity_m_per_s":1e-6}
    Continuity: spec={"area_m2":2.0,"velocity_m_per_s":1.5,"claimed_flow_m3_per_s":3.0}"""
    return tools.verify_hydrology(spec)


@mcp.tool()
def verify_information_theory(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Shannon entropy H(X)=−Σp·log₂p, channel capacity C=B·log₂(1+SNR),
    mutual information, Huffman minimum code length bounds.
    Pass spec as INFO_VERIFY contents."""
    return tools.verify_information_theory(spec)


@mcp.tool()
def verify_linguistics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Strong's number resolution (G1-G5624 Greek, H1-H8674 Hebrew),
    occurrence count, transliteration normalization, gloss consistency,
    cognate pair detection. Bridges scripture and original-language claims.
    Pass spec as LING_VERIFY contents."""
    return tools.verify_linguistics(spec)


@mcp.tool()
def verify_manufacturing(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Tolerance stack-up (worst-case/RSS), GD&T fit class
    (clearance/interference/transition), surface roughness Ra,
    process capability Cp/Cpk.
    Pass spec as MFG_VERIFY contents."""
    return tools.verify_manufacturing(spec)


@mcp.tool()
def verify_meteorology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Dew point (Magnus formula), relative humidity, pressure altitude,
    wind chill (NWS 2001 formula), heat index.
    Pass spec as MET_VERIFY contents."""
    return tools.verify_meteorology(spec)


@mcp.tool()
def verify_music_theory(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Interval semitone counts, chord quality (major/minor/dom7/dim),
    equal-temperament frequency ratios (fn=440·2^(n/12)).
    Pass spec as MUS_VERIFY contents."""
    return tools.verify_music_theory(spec)


@mcp.tool()
def verify_networking(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Subnet mask validity, CIDR notation, IP address range checks,
    network and broadcast address computation.
    Pass spec as NET_VERIFY contents."""
    return tools.verify_networking(spec)


@mcp.tool()
def verify_number_theory(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Primality testing, GCD/LCM, modular arithmetic,
    Fibonacci membership, perfect/abundant/deficient number classification.
    Pass spec as NUM_VERIFY contents."""
    return tools.verify_number_theory(spec)


@mcp.tool()
def verify_nutrition(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Macronutrient caloric values (protein/carbs=4 kcal/g, fat=9 kcal/g),
    BMR (Mifflin-St Jeor), TDEE with activity factor, nutrient density.
    Pass spec as NUT_VERIFY contents."""
    return tools.verify_nutrition(spec)


@mcp.tool()
def verify_optics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Snell's law (n₁sinθ₁=n₂sinθ₂), thin-lens equation (1/f=1/do+1/di),
    diffraction grating (d·sinθ=mλ), Rayleigh angular resolution criterion.
    Pass spec as OPT_VERIFY contents."""
    return tools.verify_optics(spec)


@mcp.tool()
def verify_photography(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Exposure value (EV=log₂(N²/t)), equivalent exposure combinations
    (aperture/shutter/ISO triangle), depth-of-field / hyperfocal distance.
    Pass spec as PHOTO_VERIFY contents."""
    return tools.verify_photography(spec)


@mcp.tool()
def verify_sports_analytics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Batting average, ERA, NFL passer rating, Pythagorean win expectation
    W%=RS²/(RS²+RA²), Elo rating change.
    Pass spec as SPORT_VERIFY contents."""
    return tools.verify_sports_analytics(spec)


@mcp.tool()
def verify_witness(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Witness / attestation record structural check: gate-chain completeness,
    reasoning trace present, anchor resolution, no-fabricated-answer.
    Pass spec as WIT_VERIFY contents (claimed_gate_verdicts, etc.)."""
    return tools.verify_witness(spec)


@mcp.tool()
def verify_quantum_computing(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Quantum computing verifier: qubit normalization (Σ|aᵢ|²=1),
    Grover optimal iterations (T=floor(π√N/4)), Shor period (a^r≡1 mod N),
    BB84 QKD security (QBER<11%), von Neumann entropy, fidelity.
    Pass spec as QCOMP_VERIFY contents.
    Normalization: spec={"amplitudes":[0.6,0.8],"claimed_normalized":true}
    Grover: spec={"n_items":64,"claimed_grover_iterations":6}
    BB84: spec={"qber":0.09,"claimed_secure":true}"""
    return tools.verify_quantum_computing(spec)


@mcp.tool()
def verify_medicine(spec: Dict[str, Any]) -> Dict[str, Any]:
    """BMI, drug dosage, blood pressure classification (AHA 2017), A1C→eAG,
    eGFR (Cockcroft-Gault), IBW (Devine), mean arterial pressure.
    Pass spec as MED_VERIFY contents.
    BMI: spec={"weight_kg":70,"height_m":1.75,"claimed_bmi":22.86}
    BP: spec={"systolic":125,"diastolic":82,"claimed_bp_class":"hypertension_stage_1"}
    MAP: spec={"systolic":120,"diastolic":80,"claimed_map_mmhg":93.3}"""
    return tools.verify_medicine(spec)


@mcp.tool()
def verify_cybersecurity(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Password entropy (bits=len*log2(charset)), TLS version status,
    CVSS severity classification, subnet host count, port classification.
    Pass spec as CYBER_VERIFY contents.
    Entropy: spec={"password_length":16,"charset_size":94,"claimed_entropy_bits":104.9}
    CVSS: spec={"cvss_base_score":9.1,"claimed_cvss_severity":"critical"}
    Port: spec={"port_number":443,"claimed_port_class":"well_known"}"""
    return tools.verify_cybersecurity(spec)


@mcp.tool()
def verify_economics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Simple/compound interest, present/future value, Rule of 72,
    inflation adjustment, GDP per capita, price elasticity of demand.
    Pass spec as ECON_VERIFY contents.
    Simple interest: spec={"principal":1000,"rate":0.05,"time_years":3,"claimed_simple_interest":150}
    Rule of 72: spec={"rate_percent":7,"claimed_doubling_years":10.3}
    Inflation: spec={"nominal_value":1000,"inflation_rate":0.03,"years":10,"claimed_real_value":744.09}"""
    return tools.verify_economics(spec)


@mcp.tool()
def verify_labor(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Gross pay, FLSA overtime (1.5x after 40h), annual-to-hourly,
    take-home pay after tax, minimum wage compliance.
    Pass spec as LABOR_VERIFY contents.
    Gross: spec={"hourly_rate":18.5,"hours_worked":45,"claimed_gross_pay":832.5}
    Overtime: spec={"hourly_rate":18.5,"regular_hours":40,"overtime_hours":5,"claimed_overtime_pay":878.75}
    Annual/hourly: spec={"annual_salary":52000,"claimed_hourly_equivalent":25.0}"""
    return tools.verify_labor(spec)


@mcp.tool()
def verify_real_estate(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Monthly mortgage payment, cap rate, gross rent multiplier,
    loan-to-value, debt service coverage ratio, rental yield.
    Pass spec as RE_VERIFY contents.
    Mortgage: spec={"loan_principal":300000,"annual_rate":0.065,"loan_term_months":360,"claimed_monthly_payment":1896.20}
    Cap rate: spec={"net_operating_income":24000,"property_value":400000,"claimed_cap_rate":0.06}
    LTV: spec={"loan_amount":240000,"appraised_value":300000,"claimed_ltv":0.80}"""
    return tools.verify_real_estate(spec)


@mcp.tool()
def verify_construction(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Concrete volume, rectangular/circular areas, rebar weight,
    wall area, paint coverage, floor tile count, beam load intensity.
    Pass spec as CONSTR_VERIFY contents.
    Concrete: spec={"length_m":10,"width_m":5,"depth_m":0.15,"claimed_concrete_m3":7.5}
    Tiles: spec={"tile_area_m2":50,"tile_size_m2":0.25,"waste_factor":0.10,"claimed_tile_count":220}
    Beam: spec={"total_load_kn":120,"span_m":6,"claimed_load_intensity_kn_per_m":20.0}"""
    return tools.verify_construction(spec)


@mcp.tool()
def verify_soil_science(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Soil pH suitability for crops, NPK fertilizer requirements,
    irrigation ETc (Kc×ET₀), lime requirement, USDA texture classification.
    Pass spec as SOIL_VERIFY contents.
    pH: spec={"crop":"maize","soil_ph":6.2,"claimed_ph_suitable":true}
    Texture: spec={"sand_pct":40,"silt_pct":40,"clay_pct":20,"claimed_texture_class":"loam"}
    Irrigation: spec={"reference_et0_mm_per_day":5.0,"crop_coefficient":1.15,"claimed_etc_mm_per_day":5.75}"""
    return tools.verify_soil_science(spec)


# ---------------------------------------------------------------------------
# Late-night domains (added overnight 2026-05-06, now wired to MCP)
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_thermodynamics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Carnot efficiency, ideal gas law (PV=nRT), specific heat (Q=mcDT), entropy change (DS=Q/T).
    Pass spec as THERMO_VERIFY contents.
    Carnot: spec={"T_hot_K":600,"T_cold_K":300,"claimed_efficiency":0.5}
    Ideal gas: spec={"pressure_Pa":101325,"volume_m3":0.0224,"moles":1.0,"claimed_temperature_K":273.15}
    Specific heat: spec={"mass_kg":1.0,"specific_heat_J_per_kg_K":4186,"delta_T_K":10,"claimed_heat_J":41860}
    Entropy: spec={"heat_J":1000,"temperature_K":300,"claimed_entropy_change_J_per_K":3.33}"""
    return tools.verify_thermodynamics(spec)


@mcp.tool()
def verify_nuclear_physics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Radioactive decay (N=N0*exp(-lambda*t)), binding energy per nucleon, half-life from activity, decay constant.
    Pass spec as NUCLEAR_VERIFY contents.
    Decay: spec={"half_life_seconds":3600,"elapsed_seconds":7200,"initial_count":1e9,"claimed_remaining_count":2.5e8}
    Binding energy: spec={"mass_defect_amu":0.0304,"nucleon_count":4,"claimed_binding_energy_MeV_per_nucleon":7.07}
    Half-life: spec={"activity_Bq":1e6,"num_atoms":5.2e9,"claimed_half_life_seconds":3600}"""
    return tools.verify_nuclear_physics(spec)


@mcp.tool()
def verify_ecology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Logistic population growth, trophic efficiency (10% rule), Shannon diversity index, carbon footprint.
    Pass spec as ECO_VERIFY contents.
    Logistic: spec={"carrying_capacity_K":1000,"initial_population_N0":100,"growth_rate_r":0.5,"time_t":5,"claimed_population":731}
    Trophic: spec={"energy_input":10000,"trophic_levels_up":2,"trophic_efficiency":0.1,"claimed_energy_available":100}
    Shannon: spec={"species_counts":[10,20,30],"claimed_shannon_index":1.09}"""
    return tools.verify_ecology(spec)


@mcp.tool()
def verify_rhetoric(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Fallacy classification (formal vs informal), syllogism validity, argument structure completeness.
    Pass spec as RHET_VERIFY contents.
    Fallacy: spec={"fallacy_name":"ad hominem","claimed_is_formal_fallacy":false}
    Syllogism: spec={"major_premise":"All M are P","minor_premise":"All S are M","conclusion":"All S are P","claimed_valid":true}
    Straw man: spec={"fallacy_name":"straw_man","claimed_is_formal_fallacy":false}"""
    return tools.verify_rhetoric(spec)


@mcp.tool()
def verify_philosophy(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Modal logic (K-axiom), ethical framework classification, epistemic claim type, Leibniz identity principle.
    Pass spec as PHIL_VERIFY contents.
    Modal: spec={"is_necessarily_true":true,"is_possibly_true":true,"claimed_consistent":true}
    Ethics: spec={"framework_name":"consequentialist","claimed_focuses_on_outcomes":true}
    Epistemic: spec={"claim_type":"empirical","claimed_requires_observation":true}"""
    return tools.verify_philosophy(spec)


@mcp.tool()
def verify_operations_research(spec: Dict[str, Any]) -> Dict[str, Any]:
    """LP feasibility, critical path (makespan), 0/1 knapsack optimal value, assignment cost.
    Pass spec as OR_VERIFY contents.
    Critical path: spec={"tasks":[{"id":"A","duration":3,"depends_on":[]},{"id":"B","duration":4,"depends_on":["A"]}],"claimed_makespan":7}
    Knapsack: spec={"items":[{"weight":2,"value":3},{"weight":3,"value":4}],"capacity":5,"claimed_max_value":7}
    LP: spec={"variable_values":{"x":3,"y":2},"constraints":[{"lhs_coeffs":{"x":1,"y":1},"operator":"<=","rhs":10}],"claimed_feasible":true}"""
    return tools.verify_operations_research(spec)


@mcp.tool()
def verify_law(spec: Dict[str, Any]) -> Dict[str, Any]:
    """US federal law: contract formation (5 elements), constitutional age requirements, FLSA overtime, Miranda completeness.
    Pass spec as LAW_VERIFY contents.
    Contract: spec={"has_offer":true,"has_acceptance":true,"has_consideration":true,"has_capacity":true,"has_legality":true,"claimed_contract_valid":true}
    Age: spec={"office":"president","age":35,"claimed_age_qualified":true}
    Miranda: spec={"has_right_to_silence":true,"has_anything_used_against":true,"has_right_to_attorney":true,"has_appointed_attorney":true,"claimed_miranda_complete":true}"""
    return tools.verify_law(spec)


@mcp.tool()
def verify_theology_doctrine(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Orthodox Christian doctrine: gospel core facts (1 Cor 15:3-4), Trinity, salvation by grace, bodily resurrection, creation ex nihilo.
    Pass spec as THEOL_VERIFY contents.
    Gospel: spec={"claimed_died_for_sins":true,"claimed_was_buried":true,"claimed_rose_third_day":true,"claimed_gospel_complete":true}
    Trinity: spec={"persons_named":["Father","Son","Holy Spirit"],"claimed_is_trinity":true}
    Salvation: spec={"is_by_grace":true,"is_through_faith":true,"claimed_salvation_orthodox":true}"""
    return tools.verify_theology_doctrine(spec)


@mcp.tool()
def verify_history_chronology(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Year arithmetic (BCE/CE), century assignment, era classification, elapsed years BCE<->CE, decade assignment.
    Pass spec as HIST_VERIFY contents.
    Year arithmetic: spec={"from_year":100,"to_year":2000,"claimed_elapsed_years":1900}
    Century: spec={"year_CE":1776,"claimed_century":18}
    Era: spec={"year":-44,"claimed_era":"BCE"}
    BCE-to-CE: spec={"from_year_bce":500,"to_year_ce":1000,"claimed_total_years":1499}"""
    return tools.verify_history_chronology(spec)


@mcp.tool()
def verify_materials_science(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Stress/strain (Young's modulus), thermal expansion, density, hardness comparison.
    Pass spec as MAT_VERIFY contents.
    Stress: spec={"youngs_modulus_Pa":200e9,"strain":0.001,"claimed_stress_Pa":2e8}
    Thermal: spec={"thermal_expansion_coeff":12e-6,"original_length_m":1.0,"delta_T_K":100,"claimed_delta_length_m":0.0012}
    Density: spec={"mass_kg":2.7,"volume_m3":0.001,"claimed_density_kg_per_m3":2700}"""
    return tools.verify_materials_science(spec)


@mcp.tool()
def verify_architecture(spec: Dict[str, Any]) -> Dict[str, Any]:
    """FAR, occupant load, stair compliance (IBC riser/tread), window-wall ratio, structural load superposition.
    Pass spec as ARCH_VERIFY contents.
    FAR: spec={"total_floor_area_m2":5000,"lot_area_m2":2000,"claimed_far":2.5}
    Occupant load: spec={"floor_area_m2":500,"occupant_load_factor_m2_per_person":5,"claimed_occupant_count":100}
    Stair: spec={"riser_height_mm":180,"tread_depth_mm":280,"claimed_ibc_compliant":true}"""
    return tools.verify_architecture(spec)


@mcp.tool()
def verify_oceanography(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Hydrostatic pressure at depth, salinity classification, deep-water wave speed, tidal range type, pelagic zone.
    Pass spec as OCEAN_VERIFY contents.
    Pressure: spec={"depth_m":1000,"claimed_pressure_Pa":10158825}
    Salinity: spec={"salinity_ppt":35,"claimed_classification":"marine"}
    Wave speed: spec={"wavelength_m":100,"claimed_wave_speed_m_per_s":12.5}
    Pelagic zone: spec={"depth_m":500,"claimed_zone":"mesopelagic"}"""
    return tools.verify_oceanography(spec)


# ---------------------------------------------------------------------------
# Scripture / Layer 0 tools
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_scripture_anchors(anchors: List[str]) -> Dict[str, Any]:
    """Confirm each ref in anchors resolves to a real WEB verse.
    Catches fabricated scripture citations — the most common LLM failure mode in this domain.
    anchors: ["John 3:16", "Rom 1:20", "Gen 1:1"]
    Returns CONFIRMED if all refs resolve, MISMATCH if any fail."""
    return tools.verify_scripture_anchors(anchors)


@mcp.tool()
def resolve_scripture_ref(ref: str) -> Dict[str, Any]:
    """Look up a scripture reference in the WEB Bible and return its text.
    Accepts: "John 3:16", "Jn3:16", "1Co13:4", "Rom 8:28".
    Returns {ref, web_text, status, detail}. status=source_missing if Layer 0 not provisioned."""
    return tools.resolve_scripture_ref(ref)


@mcp.tool()
def word_study(strongs_num: str) -> Dict[str, Any]:
    """Strong's-keyed word study: definition, derivation, every verse where the word appears.
    Accepts: "G26" (agape/love), "H2617" (hesed/lovingkindness), "G4102" (pistis/faith).
    Returns {strongs, word, transliteration, definition, derivation, verses, occurrence_count}
    or source_missing status if Layer 0 data has not been provisioned."""
    return tools.word_study(strongs_num)


@mcp.tool()
def triangulate_claim(
    ref: str,
    claim: str,
    strongs_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Check whether an interpretation claim about a scripture verse is consistent with
    original-language Strong's definitions. Without strongs_keys returns
    NEEDS_MANUAL_VERIFICATION with the WEB text and review instructions.
    With strongs_keys (e.g. ['G142'] for airo), returns the semantic range per word
    so the claim can be compared to attested meaning."""
    return tools.triangulate_claim(ref, claim, strongs_keys=strongs_keys)


# ---------------------------------------------------------------------------
# Single-gate shortcuts (cheaper than validate_packet)
# ---------------------------------------------------------------------------

@mcp.tool()
def attest_red(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Run only the RED gate against a packet: coercion detection, authority violations, hard failures.
    Cheaper than validate_packet when you only need the first-gate safety check.
    packet must include a 'domain' field (e.g. "governance", "labor", "finance")."""
    return tools.attest_red(packet)


@mcp.tool()
def attest_floor(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Run only the FLOOR gate against a packet: structural completeness, internal consistency.
    Cheaper than validate_packet when you only need the completeness check.
    packet must include a 'domain' field (e.g. "governance", "labor", "finance")."""
    return tools.attest_floor(packet)


# ---------------------------------------------------------------------------
# Developer utilities
# ---------------------------------------------------------------------------

@mcp.tool()
def get_example_packet(name: str) -> Dict[str, Any]:
    """Retrieve a sample packet by name from the examples/ directory.
    Pass name="finance", "governance", "labor", etc. to get a ready-to-use packet.
    Call with any name to get the list of available examples if the name is unknown.
    Returns {name, packet} on success or {error, available} on miss."""
    return tools.get_example_packet(name)


@mcp.tool()
def verify_physics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Physics umbrella: dimensional analysis and/or conservation law verification.
    Pass 'dimensional' key for SI unit analysis, 'conservation' key for before/after balance.
    Dimensional: spec={"dimensional": {"equation": "F=m*a", "symbols": {"F": "newton", "m": "kilogram", "a": "meter/second**2"}}}
    Conservation: spec={"conservation": {"before": {"KE": 5.0, "PE": 10.0}, "after": {"KE": 8.0, "PE": 7.0}, "law": "energy"}}
    Both keys fire independently if supplied."""
    return tools.verify_physics(spec)


@mcp.tool()
def verify_statistics(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Statistics umbrella: p-value recomputation, multiple comparisons correction, CI verification.
    Pass 'pvalue', 'multiple_comparisons', and/or 'confidence_interval' keys — each fires if present.
    p-value: spec={"pvalue": {"test": "paired_t", "n": 20, "mean_diff": 0.5, "sd_diff": 1.0, "tail": "two", "claimed_p": 0.0375}}
    Multiple comparisons: spec={"multiple_comparisons": {"raw_p_values": [0.01, 0.04], "method": "bonferroni"}}
    CI: spec={"confidence_interval": {"estimate": 5.0, "ci_low": 4.2, "ci_high": 5.8}}"""
    return tools.verify_statistics(spec)


@mcp.tool()
def verify_phase(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Classify a packet by its declared 'phase': setup, positioning, or conversion (Prov 24:27).
    Cross-cutting verifier — NA if no phase declared, CONFIRMED with canonical guidance if valid.
    spec={"phase": "setup"} or {"phase": "positioning"} or {"phase": "conversion"}"""
    return tools.verify_phase(spec)


# ---------------------------------------------------------------------------
# Polymathic — cross-domain coordinator (Path C)
# ---------------------------------------------------------------------------

@mcp.tool()
def run_polymathic(
    situation: str,
    max_domains: int = 10,
    split_threshold: int = 5,
    stop_on_discordant: bool = False,
    decompose: bool = True,
    oracle_model: str = "claude-haiku-4-5-20251001",
) -> Dict[str, Any]:
    """Cross-domain synthesis: fire every applicable verifier against one
    natural-language situation and return a composite verdict.

    Where the verify_* tools each cover ONE domain, this coordinates ALL
    of them. Decompose the situation into atomic claims, classify each
    to its domain verifier, run them in parallel, then synthesize the
    composite verdict using axis-weighted scoring across the scaffold.

    Composite verdicts:
      CONCORDANT   — all fired domains confirmed
      DISCORDANT   — at least one core-axis mismatch
      MIXED        — peripheral mismatch, structural pieces still hold
      QUARANTINE   — confirmed pieces but unresolved claims remain
      OUT_OF_SCOPE — no domain matched
      ERROR        — system failure

    The 25-pp gap on the polymathic benchmark (engine 100% vs
    Sonnet/Haiku alone 75%) lives here: the synthesis requires
    calibrated numerical verification AND axis-weighted mismatch
    fraction across N domains, neither of which an LLM can reliably
    do unaided. ~5–15s typical.

    situation:           Natural-language description spanning multiple domains.
    max_domains:         Hard cap on total domains processed (default 10).
    split_threshold:     When domain count exceeds this, the coordinator
                         delegates to umbrella sub-coordinators for
                         bounded compute (default 5).
    stop_on_discordant:  Early-exit when a cluster confirms DISCORDANT.
    decompose:           Two-stage pipeline (decompose -> classify ->
                         verify). When False, uses a single combined
                         oracle call for speed at the cost of accuracy.
    oracle_model:        Anthropic model used for decompose/classify.

    Returns a PolymathicRecord dict: situation, atomic_claims,
    quarantined_claims, keeper_manifest, closest_precedent,
    domain_results, axis_overlaps, composite_verdict, content_hash.
    """
    # Prefer the hosted engine when configured — that process already has
    # ANTHROPIC_API_KEY in its env (loaded from .env at startup) and the
    # parallelized classifier wired in. The thin stdio MCP client should
    # not need its own oracle credentials.
    if CONCORDANCE_API_URL:
        try:
            payload = json.dumps({
                "situation": situation,
                "max_domains": max_domains,
                "split_threshold": split_threshold,
                "stop_on_discordant": stop_on_discordant,
                "oracle_model": oracle_model,
                "store": True,
            }).encode()
            headers = {"Content-Type": "application/json"}
            if CONCORDANCE_API_KEY:
                headers["x-api-key"] = CONCORDANCE_API_KEY
            req = urllib.request.Request(
                f"{CONCORDANCE_API_URL.rstrip('/')}/polymathic",
                data=payload,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                api_result = json.loads(resp.read().decode())
            api_result["_source"] = "api"
            return api_result
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            # Fall through to local; capture so the trail isn't silent
            _last_err = f"hosted poly call failed: {type(exc).__name__}: {exc}"
        except Exception as exc:
            _last_err = f"hosted poly call error: {type(exc).__name__}: {exc}"
    else:
        _last_err = None

    # Local path — needs ANTHROPIC_API_KEY in this process's env to call
    # the oracle for decompose/classify.
    try:
        from ..agent.poly_agent import run_polymathic as _run_poly
    except ImportError as exc:
        return {
            "composite_verdict": "ERROR",
            "detail": f"polymathic agent unavailable: {exc}",
            "_source": "local",
        }
    rec = _run_poly(
        situation=situation,
        model=oracle_model,
        max_domains=max_domains,
        split_threshold=split_threshold,
        stop_on_discordant=stop_on_discordant,
        decompose=decompose,
    )
    out = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__)
    out["_source"] = "local"
    if _last_err:
        out["_hosted_fallback_reason"] = _last_err
    return out


# ---------------------------------------------------------------------------
# Atlas + Almanac — read-from-the-well surfaces
# ---------------------------------------------------------------------------
# Atlas walks the structural map (grid: domains, axes, adjacency).
# Almanac walks the record (sealed precedent, observed patterns,
# quarantine, what the workers have discovered).
# Together they give an agent the full READ surface of the engine —
# the complement to verify_*/run_polymathic which write new claims.

@mcp.tool()
def atlas(
    domain: Optional[str] = None,
    axis: Optional[str] = None,
    limit: int = 20,
) -> Dict[str, Any]:
    """Walk the structural map of the engine — the grid.

    The atlas describes WHERE things sit. Every domain has a position
    on the 7-axis scaffold (encoding, metabolism, reasoning,
    physical_substance, authority_trust, time_sequence,
    conservation_balance). Domains that share an axis are
    structurally adjacent. Domains on 3+ axes are structurally deep.

    Use the atlas before calling a verifier when you don't know which
    domain applies, or to find which other domains are adjacent to a
    domain you already know.

    Modes (call with at most one of these):
      no args         → return the full scaffold (all 7 axes + their
                        member counts, total domains, umbrella groupings).
      domain="X"      → return X's axis position, depth, neighbors
                        ranked by shared-axis count, umbrella, children.
      axis="reasoning" → list every domain on that axis, ranked by depth.

    limit caps the adjacency / member list (default 20).
    """
    from .. import grid as _grid

    if domain and axis:
        return {"view": "error", "detail": "pass at most one of domain or axis"}

    if domain:
        if domain not in _grid.AXIS_DIMENSIONS:
            return {
                "view": "domain",
                "subject": domain,
                "found": False,
                "detail": f"{domain!r} is not in the scaffold",
            }
        dims = sorted(_grid.axis_dimensions(domain))
        adj = _grid.adjacent(domain)
        umbrella = next(
            (parent for parent, kids in _grid.UMBRELLAS.items() if domain in kids),
            None,
        )
        kids = list(_grid.umbrella_children(domain))
        return {
            "view": "domain",
            "subject": domain,
            "found": True,
            "axes": dims,
            "depth": len(dims),
            "umbrella": umbrella,
            "umbrella_children": kids,
            "adjacent": [
                {
                    "domain": other,
                    "shared_axes": sorted(shared),
                    "shared_count": len(shared),
                }
                for other, shared in adj[:limit]
            ],
            "adjacent_total": len(adj),
        }

    if axis:
        if axis not in _grid.DIMENSIONS:
            return {
                "view": "axis",
                "subject": axis,
                "found": False,
                "valid_axes": list(_grid.DIMENSIONS),
            }
        members = [
            (d, sorted(_grid.AXIS_DIMENSIONS[d]))
            for d in _grid.AXIS_DIMENSIONS
            if axis in _grid.AXIS_DIMENSIONS[d]
        ]
        # rank by depth (more axes = more structurally deep)
        members.sort(key=lambda dx: (-len(dx[1]), dx[0]))
        return {
            "view": "axis",
            "subject": axis,
            "found": True,
            "members": [
                {"domain": d, "axes": ax, "depth": len(ax)}
                for d, ax in members[:limit]
            ],
            "members_total": len(members),
        }

    # No args → scaffold overview
    by_axis: Dict[str, int] = {a: 0 for a in _grid.DIMENSIONS}
    for d, axes in _grid.AXIS_DIMENSIONS.items():
        for a in axes:
            if a in by_axis:
                by_axis[a] += 1
    return {
        "view": "scaffold",
        "axes": list(_grid.DIMENSIONS),
        "axis_counts": by_axis,
        "domains_total": len(_grid.AXIS_DIMENSIONS),
        "umbrellas": {p: list(c) for p, c in _grid.UMBRELLAS.items()},
        "note": "Call with domain= or axis= to drill in.",
    }


# ──────────────────────────────────────────────────────────────────────
# The Almanac — a curated book with two kinds of entries:
#
#   protocol — a canonical multi-domain situation, pre-run through the
#              engine. Includes a structured `pre_run` with composite
#              verdict, per-domain results, and axis overlaps. The
#              textbook part of the book.
#
#   saying   — an old proverb, rule of thumb, or farmer's-almanac line
#              run through the engine's verifiers and annotated with
#              the result. Includes a `verification` paragraph (the
#              math) and a wry `wisdom` line. The field-handbook part.
#
# Both kinds share: id, title, category, domains, axes, verdict,
# wisdom, triggers. Difference is structural: protocols carry a
# pre_run object, sayings carry a verification text. The almanac
# tool serves both from one file: data/almanac/entries.jsonl
#
# Curated, not generated. Updated by editing the file and bouncing
# the engine. No oracle calls, no live API roundtrips — like a book.
# ──────────────────────────────────────────────────────────────────────
def _load_almanac_entries():
    from pathlib import Path as _P
    out = []
    candidates = [
        _P("data") / "almanac" / "entries.jsonl",
        _P(__file__).resolve().parents[3] / "data" / "almanac" / "entries.jsonl",
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            for line in path.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            return out
        except OSError:
            continue
    return out


_ALMANAC_ENTRIES = _load_almanac_entries()


# ──────────────────────────────────────────────────────────────────────
# search / fetch — the two tools ChatGPT connectors and Deep Research
# require by name. `search` returns a ranked list of {id, title, url};
# `fetch` returns one document's full text by id. Both read the same
# curated book (data/almanac/entries.jsonl), preferring pages that carry
# a sealed, tamper-evident proof. This is what lets ChatGPT (and any
# connector-capable agent) find and cite the verified corpus.
# ──────────────────────────────────────────────────────────────────────
def _entry_proof(e: Dict[str, Any]) -> Optional[str]:
    return e.get("proof") or (e.get("pre_run") or {}).get("proof_receipt")


def _entry_url(e: Dict[str, Any]) -> str:
    return f"https://narrowhighway.com/almanac/{e.get('id', '')}"


def _entry_blob(e: Dict[str, Any]) -> str:
    parts = [
        str(e.get("title", "")),
        str(e.get("situation", "")),
        str(e.get("use", "")),
        str(e.get("verification", "")),
        str(e.get("wisdom", "")),
        " ".join(str(x) for x in (e.get("domains") or [])),
        " ".join(str(x) for x in ((e.get("triggers") or {}).get("keywords") or [])),
        str(e.get("category", "")),
    ]
    return " ".join(parts).lower()


def _entry_text(e: Dict[str, Any]) -> str:
    """Assemble one entry into a single readable document for fetch()."""
    lines: List[str] = []
    if e.get("title"):
        lines.append(str(e["title"]))
        lines.append("")
    if e.get("situation"):
        lines.append(str(e["situation"]))
    if e.get("verification"):
        lines.append(str(e["verification"]))
    if e.get("use"):
        lines.append("")
        lines.append("USE: " + str(e["use"]))
    pre = e.get("pre_run") or {}
    if pre.get("summary"):
        lines.append("")
        lines.append("VERIFICATION: " + str(pre["summary"]))
    for dr in (pre.get("domain_results") or []):
        lines.append(
            f"  - {dr.get('domain')}: {dr.get('verdict')} -- {dr.get('detail')}"
        )
    if e.get("wisdom"):
        lines.append("")
        lines.append(str(e["wisdom"]))
    proof = _entry_proof(e)
    if proof:
        lines.append("")
        lines.append("PROOF (tamper-evident receipt): " + str(proof))
    doms = e.get("domains") or []
    if doms:
        lines.append("DOMAINS: " + ", ".join(str(d) for d in doms))
    return "\n".join(lines)


@mcp.tool()
def search(query: str, max_results: int = 10) -> Dict[str, Any]:
    """Search the verified corpus and return ranked results.

    This is the entry point ChatGPT connectors and Deep Research call.
    It ranks the curated, engine-verified pages (cross-domain
    connections, located results, and sayings) by keyword match against
    the query, preferring pages that carry a sealed, citable proof.

    Returns {"results": [{"id", "title", "url", "snippet"}]}. Pass an id
    to fetch() to read the whole page and its proof receipt.
    """
    book = _ALMANAC_ENTRIES or []
    q = (query or "").lower().strip()
    tokens = [t for t in re.split(r"[^a-z0-9]+", q) if len(t) > 1]
    scored: List[tuple] = []
    for e in book:
        if not e.get("id"):
            continue
        blob = _entry_blob(e)
        title = str(e.get("title", "")).lower()
        if tokens:
            score = 0
            for t in tokens:
                score += blob.count(t)
                if t in title:
                    score += 5  # title hits weigh more
            if score == 0:
                continue
        else:
            score = 0  # empty query → table of contents (proven first)
        if _entry_proof(e):
            score += 3  # prefer pages with a sealed proof
        scored.append((score, e))
    scored.sort(key=lambda se: (-se[0], se[1].get("id") or ""))
    results = []
    for _score, e in scored[: max(1, min(max_results, 50))]:
        snippet = str(e.get("situation") or e.get("verification") or e.get("use") or "")[:300]
        proof = _entry_proof(e)
        results.append({
            "id": e.get("id"),
            "title": e.get("title", ""),
            "url": proof or _entry_url(e),
            "snippet": snippet,
        })
    return {"results": results}


@mcp.tool()
def fetch(id: str) -> Dict[str, Any]:
    """Fetch one verified page by id (the second tool ChatGPT connectors
    require). Returns {"id", "title", "text", "url", "metadata"} where
    `text` is the full page (situation, use, the per-domain verification
    results, the wisdom, and the tamper-evident proof receipt) and
    `metadata` carries domains, category, verdict, and the proof URL.

    Accepts an entry id (e.g. "connection_rsa_is_modular_inverse_of_primes")
    or a seal ref / cite_url; for a seal it points the reader to GET
    /seal/{ref}, the permanent record.
    """
    book = _ALMANAC_ENTRIES or []
    key = (id or "").strip()
    # allow a full cite_url or bare seal ref to be fetched too
    seal_ref = ""
    if "/seal/" in key:
        seal_ref = key.rsplit("/seal/", 1)[-1].strip("/ ")
    match = next((e for e in book if e.get("id") == key), None)
    if match is None and seal_ref:
        match = next(
            (e for e in book if (_entry_proof(e) or "").endswith(seal_ref)),
            None,
        )
    if match is None:
        return {
            "id": key,
            "title": "(not found)",
            "text": (
                "No verified page with that id. Call search(query) first to "
                "get ids, or browse GET https://narrowhighway.com/verified."
            ),
            "url": "https://narrowhighway.com/verified",
            "metadata": {"found": False},
        }
    proof = _entry_proof(match)
    return {
        "id": match.get("id"),
        "title": match.get("title", ""),
        "text": _entry_text(match),
        "url": proof or _entry_url(match),
        "metadata": {
            "domains": match.get("domains") or [],
            "category": match.get("category"),
            "kind": match.get("kind", "protocol"),
            "verdict": match.get("verdict"),
            "proof": proof,
            "canonical": _entry_url(match),
            "found": True,
        },
    }


@mcp.tool()
def almanac(
    query: Optional[str] = None,
    entry_id: Optional[str] = None,
    category: Optional[str] = None,
    kind: Optional[str] = None,
    verdict: Optional[str] = None,
    limit: int = 5,
) -> Dict[str, Any]:
    """The Almanac — a curated book the engine has worked through.

    Two kinds of entries, one book:

      protocol — canonical multi-domain situations, pre-run through
                 the engine. Composite verdict + per-domain results +
                 axis overlaps + the wisdom the run teaches.

      saying   — proverbs, rules of thumb, and old farmer's-almanac
                 lines, each one verified by computation and annotated
                 with a wry note about what the math actually shows.
                 Folk wisdom that's been confirmed (or, in some cases,
                 quietly retired) by the verifiers.

    Each entry is curated. The book is updated by editing
    data/almanac/entries.jsonl. No oracle calls, no roundtrips.

    Modes:
      no args              → table of contents (id, title, kind,
                              category, verdict)
      query="..."          → up to `limit` entries ranked by keyword +
                              axis match against the query
      entry_id="X"         → one entry's full record
      category="weather"   → list every entry in a category
      kind="saying"        → list everything of one kind
      verdict="MISMATCH"   → entries whose verdicts came out a certain
                              way (handy for finding sayings the math
                              has quietly retired)

    Each match returns: id, title, kind, category, domains, axes,
    verdict, wisdom — plus pre_run (for protocols) or verification
    (for sayings). The Guide does not panic.
    """
    book = _ALMANAC_ENTRIES
    if not book:
        return {
            "view": "empty",
            "detail": "No entries loaded. Expected data/almanac/entries.jsonl.",
            "matches": [],
            "total_in_book": 0,
        }

    def _shape(e: Dict[str, Any], full: bool = False) -> Dict[str, Any]:
        """Render an entry for the response. Both kinds share most
        fields; protocols include pre_run, sayings include verification."""
        base = {
            "id": e.get("id"),
            "title": e.get("title"),
            "kind": e.get("kind", "protocol"),
            "category": e.get("category"),
            "domains": e.get("domains", []),
            "axes": e.get("axes", []),
            "verdict": e.get("verdict"),
            "wisdom": e.get("wisdom"),
        }
        if full:
            if e.get("kind") == "saying":
                base["verification"] = e.get("verification")
            else:
                base["situation"] = e.get("situation")
                base["pre_run"] = e.get("pre_run")
        return base

    # ── single entry by id
    if entry_id:
        match = next((e for e in book if e.get("id") == entry_id), None)
        if not match:
            return {
                "view": "entry",
                "entry_id": entry_id,
                "found": False,
                "available_ids": [e.get("id") for e in book],
                "matches": [],
                "total_in_book": len(book),
            }
        return {
            "view": "entry",
            "entry_id": entry_id,
            "found": True,
            "matches": [_shape(match, full=True)],
            "total_in_book": len(book),
        }

    # ── filter by kind
    if kind and not (query or category or verdict):
        matched = [e for e in book if e.get("kind") == kind]
        return {
            "view": "kind",
            "kind": kind,
            "matches": [_shape(e) for e in matched[:limit]],
            "total_with_kind": len(matched),
            "total_in_book": len(book),
        }

    # ── filter by category
    if category and not (query or verdict):
        matched = [e for e in book if e.get("category") == category]
        if kind:
            matched = [e for e in matched if e.get("kind") == kind]
        return {
            "view": "category",
            "category": category,
            "kind_filter": kind,
            "matches": [_shape(e, full=True) for e in matched[:limit]],
            "total_in_category": len(matched),
            "total_in_book": len(book),
        }

    # ── filter by verdict
    if verdict and not query:
        v = verdict.upper()
        matched = [e for e in book if (e.get("verdict") or "").upper() == v]
        if kind:
            matched = [e for e in matched if e.get("kind") == kind]
        if category:
            matched = [e for e in matched if e.get("category") == category]
        return {
            "view": "verdict",
            "verdict": v,
            "matches": [_shape(e, full=True) for e in matched[:limit]],
            "total_with_verdict": len(matched),
            "total_in_book": len(book),
        }

    # ── query: rank entries by trigger-keyword + saying/title match + axis overlap
    if query:
        qlower = query.lower()
        predicted = _predict_axes_from_query(qlower)
        scored = []
        for e in book:
            if kind and e.get("kind") != kind: continue
            if category and e.get("category") != category: continue
            if verdict and (e.get("verdict") or "").upper() != verdict.upper(): continue

            score = 0
            triggers = e.get("triggers") or {}
            keywords = [k.lower() for k in (triggers.get("keywords") or [])]
            score += sum(2 for k in keywords if k in qlower)

            # Title / saying match
            title_l = (e.get("title") or "").lower()
            if qlower in title_l: score += 4
            for w in qlower.split():
                if len(w) < 3: continue
                if w in title_l: score += 2
                if w in (e.get("category") or "").lower(): score += 1
                # For sayings, search the verification + wisdom prose
                if e.get("kind") == "saying":
                    if w in (e.get("verification") or "").lower(): score += 1
                    if w in (e.get("wisdom") or "").lower(): score += 1
                # For protocols, search the situation
                else:
                    if w in (e.get("situation") or "").lower(): score += 1
                for d in e.get("domains", []):
                    if w in d.lower(): score += 1

            # Axis overlap
            trigger_axes = set(triggers.get("axes") or [])
            entry_axes = set(e.get("axes") or [])
            score += len(predicted & (trigger_axes | entry_axes))

            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda se: -se[0])
        return {
            "view": "query",
            "query": query,
            "predicted_axes": sorted(predicted),
            "filters": {"kind": kind, "category": category, "verdict": verdict},
            "matches": [
                {**_shape(e, full=True), "score": s}
                for s, e in scored[:limit]
            ],
            "total_matched": len(scored),
            "total_in_book": len(book),
        }

    # ── default: full table of contents
    return {
        "view": "index",
        "matches": [
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "kind": e.get("kind", "protocol"),
                "category": e.get("category"),
                "verdict": e.get("verdict"),
            }
            for e in book
        ],
        "total_in_book": len(book),
        "kinds": sorted({e.get("kind", "protocol") for e in book}),
        "categories": sorted({e.get("category") for e in book if e.get("category")}),
        "verdicts": sorted({e.get("verdict") for e in book if e.get("verdict")}),
        "preface": (
            "The Almanac is what the engine has worked through. Two kinds of "
            "entry: protocols (canonical pre-run polymathic situations) and "
            "sayings (folk wisdom verified by computation). Pass query=, "
            "entry_id=, category=, kind=, or verdict= to drill in. The Almanac "
            "does not panic."
        ),
    }


@mcp.tool()
def propose_almanac_entry(
    candidate: str,
    kind: str = "auto",
    title: Optional[str] = None,
    category: Optional[str] = None,
) -> Dict[str, Any]:
    """Propose a draft almanac entry from a saying or situation.

    The growth loop for the Almanac. Hand it a candidate — an old
    proverb, a rule of thumb, a multi-domain situation — and it
    runs the engine, packages the result into a draft entry, and
    returns it ready for human curation. The draft never auto-commits
    to data/almanac/entries.jsonl; a curator (you) reads it, decides
    whether the wisdom and the verdict belong in the book, edits the
    prose, and appends it manually. The engine does the math; the
    human does the wisdom.

    Use this on the Library of Congress harvest of historical
    farmer's almanacs, on traditions, on shop talk — anywhere a
    folk claim sits and someone wants to know if the math agrees.

    Arguments:
      candidate    A saying, proverb, or natural-language situation.
                   For sayings, just paste the proverb. For protocols,
                   describe the situation with concrete numbers.
      kind         "auto" (default), "saying", or "protocol".
                   "auto" guesses based on length and structure:
                   short pithy text → saying; longer concrete
                   numerical text → protocol.
      title        Optional override. If omitted, uses the candidate
                   text (for sayings) or asks for one (for protocols).
      category     Optional starter category. Curator can change it.

    Returns a draft entry shaped like the file format. Includes
    suggested triggers (keywords + axes) extracted from the run.
    """
    candidate = (candidate or "").strip()
    if not candidate:
        return {"error": "candidate is required"}

    chosen_kind = kind
    if chosen_kind == "auto":
        # Sayings tend to be short, pithy, and have no numbers.
        # Protocols tend to be long and contain concrete values.
        is_short = len(candidate) <= 120
        has_numbers = any(ch.isdigit() for ch in candidate)
        chosen_kind = "saying" if (is_short and not has_numbers) else "protocol"

    # Slug-style id from the title or first words of the candidate
    seed = (title or candidate).lower()
    import re as _re
    slug = _re.sub(r"[^a-z0-9]+", "_", seed).strip("_")[:48] or "draft_entry"

    # Predict axes for the candidate
    predicted_axes = sorted(_predict_axes_from_query(candidate.lower()))

    draft: Dict[str, Any] = {
        "id": slug,
        "kind": chosen_kind,
        "title": title or candidate,
        "category": category or "uncategorized",
        "domains": [],
        "axes": predicted_axes,
        "verdict": "DRAFT",
        "wisdom": "(curator: write the dry note here — what does the math actually show?)",
        "triggers": {
            "keywords": [
                w for w in _re.findall(r"[a-zA-Z]{4,}", candidate.lower())
                if w not in {"that","this","with","from","into","when","than",
                              "what","were","they","then","have","been","does"}
            ][:10],
            "axes": predicted_axes,
        },
    }

    # Run the engine on the candidate so the curator gets the math.
    # Prefer the hosted engine when configured (it has ANTHROPIC_API_KEY
    # already loaded); fall back to local in-process execution if the
    # hosted call fails or no URL is set.
    rec_d: Dict[str, Any] = {}
    used_source = "local"
    try:
        if CONCORDANCE_API_URL:
            try:
                payload = json.dumps({
                    "situation": candidate,
                    "max_domains": 8,
                    "split_threshold": 5,
                    "store": True,
                }).encode()
                headers = {"Content-Type": "application/json"}
                if CONCORDANCE_API_KEY:
                    headers["x-api-key"] = CONCORDANCE_API_KEY
                req = urllib.request.Request(
                    f"{CONCORDANCE_API_URL.rstrip('/')}/polymathic",
                    data=payload,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    rec_d = json.loads(resp.read().decode())
                used_source = "api"
            except Exception:
                rec_d = {}

        if not rec_d:
            from ..agent.poly_agent import run_polymathic as _run_poly
            rec = _run_poly(situation=candidate, max_domains=8, decompose=True)
            rec_d = rec.to_dict() if hasattr(rec, "to_dict") else dict(rec.__dict__)
            used_source = "local"

        if chosen_kind == "saying":
            draft["verification"] = (
                "(curator: replace this with a one-paragraph explanation "
                "of why the math gives the verdict it does. The polymathic "
                "run below is the engine's first pass — distill it.)"
            )
        else:
            draft["situation"] = candidate
            draft["pre_run"] = {
                "summary": "(curator: write a one-sentence summary)",
                "domain_results": rec_d.get("domain_results", []),
                "axis_overlaps": rec_d.get("axis_overlaps", []),
            }
        draft["verdict"] = rec_d.get("composite_verdict", "DRAFT")
        draft["domains"] = sorted({
            r.get("domain") for r in (rec_d.get("domain_results") or [])
            if r.get("domain")
        })
        draft["_engine_trail"] = {
            "source": used_source,
            "atomic_claims": rec_d.get("atomic_claims", []),
            "quarantined_claims": rec_d.get("quarantined_claims", []),
            "axis_overlaps": rec_d.get("axis_overlaps", []),
            "content_hash": rec_d.get("content_hash"),
        }
    except Exception as exc:
        draft["_engine_error"] = str(exc)[:240]
        draft["_engine_note"] = (
            "Polymathic run failed for this candidate. Draft returned "
            "without computed verdict. Curator: run the math manually "
            "or refine the candidate text."
        )

    return {
        "draft": draft,
        "instructions_for_curator": (
            "1. Review the draft. Check that the verdict the engine produced "
            "matches your intent.\n"
            "2. Replace the placeholder wisdom prose with a short dry note "
            "in the Almanac's voice — what does the math actually show?\n"
            "3. For sayings: write the verification paragraph. "
            "For protocols: write the pre_run.summary one-liner.\n"
            "4. Adjust category, triggers, and id slug as needed.\n"
            "5. When ready, append the cleaned-up entry as one JSON line "
            "to data/almanac/entries.jsonl, and bounce the engine to load."
        ),
    }


def _predict_axes_from_query(qlower: str) -> set:
    """Stem-based axis prediction. Local helper for almanac scoring."""
    from .. import grid as _grid
    AXIS_STEMS = {
        "encoding":              ["encod", "encrypt", "decod", "symbol", "cipher"],
        "metabolism":            ["metabol", "growth", "decay", "nutri", "energ"],
        "reasoning":             ["reason", "logic", "proof", "compute", "calculat", "infer"],
        "physical_substance":    ["physic", "matter", "substanc", "spatial", "geometr"],
        "authority_trust":       ["author", "trust", "consent", "consensus", "legitim", "sign"],
        "time_sequence":         ["time", "sequenc", "order", "before", "after", "deadline", "period"],
        "conservation_balance":  ["balanc", "conserv", "equilibri", "invariant", "preserv"],
    }
    predicted: set = set()
    for ax, stems in AXIS_STEMS.items():
        if any(s in qlower for s in stems):
            predicted.add(ax)
    for ax in _grid.DIMENSIONS:
        if ax.replace('_', ' ') in qlower or ax in qlower:
            predicted.add(ax)
    for dom in _grid.AXIS_DIMENSIONS:
        stem = dom[:6] if len(dom) >= 6 else dom
        if dom in qlower or (len(stem) >= 5 and stem in qlower):
            predicted.update(_grid.AXIS_DIMENSIONS[dom])
    return predicted


# ============================================================
# Engine-substrate tools (close the parity gap with HTTP API)
# ============================================================
# Until this section, the MCP surface was 76 verifier tools — all
# deterministic checks. Humans at /, /walk, /apothecary, /curriculum
# have a much wider engine. These tools expose the rest of the engine
# to agents so the dual-audience framing (humans + agents) is honest.
#
# Each tool calls the local HTTP engine at 127.0.0.1:8000 (or
# CONCORDANCE_API_URL if set) and returns the JSON response. Same
# behavior whether invoked via stdio or via /mcp HTTP.

_LOCAL_API_BASE = (os.environ.get("CONCORDANCE_API_URL") or "http://127.0.0.1:8000").rstrip("/")


def _engine_get(path: str, **params) -> Dict[str, Any]:
    """GET an engine endpoint; defensive, returns {error: ...} on failure."""
    import urllib.parse as _up
    q = _up.urlencode({k: v for k, v in params.items() if v is not None and v != ""})
    url = f"{_LOCAL_API_BASE}{path}"
    if q:
        url = f"{url}?{q}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "url": url}


def _engine_post(path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST JSON to an engine endpoint; defensive."""
    url = f"{_LOCAL_API_BASE}{path}"
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}", "url": url}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}", "url": url}


@mcp.tool()
def apothecary_compound(condition: str, lang: str = "en") -> Dict[str, Any]:
    """Compound a remedy for a stated condition from across the substrate.

    For a condition (e.g. "anxiety", "I can't forgive my brother", "exhausted
    and bitter"), the engine retrieves one packet of each ingredient kind —
    a Scripture anchor, a protocol to walk, a mind practice, a parable, a
    body insight, a philosopher's note, an almanac confirmation — and
    returns the compounded card. The engine eliminates; it doesn't invent.
    Each ingredient is a packet already in the keeping.

    Args:
        condition: Free-text condition the visitor is carrying.
        lang: 2-letter language code for Scripture text (default 'en').
            Supports en/es/zh/fr/pt/de/ko/ja/ar/ru/fa/vi/it/my/uk/nl/ro/ht/he/la/hi/sw.

    Returns the full compound card with all ingredients."""
    return _engine_get("/apothecary", condition=condition, lang=lang)


@mcp.tool()
def curriculum_list() -> Dict[str, Any]:
    """Return every primary-education unit across all 8 tracks.

    Tracks: phonics, math, reading, writing, science, social_studies,
    bible_curriculum, workready. Returns grouped units with track totals.
    Free K-2 curriculum — each unit has rule, examples, manipulative,
    three modes, wedges, check, prerequisites, next."""
    return _engine_get("/curriculum")


@mcp.tool()
def unit_get(unit_id: str) -> Dict[str, Any]:
    """Fetch a single curriculum unit by id. The engine tries each track
    until it finds the unit.

    Args:
        unit_id: e.g. 'phonics_short_a', 'math_counting_to_20',
                 'bible_psalm_23', 'science_simple_machines'.

    Returns the full record: rule, examples, manipulative, modes, wedges,
    check (with answer + teaching_note), prerequisites, next, summary, and
    any inline SVG diagrams."""
    # Try each track in order — same logic the /unit.html page uses
    for track in ["phonics", "math", "reading", "writing", "science",
                  "bible_curriculum", "social_studies", "workready"]:
        result = _engine_get(f"/{track}/{unit_id}")
        if "error" not in result:
            return result
    return {"error": f"unit {unit_id!r} not found in any track"}


@mcp.tool()
def herb_get(herb_id: Optional[str] = None) -> Dict[str, Any]:
    """Fetch herb monographs — botanical remedies with evidence-honest
    verdicts (CONFIRMED / MIXED / DISCORDANT).

    Args:
        herb_id: Optional. If provided ('herb_ginger', 'herb_chamomile',
                 etc.), returns that single monograph with all preparations,
                 safety notes, evidence verdicts, growing instructions, and
                 inline SVG. If omitted, returns the full list of 12 herbs.

    Each verdict carries a note explaining the evidence. Folk claims that
    don't hold up are marked DISCORDANT (e.g. ginger 'detox', raw elderberry,
    honey for infants under 1)."""
    if herb_id:
        return _engine_get(f"/herbs/{herb_id}")
    return _engine_get("/herbs")


@mcp.tool()
def packets_search(query: str, limit: int = 12, kinds: Optional[str] = None) -> Dict[str, Any]:
    """Search the unified packet substrate across every lens.

    Returns packets from: almanac, scripture (proverbs/psalms/sermon-on-mount/
    ecclesiastes/james), Sermon on the Mount, philosophers (Aurelius/
    La Rochefoucauld/Augustine/Imitation/Boethius/Pirkei Avot/Pilgrim's),
    early Fathers (Didache/Clement/Polycarp/Barnabas/Ignatius/Martyrdom),
    parables, body layers, mind practices, archetypes, fieldkit, protocols,
    Easton's Bible Dictionary, Aesop's Fables, training, places, curriculum
    units across 8 tracks, herb monographs, wedges, steward audit, receipts.

    Args:
        query: Free-text search; multi-word AND-matched.
        limit: Max packets to return (default 12, max 500).
        kinds: Optional comma-separated kinds filter (e.g. 'phonics_unit,herb_monograph').

    Returns: {q, total, packets: [{kind, id, title, verdict, domains, axes, summary, permalink, score}]}"""
    return _engine_get("/index/packets/search", q=query, limit=limit, kinds=kinds)


@mcp.tool()
def almanac_search(query: str, limit: int = 12) -> Dict[str, Any]:
    """Search the almanac specifically — verified claims with CONFIRMED /
    MIXED / MISMATCH / OBSOLETE / DISCORDANT verdicts.

    The almanac is the engine's ledger of falsifiable claims. ~880+ entries
    across weather, agriculture, scripture, health, finance, logic, biology,
    sociology, and more.

    Args:
        query: Free-text search.
        limit: Max entries (default 12).

    Returns the matching almanac entries with their full verdict trails."""
    return _engine_get("/index/packets/search", q=query, limit=limit, kinds="almanac")


@mcp.tool()
def polymathic_run(situation: str, visitor_id: str = "mcp_agent") -> Dict[str, Any]:
    """Multi-domain synthesis — every applicable verifier fires in
    parallel and returns a composite verdict.

    Requires the engine to have an Anthropic API key configured for the
    oracle classification step. If not configured, returns OUT_OF_SCOPE
    honestly rather than fabricating.

    Args:
        situation: Free-text situation that spans multiple domains
                   (e.g. "I'm building a wind turbine for off-grid power
                    in a region prone to lightning storms").
        visitor_id: Opaque hex (default 'mcp_agent'). Per-visitor history
                    keeps the polymathic substrate auditable.

    Returns the composite verdict + per-domain results."""
    return _engine_post("/polymathic", {"situation": situation, "visitor_id": visitor_id})


@mcp.tool()
def walk_start(situation: str, visitor_id: str = "mcp_agent") -> Dict[str, Any]:
    """Begin a four-gate walk with the Shepherd.

    The Shepherd asks four gate questions in order (RED, FLOOR, BROTHERS,
    GOD) about a hard decision the visitor is carrying. Each gate is the
    visitor's own answer; the engine never decides for them.

    Args:
        situation: Free-text — what is the visitor carrying?
        visitor_id: Opaque hex.

    Returns the walk record with the first gate question. Subsequent
    answers go through /coach/journal/answer (not yet MCP-wired)."""
    return _engine_post("/coach/journal/start", {
        "situation": situation,
        "visitor_id": visitor_id,
    })


@mcp.tool()
def scribe_submit(text: str, title: str = "", visitor_id: str = "mcp_agent",
                  contributor_handle: str = "") -> Dict[str, Any]:
    """Write something to the keeping. The Scribe captures it; the
    keeping decides whether to promote it to the almanac. Operator-attended.

    Args:
        text: The writing to submit.
        title: Optional short title.
        visitor_id: Opaque hex.
        contributor_handle: Optional handle for attribution (e.g. 'mharris').

    Returns the writing's id, status, and view URL."""
    return _engine_post("/scribe/intake", {
        "text": text,
        "title": title,
        "visitor_id": visitor_id,
        "contributor_handle": contributor_handle,
    })


@mcp.tool()
def mastery_mark(visitor_id: str, unit_id: str, state: str = "mastered",
                 note: str = "") -> Dict[str, Any]:
    """Record that a visitor (or the visitor's learner) worked through a
    curriculum unit. Append-only — the trail is preserved.

    Args:
        visitor_id: Opaque hex.
        unit_id: Curriculum unit id.
        state: 'working' | 'mastered' | 'set_aside' | 'reset' (default 'mastered').
        note: Optional free-text observation.

    Returns the recorded row. The visitor's full mastery state is at
    /mastery/visitor?visitor_id=X."""
    return _engine_post("/mastery/mark", {
        "visitor_id": visitor_id,
        "unit_id": unit_id,
        "state": state,
        "note": note,
    })


# ============================================================
# Flow tools — composition over the engine's primitives
# ============================================================
# Flows are named, registered sequences of tool calls + branches +
# state. Agents call flow_list to discover them, flow_run to execute.
# Same semantics as the human-facing "What next?" cards.

@mcp.tool()
def flow_list(audience: str = "agent", starts_from: str = "") -> Dict[str, Any]:
    """List every registered flow.

    Args:
        audience: 'human' | 'agent' | 'robot' (default 'agent'). Filters
                  to flows whose audience array contains this value.
        starts_from: optional filter by starts_from field ('walk',
                     'apothecary', 'curriculum', 'any').

    Returns: {flows: [{id, name, description, audience, starts_from,
                       first_input, step_count, outputs}]}"""
    params = {"audience": audience}
    if starts_from:
        params["starts_from"] = starts_from
    return _engine_get("/flows", **params)


@mcp.tool()
def flow_run(flow_id: str, state: Optional[Dict[str, Any]] = None,
             run_id: Optional[str] = None) -> Dict[str, Any]:
    """Execute (or resume) a flow.

    To start a new flow: pass flow_id and initial state including any
    inputs the flow's first_input declares.

    Example — start walk_to_keep:
        flow_run("walk_to_keep", {"situation": "...", "visitor_id": "agent_X"})

    The flow runs until it hits an `input` step (pauses) or completes.
    On pause, returns {status: 'waiting_for_input', expects: <key>,
    label: <prompt>, run_id: <id>}. The caller resumes by calling
    flow_run again with the same run_id and the new input added to state.

    On complete, returns {status: 'complete', state, outputs, run_id}.

    Flow definitions live as data at /flows/<id> — call flow_list first
    to discover what's available, or fetch one by id."""
    payload = {"flow_id": flow_id}
    if state:
        payload["state"] = state
    if run_id:
        payload["run_id"] = run_id
    return _engine_post("/flow/run", payload)


# ============================================================
# Card library tools — the substrate, walks, atlas, notes, stacks
# Added 2026-05-19. The 11,000+ card library Matt built today is now
# walkable by agents the same way humans walk it at /walks.html.
# ============================================================

@mcp.tool()
def cards_walk(query: str, k: int = 7, asked_by: str = "mcp_agent") -> Dict[str, Any]:
    """Ask Shepherd to pull cards for a query. The signature operation of the
    card system.

    Cache-first: same question previously asked → cached walk returned, no
    re-search. Otherwise inverted-index lookup → score top-k candidates →
    return cards with source, shelf, and Shepherd narration per step.

    Use this when an agent wants the substrate's answer to a question.
    Cards carry source + link-back; agents should cite the cards back to
    the user, never present them as their own.

    Args:
        query: the question or topic. Plain English; Shepherd handles tokens.
        k: how many cards to return (default 7, max 20).
        asked_by: optional agent identifier for the replay log.

    Returns: {query, step_count, steps: [...], narration, corpus_size,
             cache_hit?, walk_card_id?}
    """
    return _engine_post("/cards/walk", {"query": query, "k": min(k, 20), "asked_by": asked_by})


@mcp.tool()
def card_get(card_id: str) -> Dict[str, Any]:
    """Get a single card by id. Returns full content: title, body, source
    (with authority_tier and link-back URL), shelf, box, bands, connections,
    metrics, lifecycle_stage, volatility.

    Card IDs look like `card_n_<hash>` (note), `card_c_<hash>` (connection),
    `card_w_<hash>` (walk). Get them from cards_walk results, atlas_paths,
    or cards_browse.
    """
    return _engine_get(f"/cards/{card_id}")


@mcp.tool()
def cards_browse(shelf: Optional[str] = None, box: Optional[str] = None,
                 kind: Optional[str] = None, lifecycle: Optional[str] = None,
                 limit: int = 50) -> Dict[str, Any]:
    """List cards filtered by shelf, box, kind, lifecycle.

    Common shelves: codex, classics, dictionary, patristics, hymns, recipes,
    maker, animation, atlas, connections.

    Common kinds: note (default content), connection (graph edges),
    walk (curated paths), community_note, search, stack.

    Lifecycle: public, featured, public_review, private, archived, quarantine.

    Returns {count, total_matching, cards: [...]} — cards in this list are
    summary objects; use card_get(id) for full content.
    """
    return _engine_get("/cards", shelf=shelf, box=box, kind=kind,
                       lifecycle=lifecycle, limit=limit)


@mcp.tool()
def card_connections(card_id: str) -> Dict[str, Any]:
    """Get a card's connections — outgoing (this card cites X) and inbound
    (X cites this card). The graph is bidirectional: navigation works from
    either end.

    Use this to find: scripture proof texts for a catechism Q, related
    creeds, the next section in a narrative work (Pilgrim's Progress,
    Augustine Confessions), community notes annotating the card.

    Returns {card_id, outgoing: [...], inbound: [...], outgoing_count, inbound_count}
    """
    return _engine_get(f"/cards/{card_id}/connections")


@mcp.tool()
def cards_stats() -> Dict[str, Any]:
    """Substrate composition: total cards, breakdown by shelf / kind /
    authority_tier / lifecycle_stage. Also returns working-set cache stats.

    Useful when an agent needs to know what's in the library before deciding
    whether to walk it. Numbers are live as of last call.
    """
    return _engine_get("/cards/stats")


@mcp.tool()
def shepherd_interview(query: str, interview_id: Optional[str] = None,
                       skip_to_walk: bool = False,
                       asked_by: str = "mcp_agent") -> Dict[str, Any]:
    """Pre-flight conversational interview before walking the cards. Shepherd
    asks up to 3 clarifying questions (audience / tradition lens / use intent /
    specificity) before any expensive search fires.

    Two-call pattern for new interview:
      1. shepherd_interview(query="baptism")
         → returns {state:"needs_followup", shepherd_says:"...", interview_id, ask_kind}
      2. shepherd_interview(query="for my kids", interview_id=<id>)
         → may converge to {state:"ready_to_walk", shaped_query} or ask another
            follow-up

    Pass skip_to_walk=true to converge immediately with whatever Shepherd
    has inferred so far.

    Once state="ready_to_walk", pass shaped_query into cards_walk.
    """
    return _engine_post("/shepherd/interview", {
        "query": query, "interview_id": interview_id,
        "skip_to_walk": skip_to_walk, "asked_by": asked_by,
    })


@mcp.tool()
def atlas_paths(lifecycle: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """List curated Atlas paths — walks the operator (or the community) has
    canonized as recommended ways through the substrate.

    Examples in the live library: "The Trinity in 4 cards", "A child's first
    catechism walk", "How the Reformers read justification".

    Filter by lifecycle: featured, public, public_review.
    """
    return _engine_get("/atlas/paths", lifecycle=lifecycle, limit=limit)


@mcp.tool()
def atlas_path(walk_card_id: str) -> Dict[str, Any]:
    """Hydrate a single Atlas path: full card content for each step, with
    per-step narration. Use this after atlas_paths() to read a walk end-to-end.

    Returns {card_id, title, body, author, lifecycle_stage, step_count,
             cards: [{card_id, title, body, source, narration}], query}
    """
    return _engine_get(f"/atlas/paths/{walk_card_id}")


@mcp.tool()
def daily_card(date: Optional[str] = None) -> Dict[str, Any]:
    """Today's card. Deterministic worldwide: same date → same card. The pool
    is restricted to permanent + public/featured cards from foundational
    tiers (Words in Red, Scripture, Catechism, Creed, Father, Matt).

    Args:
        date: optional ISO date YYYY-MM-DD. Omit for today's card.

    Returns {date, card: {id, title, body, source, shelf, box, url}, pool_size}
    """
    return _engine_get("/daily-card", **({"date": date} if date else {}))


@mcp.tool()
def card_notes(card_id: str, balance_only: bool = False) -> Dict[str, Any]:
    """Community notes annotating a card. Notes never overwrite the card —
    they surface alongside as "Balance" when raters from 2+ different
    traditions agree (bridge-rating, not majority).

    Args:
        card_id: the card being annotated.
        balance_only: if True, return only notes that crossed the bridge
                      threshold; if False (default), return all notes
                      including unsurfaced.

    Returns {card_id, count, notes/balance_notes: [...]}
    """
    path = f"/notes/by_card/{card_id}/balance" if balance_only else f"/notes/by_card/{card_id}"
    return _engine_get(path)


@mcp.tool()
def library_health() -> Dict[str, Any]:
    """Card library operational health: total cards, breakdown by lifecycle
    stage, total citations in the graph, flagged cards count, retracted
    count, pending promotions in the operator queue, sum of metrics.

    Use this to know the state of the substrate before committing to a
    long walk or a large bulk operation.
    """
    return _engine_get("/promotion/health")


@mcp.tool()
def stack_get(household_id: str) -> Dict[str, Any]:
    """Read a household's card stack: paperclipped cards, authored cards,
    forked cards, shared-inbox, tip total.

    Stacks are private by default — this endpoint returns the stack contents
    only if the household_id is well-formed; agents should respect privacy
    and not enumerate household IDs.

    Returns {household_id, paperclipped_card_ids, authored_card_ids,
             forked_card_ids, tip_total_usd, inbox, created_at, updated_at}
    """
    return _engine_get(f"/stacks/{household_id}")


# ============================================================
# Prompts — pre-built templates an agent can offer the user
# ============================================================
# MCP prompts are NOT actions. They're text templates an agent's user can
# pick from a dropdown to insert into their prompt. These canonicalize the
# engine's load-bearing flows so an agent client surfaces them as menu items.

@mcp.prompt()
def walk_this(situation: str) -> str:
    """Walk a hard decision through the four gates (RED, FLOOR, BROTHERS, GOD)."""
    return (
        f"Walk this situation through the four gates with the Shepherd: {situation}\n\n"
        f"For each gate, surface the relevant Scripture, settled wisdom from the "
        f"keeping, and questions the visitor answers themselves. The engine never "
        f"decides; it walks. Halt on first failure if any gate cannot be passed."
    )


@mcp.prompt()
def walk_the_cards(question: str) -> str:
    """Walk the card library to teach the user how to think through a question."""
    return (
        f"The user has asked: {question}\n\n"
        f"First, call shepherd_interview to shape the question (audience, "
        f"tradition lens, use intent) if the question is broad. If specific, "
        f"call cards_walk directly.\n\n"
        f"Then read the surfaced cards in order. Cite each by its source — "
        f"never present a card's content as your own. The cards carry their "
        f"own authority (scripture, catechism, creed, father, matt). Your "
        f"job is to walk them with the user, point at the connections "
        f"between them, and let the substrate teach.\n\n"
        f"Never synthesize when a card already answers. Never paraphrase "
        f"scripture or catechism — quote verbatim with the reference. The "
        f"engine eliminates what is not the answer so the narrow path is "
        f"illuminated by what survives."
    )


@mcp.prompt()
def compound_this(condition: str) -> str:
    """Compound a remedy from the substrate for a stated condition."""
    return (
        f"Compound a remedy for: {condition}\n\n"
        f"Use the apothecary_compound tool. The engine retrieves one packet of "
        f"each ingredient kind: Scripture anchor, protocol, mind practice, parable, "
        f"body insight, philosopher's note, almanac confirmation. Read the trail."
    )


@mcp.prompt()
def verify_this(claim: str) -> str:
    """Verify a single claim through the appropriate domain verifier."""
    return (
        f"Verify this claim: {claim}\n\n"
        f"Pick the appropriate verify_* tool based on domain (math, chemistry, "
        f"biology, statistics, etc.). The verifier returns CONFIRMED / MIXED / "
        f"MISMATCH / OBSOLETE / DISCORDANT with a reasoning trail. Read the trail."
    )


@mcp.prompt()
def find_precedent(situation: str) -> str:
    """Find precedent in the substrate for a stated situation."""
    return (
        f"Find precedent for: {situation}\n\n"
        f"Use packets_search to walk the unified packet substrate across all "
        f"lenses — almanac, scripture, philosophers, parables, fieldkit, training. "
        f"Surface the closest precedent and overlay it on the situation."
    )


@mcp.prompt()
def teach_a_child(topic: str) -> str:
    """Find the curriculum unit to teach a child about a topic."""
    return (
        f"Help a parent teach a child about: {topic}\n\n"
        f"Use curriculum_list to find the right track and unit_get to fetch the "
        f"full record. Each unit has rule + examples + manipulative + three modes "
        f"(coach reads · take turns · I read/solve) + wedges + check. Walk the "
        f"parent through the modes in order."
    )


# ============================================================
# Resources — read-only substrate exposed as MCP resources
# ============================================================

@mcp.resource("concordance://identity")
def resource_identity() -> str:
    """The full doctrinal statement — who the engine serves and how."""
    result = _engine_get("/identity")
    if "error" in result:
        return _MCP_INSTRUCTIONS
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.resource("concordance://curriculum")
def resource_curriculum() -> str:
    """The full primary curriculum — 8 tracks, ~66 units."""
    return json.dumps(_engine_get("/curriculum"), indent=2, ensure_ascii=False)


@mcp.resource("concordance://herbs")
def resource_herbs() -> str:
    """All herb monographs with evidence-honest verdicts."""
    return json.dumps(_engine_get("/herbs"), indent=2, ensure_ascii=False)


@mcp.resource("concordance://manifest")
def resource_manifest() -> str:
    """Engine manifest — endpoints, capabilities, doctrine link."""
    result = _engine_get("/manifest")
    if "error" in result:
        result = _engine_get("/")  # fallback to homepage HTML
    return json.dumps(result, indent=2, ensure_ascii=False) if isinstance(result, dict) else str(result)


def main() -> None:
    """Entry point for the MCP server. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
