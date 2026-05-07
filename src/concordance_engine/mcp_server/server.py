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
def verify_chemistry(equation: str, temperature_K: Optional[float] = None) -> Dict[str, Any]:
    """Verify a chemical equation balances (atoms and charge) and optionally
    that the temperature is physical (positive Kelvin).

    Equation format: '2 H2 + O2 -> 2 H2O'. Supports nested groups (Cu(OH)2),
    charges (Fe^2+, MnO4^-), and ionic forms. On MISMATCH, returns the
    correctly balanced coefficients in data.balanced_lhs / balanced_rhs.
    """
    return tools.verify_chemistry(equation, temperature_K)


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
# Statistics
# ---------------------------------------------------------------------------

@mcp.tool()
def verify_statistics_pvalue(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute a p-value from supplied test inputs and verify against claimed_p.

    spec must include 'test' (one of: two_sample_t, one_sample_t, z, chi2, f)
    plus the corresponding inputs. Optional: claimed_p (to verify), tolerance (default 1e-3).
    """
    return tools.verify_statistics_pvalue(spec)


@mcp.tool()
def verify_statistics_multiple_comparisons(
    raw_p_values: List[float],
    method: str,
    alpha: float = 0.05,
    claimed_rejected_indices: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Apply Bonferroni or BH (Benjamini-Hochberg) correction and verify the
    rejection set at alpha matches the claim, if a claim is provided.
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
    Pass spec as ACOUS_VERIFY contents."""
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
    Pass spec as GEO_VERIFY contents."""
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
    Pass spec as HYD_VERIFY contents."""
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


def main() -> None:
    """Entry point for the MCP server. Runs over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
