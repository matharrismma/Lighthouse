"""MCP tool implementations.

FastMCP server (server.py) imports the function-style API directly. List-style
API (TOOLS, list_tools, call_tool) used as fallback. ALL_TOOLS exposes a flat
{name: callable} map for tests and embedders.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from ..engine import (
    EngineConfig, validate_packet as _engine_validate,
    validate_and_seal as _engine_seal,
)
from ..verifiers import (
    chemistry, physics, mathematics, statistics,
    computer_science, biology, governance, scripture,
)
from ..verifiers import energy as _energy
from ..verifiers import acoustics as _acoustics
from ..verifiers import agriculture as _agriculture
from ..verifiers import astronomy as _astronomy
from ..verifiers import calendar_time as _calendar_time
from ..verifiers import combinatorics as _combinatorics
from ..verifiers import cryptography as _cryptography
from ..verifiers import document_validation as _document_validation
from ..verifiers import electrical as _electrical
from ..verifiers import exercise_science as _exercise_science
from ..verifiers import finance as _finance
from ..verifiers import formal_logic as _formal_logic
from ..verifiers import genetics as _genetics
from ..verifiers import geography as _geography
from ..verifiers import geology as _geology
from ..verifiers import geometry as _geometry
from ..verifiers import hydrology as _hydrology
from ..verifiers import information_theory as _information_theory
from ..verifiers import linguistics as _linguistics
from ..verifiers import manufacturing as _manufacturing
from ..verifiers import meteorology as _meteorology
from ..verifiers import music_theory as _music_theory
from ..verifiers import networking as _networking
from ..verifiers import number_theory as _number_theory
from ..verifiers import nutrition as _nutrition
from ..verifiers import optics as _optics
from ..verifiers import photography as _photography
from ..verifiers import sports_analytics as _sports_analytics
from ..verifiers import witness as _witness
from ..verifiers import quantum_computing as _quantum_computing
from ..verifiers import medicine as _medicine
from ..verifiers import cybersecurity as _cybersecurity
from ..verifiers import economics as _economics
from ..verifiers import labor as _labor
from ..verifiers import real_estate as _real_estate
from ..verifiers import construction as _construction
from ..verifiers import soil_science as _soil_science
from ..verifiers.base import VerifierResult
from ..walkthrough import (
    render_walkthrough, render_walkthrough_compact, render_walkthrough_html,
)
from ..ledger import find_closest as _find_closest


def _r(r: VerifierResult) -> Dict[str, Any]:
    return {"status": r.status, "detail": r.detail, "data": r.data}


# ---------------------------------------------------------------------
# Function-style API
# ---------------------------------------------------------------------

def validate_packet(packet, now_epoch=None):
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    res = _engine_validate(packet, now_epoch=now_epoch, config=cfg)
    return {
        "overall": res.overall,
        "gate_results": [
            {"gate": gr.gate, "status": gr.status,
             "reasons": gr.reasons, "details": gr.details}
            for gr in res.gate_results
        ],
    }


def seal_packet(packet, now_epoch=None, auto_precedent=False):
    """Run a packet through the four gates and return the sealed
    WitnessRecord as JSON. The agent surface for the canonical sealed
    record — same object the human walkthrough renderer consumes.

    When `auto_precedent=True`, the Audit Chain is queried for the
    closest comparable precedent and (if found) sealed into the record.
    """
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet.get("id"),
    )
    return rec.to_dict()


def walkthrough_packet(
    packet,
    now_epoch=None,
    fmt="markdown",
    expand_traces=False,
    auto_precedent=False,
):
    """Run a packet and return a human-readable walkthrough.

    `fmt` selects the renderer: "markdown" (Socratic walk, default),
    "compact" (one-screen status), or "html" (self-contained HTML page).
    `expand_traces=True` adds the verifier trace section to markdown
    and HTML outputs (compact ignores it). `auto_precedent=True` pulls
    in the closest comparable precedent before sealing.
    """
    cfg = EngineConfig(schema_path="schema/packet.schema.json")
    closest = _find_closest(packet) if auto_precedent else None
    rec = _engine_seal(
        packet, now_epoch=now_epoch, config=cfg,
        closest_case=closest, packet_id=packet.get("id"),
    )
    fmt = (fmt or "markdown").lower()
    if fmt == "compact":
        return render_walkthrough_compact(rec)
    if fmt == "html":
        return render_walkthrough_html(rec, expand_traces=expand_traces)
    return render_walkthrough(rec, expand_traces=expand_traces)


def verify_chemistry(equation, temperature_K=None):
    out = {}
    eq_r = chemistry.verify_equation(equation, balance_if_unbalanced=True)
    out["equation"] = _r(eq_r)
    if eq_r.status == "MISMATCH" and eq_r.data and "balanced_lhs" in eq_r.data:
        out["balanced_form"] = f"{eq_r.data['balanced_lhs']} -> {eq_r.data['balanced_rhs']}"
        out["balanced_coefficients"] = eq_r.data.get("balanced_coefficients")
    if temperature_K is not None:
        out["temperature"] = _r(chemistry.verify_temperature(temperature_K))
    return out


def verify_physics_dimensional(equation, symbols):
    return _r(physics.verify_dimensional_consistency(equation, symbols))


def verify_physics_conservation(before, after, tolerance_relative=1e-6,
                                 tolerance_absolute=0.0, law=None):
    if law:
        return _r(physics.verify_named_conservation(
            law, before, after,
            tolerance_relative=tolerance_relative,
            tolerance_absolute=tolerance_absolute,
        ))
    return _r(physics.verify_conservation(
        before, after,
        tolerance_relative=tolerance_relative,
        tolerance_absolute=tolerance_absolute,
    ))


def verify_mathematics(mode, params):
    """Mode dispatcher: equality|derivative|integral|limit|solve|matrix|inequality|series|ode."""
    mode = (mode or "").lower()
    out = {}
    import sympy as sp

    if mode == "equality":
        return _r(mathematics.verify_equality(params))
    if mode == "derivative":
        function = params["function"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        actual = sp.diff(f, x)
        out["computed_derivative"] = str(actual)
        if "claimed_derivative" in params:
            out.update(_r(mathematics.verify_derivative(params)))
        else:
            out["status"] = "CONFIRMED"
            out["detail"] = f"d/d{variable} of {function} = {actual}"
        return out
    if mode == "integral":
        integrand = params["integrand"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        f = sp.sympify(integrand, locals={variable: x})
        try:
            anti = sp.integrate(f, x)
            out["computed_antiderivative"] = str(anti)
        except Exception as e:
            out["computed_antiderivative"] = None
            out["compute_error"] = str(e)
        if "claimed_antiderivative" in params:
            out.update(_r(mathematics.verify_integral(params)))
        return out
    if mode == "limit":
        function = params["function"]
        variable = params.get("variable", "x")
        point = params["point"]
        x = sp.Symbol(variable)
        f = sp.sympify(function, locals={variable: x})
        try:
            actual = sp.limit(f, x, sp.sympify(str(point)))
            out["computed_limit"] = str(actual)
        except Exception as e:
            out["computed_limit"] = None
            out["compute_error"] = str(e)
        if "claimed_limit" in params:
            out.update(_r(mathematics.verify_limit(params)))
        return out
    if mode == "solve":
        eq = params["equation"]
        variable = params.get("variable", "x")
        x = sp.Symbol(variable)
        if "=" in eq and "==" not in eq:
            lhs, rhs = eq.split("=", 1)
            eq_expr = sp.sympify(lhs, locals={variable: x}) - sp.sympify(rhs, locals={variable: x})
        else:
            eq_expr = sp.sympify(eq, locals={variable: x})
        actual = [str(s) for s in sp.solve(eq_expr, x)]
        out["computed_solutions"] = actual
        if "claimed_solutions" in params:
            out.update(_r(mathematics.verify_solve(params)))
        return out
    if mode == "matrix":
        return _r(mathematics.verify_matrix(params))
    if mode == "inequality":
        return _r(mathematics.verify_inequality(params))
    if mode == "series":
        return _r(mathematics.verify_series(params))
    if mode == "ode":
        return _r(mathematics.verify_ode(params))
    return {"status": "ERROR", "detail": f"unknown mode {mode!r}",
            "data": {"valid_modes": ["equality", "derivative", "integral", "limit",
                                     "solve", "matrix", "inequality", "series", "ode"]}}


def verify_statistics_pvalue(spec):
    return _r(statistics.verify_pvalue_calibration(spec))


def verify_statistics_multiple_comparisons(raw_p_values, method, alpha=0.05,
                                            claimed_rejected_indices=None):
    spec = {"raw_p_values": raw_p_values, "method": method, "alpha": alpha}
    if claimed_rejected_indices is not None:
        spec["claimed_rejected_indices"] = claimed_rejected_indices
    return _r(statistics.verify_multiple_comparisons(spec))


def verify_statistics_confidence_interval(estimate, ci_low, ci_high, *, spec=None):
    if spec:
        full = dict(spec)
        full.setdefault("estimate", estimate)
        full.setdefault("ci_low", ci_low)
        full.setdefault("ci_high", ci_high)
        return _r(statistics.verify_confidence_interval(full))
    return _r(statistics.verify_confidence_interval({
        "estimate": estimate, "ci_low": ci_low, "ci_high": ci_high,
    }))


def verify_computer_science(code, function_name=None, test_cases=None,
                             input_generator=None, claimed_class=None,
                             sizes=None, tolerance=0.40, *,
                             determinism_trials=None, claimed_space_class=None):
    out = {"static_termination": _r(computer_science.verify_static_termination(code))}
    if function_name and test_cases:
        out["functional_correctness"] = _r(computer_science.verify_functional_correctness({
            "code": code, "function_name": function_name, "test_cases": test_cases,
        }))
    if function_name and input_generator and claimed_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator, "claimed_class": claimed_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["runtime_complexity"] = _r(computer_science.verify_runtime_complexity(spec))
    if function_name and input_generator and claimed_space_class:
        spec = {"code": code, "function_name": function_name,
                "input_generator": input_generator,
                "claimed_space_class": claimed_space_class,
                "tolerance": tolerance}
        if sizes is not None:
            spec["sizes"] = sizes
        out["space_complexity"] = _r(computer_science.verify_space_complexity(spec))
    if function_name and test_cases and determinism_trials and determinism_trials >= 2:
        out["determinism"] = _r(computer_science.verify_determinism({
            "code": code, "function_name": function_name,
            "test_cases": test_cases, "trials": determinism_trials,
        }))
    return out


def verify_biology(n_replicates=None, min_replicates=3, assay_classes=None,
                    min_assay_classes=2, dose_response=None, power_analysis=None,
                    *, bio_control=None, hardy_weinberg=None, primer=None,
                    molarity=None, mendelian=None):
    spec = {}
    if n_replicates is not None:
        spec["n_replicates"] = n_replicates
        spec["min_replicates"] = min_replicates
    if assay_classes is not None:
        spec["assay_classes"] = assay_classes
        spec["min_assay_classes"] = min_assay_classes
    if dose_response is not None:
        spec["dose_response"] = dose_response
    if power_analysis is not None:
        spec["power_analysis"] = power_analysis
    if hardy_weinberg is not None:
        spec["hardy_weinberg"] = hardy_weinberg
    if primer is not None:
        spec["primer"] = primer
    if molarity is not None:
        spec["molarity"] = molarity
    if mendelian is not None:
        spec["mendelian"] = mendelian
    packet = {"BIO_VERIFY": spec}
    if bio_control is not None:
        packet["BIO_CONTROL"] = bio_control
    results = biology.run(packet)
    return {"checks": [_r(r) for r in results]}


def verify_governance_decision_packet(decision_packet, witness_count=None, *, domain=None):
    out = {"shape": _r(governance.verify_decision_packet_shape(decision_packet))}
    if witness_count is not None:
        out["witness_consistency"] = _r(
            governance.verify_witness_count_consistency(
                decision_packet, {"witness_count": witness_count}))
    if domain:
        out["domain_profile"] = _r(governance.verify_domain_profile(domain, decision_packet))
    return out


def verify_energy(spec):
    """Run all applicable energy-system checks against the supplied spec.

    Spec is the contents of the ENERGY_VERIFY field — see
    `concordance_engine.verifiers.energy` docstring for the full
    field reference. Each check fires when its inputs are present;
    unsupplied checks return NOT_APPLICABLE.

    Off-grid system sizing, wire voltage drop, battery sizing,
    solar daily yield, peak-load-vs-inverter, runtime, kWh↔Wh,
    efficiency (with heat-pump COP carve-out), power balance.
    """
    packet = {"ENERGY_VERIFY": spec or {}}
    results = _energy.run(packet)
    return {"checks": [_r(r) for r in results]}


def verify_acoustics(spec):
    """Wave speed/frequency/wavelength, decibel ratios, Doppler shift, harmonic frequencies."""
    return {"checks": [_r(r) for r in _acoustics.run({"ACOUS_VERIFY": spec or {}})]}


def verify_agriculture(spec):
    """Hardiness zones, soil pH range, crop rotation rules, livestock stocking density."""
    return {"checks": [_r(r) for r in _agriculture.run({"AG_VERIFY": spec or {}})]}


def verify_astronomy(spec):
    """Kepler's third law, gravitational force, stellar parallax distance, distance modulus."""
    return {"checks": [_r(r) for r in _astronomy.run({"ASTRO_VERIFY": spec or {}})]}


def verify_calendar_time(spec):
    """Leap-year rule, ISO 8601 validity, day-of-week computation, duration addition."""
    return {"checks": [_r(r) for r in _calendar_time.run({"CAL_VERIFY": spec or {}})]}


def verify_combinatorics(spec):
    """Permutations, combinations, derangements, multinomial coefficients."""
    return {"checks": [_r(r) for r in _combinatorics.run({"COMB_VERIFY": spec or {}})]}


def verify_cryptography(spec):
    """Hash match, hash strength, key strength.
    Hash match: {"message": "hello", "claimed_hash": "2cf24dba...", "algorithm": "sha256"}
    Hash strength: {"algorithm": "md5", "claimed_strong": false}
    Key strength: {"key_bits": 256, "algorithm": "aes", "claimed_strong": true}"""
    return {"checks": [_r(r) for r in _cryptography.run({"CRYPTO_VERIFY": spec or {}})]}


def verify_document_validation(spec):
    """ISBN-13 check-digit validation and Luhn algorithm for credit card numbers.
    ISBN-13: {"isbn13": "9780306406157", "claimed_valid": true}
    Luhn:    {"luhn": "4532015112830366", "claimed_valid": true}"""
    return {"checks": [_r(r) for r in _document_validation.run({"DOC_VERIFY": spec or {}})]}


def verify_electrical(spec):
    """Ohm's law, power equations, Kirchhoff voltage loop, RC time constant."""
    return {"checks": [_r(r) for r in _electrical.run({"ELEC_VERIFY": spec or {}})]}


def verify_exercise_science(spec):
    """Energy expenditure, heart rate formulas, MET lookup.
    Energy: {"claimed_met": 8.0, "weight_kg": 70, "duration_hours": 1.0, "claimed_kcal": 560}
    Max HR (Tanaka): {"age_years": 30, "claimed_max_hr": 187}
    HR zone (Karvonen): {"age_years": 30, "resting_hr": 60, "intensity_low": 0.7, "intensity_high": 0.8,
                         "claimed_zone_low_bpm": 149, "claimed_zone_high_bpm": 162}"""
    return {"checks": [_r(r) for r in _exercise_science.run({"EX_VERIFY": spec or {}})]}


def verify_finance(spec):
    """Accounting identity (A=L+E), compound interest, NPV, present value."""
    return {"checks": [_r(r) for r in _finance.run({"FIN_VERIFY": spec or {}})]}


def verify_formal_logic(spec):
    """Satisfiability, tautology, contradiction, entailment, logical equivalence (propositional)."""
    return {"checks": [_r(r) for r in _formal_logic.run({"LOGIC_VERIFY": spec or {}})]}


def verify_genetics(spec):
    """DNA/RNA complementarity, reverse complement, GC content, codon translation, ORF bounds."""
    return {"checks": [_r(r) for r in _genetics.run({"GENETICS_VERIFY": spec or {}})]}


def verify_geography(spec):
    """Lat/lon validity, Haversine distance, initial bearing, UTM zone assignment."""
    return {"checks": [_r(r) for r in _geography.run({"GEO_LOC_VERIFY": spec or {}})]}


def verify_geology(spec):
    """Radiometric decay dating, Mohs hardness scratch test, Richter amplitude ratio."""
    return {"checks": [_r(r) for r in _geology.run({"GEO_VERIFY": spec or {}})]}


def verify_geometry(spec):
    """Areas, volumes, perimeters, Pythagorean theorem, circle/sphere relationships."""
    return {"checks": [_r(r) for r in _geometry.run({"GEOM_VERIFY": spec or {}})]}


def verify_hydrology(spec):
    """Manning's equation, Darcy's law, unit hydrograph, flow-rate/velocity/area."""
    return {"checks": [_r(r) for r in _hydrology.run({"HYD_VERIFY": spec or {}})]}


def verify_information_theory(spec):
    """Shannon entropy, channel capacity, mutual information, Huffman code length bounds."""
    return {"checks": [_r(r) for r in _information_theory.run({"INFO_VERIFY": spec or {}})]}


def verify_linguistics(spec):
    """Strong's resolution, occurrence count, transliteration, gloss consistency, cognate pairs."""
    return {"checks": [_r(r) for r in _linguistics.run({"LING_VERIFY": spec or {}})]}


def verify_manufacturing(spec):
    """Tolerance stack-up, GD&T fits, surface roughness, process capability (Cp/Cpk)."""
    return {"checks": [_r(r) for r in _manufacturing.run({"MFG_VERIFY": spec or {}})]}


def verify_meteorology(spec):
    """Dew point, relative humidity, pressure altitude, wind chill, heat index."""
    return {"checks": [_r(r) for r in _meteorology.run({"MET_VERIFY": spec or {}})]}


def verify_music_theory(spec):
    """Interval semitone counts, chord quality (major/minor/dom7), frequency ratios."""
    return {"checks": [_r(r) for r in _music_theory.run({"MUS_VERIFY": spec or {}})]}


def verify_networking(spec):
    """Subnet masks, CIDR notation, IP address validity, broadcast/network address."""
    return {"checks": [_r(r) for r in _networking.run({"NET_VERIFY": spec or {}})]}


def verify_number_theory(spec):
    """Primality, GCD, LCM, modular arithmetic, Fibonacci membership, divisibility."""
    return {"checks": [_r(r) for r in _number_theory.run({"NUM_VERIFY": spec or {}})]}


def verify_nutrition(spec):
    """Macronutrient caloric values, BMR (Mifflin-St Jeor), TDEE, nutrient density."""
    return {"checks": [_r(r) for r in _nutrition.run({"NUT_VERIFY": spec or {}})]}


def verify_optics(spec):
    """Snell's law, thin-lens equation, diffraction grating, angular resolution."""
    return {"checks": [_r(r) for r in _optics.run({"OPT_VERIFY": spec or {}})]}


def verify_photography(spec):
    """Exposure triangle (aperture/shutter/ISO), EV calculation, depth-of-field."""
    return {"checks": [_r(r) for r in _photography.run({"PHOTO_VERIFY": spec or {}})]}


def verify_sports_analytics(spec):
    """Batting average, ERA, passer rating, Pythagorean win expectation, Elo rating."""
    return {"checks": [_r(r) for r in _sports_analytics.run({"SPORT_VERIFY": spec or {}})]}


def verify_witness(spec):
    """Gate-chain completeness, reasoning trace presence, anchor resolution, no-fabricated-answer check."""
    return {"checks": [_r(r) for r in _witness.run({"WIT_VERIFY": spec or {}})]}


def verify_quantum_computing(spec):
    """Qubit normalization, Grover iterations, Shor period, BB84 QKD security, von Neumann entropy, fidelity.
    Normalization: {"amplitudes": [0.6, 0.8], "claimed_normalized": true}
    Grover: {"n_items": 64, "claimed_grover_iterations": 6}
    Shor period: {"shor_a": 2, "shor_N": 15, "shor_r": 4, "claimed_period_valid": true}
    BB84: {"qber": 0.09, "claimed_secure": true}
    vN entropy: {"density_eigenvalues": [0.5, 0.5], "claimed_entropy_bits": 1.0}"""
    return {"checks": [_r(r) for r in _quantum_computing.run({"QCOMP_VERIFY": spec or {}})]}


def verify_medicine(spec):
    """BMI, drug dosage, blood pressure (AHA 2017), A1C→eAG, eGFR Cockcroft-Gault, IBW Devine, MAP.
    BMI: {"weight_kg": 70, "height_m": 1.75, "claimed_bmi": 22.86, "claimed_bmi_class": "normal"}
    Dosage: {"dose_mg_per_kg": 5, "weight_kg": 70, "claimed_dose_mg": 350}
    BP: {"systolic": 125, "diastolic": 82, "claimed_bp_class": "hypertension_stage_1"}
    A1C: {"a1c_pct": 7.0, "claimed_eag_mg_dl": 154.1}
    eGFR: {"age_years": 45, "weight_kg": 70, "serum_creatinine": 1.1, "sex": "male", "claimed_egfr": 75.0}
    IBW: {"height_in": 70, "sex_ibw": "male", "claimed_ibw_kg": 75.5}
    MAP: {"systolic": 120, "diastolic": 80, "claimed_map_mmhg": 93.3}"""
    return {"checks": [_r(r) for r in _medicine.run({"MED_VERIFY": spec or {}})]}


def verify_cybersecurity(spec):
    """Password entropy, TLS version status, CVSS severity, subnet host count, port classification.
    Entropy: {"password_length": 16, "charset_size": 94, "claimed_entropy_bits": 104.9}
    TLS: {"tls_version": "1.3", "claimed_tls_status": "recommended"}
    CVSS: {"cvss_base_score": 9.1, "claimed_cvss_severity": "critical"}
    Subnet: {"cidr_prefix": 24, "claimed_host_count": 254}
    Port: {"port_number": 443, "claimed_port_class": "well_known"}"""
    return {"checks": [_r(r) for r in _cybersecurity.run({"CYBER_VERIFY": spec or {}})]}


def verify_economics(spec):
    """Simple/compound interest, PV/FV, Rule of 72, inflation adjustment, GDP per capita, price elasticity.
    Simple interest: {"principal": 1000, "rate": 0.05, "time_years": 3, "claimed_simple_interest": 150}
    Compound: {"principal": 1000, "rate": 0.05, "time_years": 3, "compounding_periods": 12, "claimed_compound_amount": 1161.62}
    Rule of 72: {"rate_percent": 7, "claimed_doubling_years": 10.3}
    Inflation: {"nominal_value": 1000, "inflation_rate": 0.03, "years": 10, "claimed_real_value": 744.09}"""
    return {"checks": [_r(r) for r in _economics.run({"ECON_VERIFY": spec or {}})]}


def verify_labor(spec):
    """Gross pay, FLSA overtime, annual-to-hourly, take-home pay, minimum wage compliance.
    Gross: {"hourly_rate": 18.5, "hours_worked": 45, "claimed_gross_pay": 832.5}
    Overtime: {"hourly_rate": 18.5, "regular_hours": 40, "overtime_hours": 5, "claimed_overtime_pay": 878.75}
    Take-home: {"gross_pay": 1000, "total_tax_rate": 0.28, "claimed_take_home": 720}
    Annual/hourly: {"annual_salary": 52000, "claimed_hourly_equivalent": 25.0}"""
    return {"checks": [_r(r) for r in _labor.run({"LABOR_VERIFY": spec or {}})]}


def verify_real_estate(spec):
    """Monthly mortgage payment, cap rate, GRM, LTV, DSCR, rental yield.
    Mortgage: {"loan_principal": 300000, "annual_rate": 0.065, "loan_term_months": 360, "claimed_monthly_payment": 1896.20}
    Cap rate: {"net_operating_income": 24000, "property_value": 400000, "claimed_cap_rate": 0.06}
    LTV: {"loan_amount": 240000, "appraised_value": 300000, "claimed_ltv": 0.80}
    DSCR: {"net_operating_income": 24000, "annual_debt_service": 22755, "claimed_dscr": 1.055}"""
    return {"checks": [_r(r) for r in _real_estate.run({"RE_VERIFY": spec or {}})]}


def verify_construction(spec):
    """Concrete volume, area (rect/circle), rebar weight, wall area, paint cans, floor tiles, beam load.
    Concrete: {"length_m": 10, "width_m": 5, "depth_m": 0.15, "claimed_concrete_m3": 7.5}
    Tiles: {"tile_area_m2": 50, "tile_size_m2": 0.25, "waste_factor": 0.10, "claimed_tile_count": 220}
    Beam: {"total_load_kn": 120, "span_m": 6, "claimed_load_intensity_kn_per_m": 20.0}"""
    return {"checks": [_r(r) for r in _construction.run({"CONSTR_VERIFY": spec or {}})]}


def verify_soil_science(spec):
    """Soil pH suitability, NPK fertilizer requirements, irrigation ETc, lime requirement, texture classification.
    pH: {"crop": "maize", "soil_ph": 6.2, "claimed_ph_suitable": true}
    NPK: {"crop_npk": "wheat", "area_hectares": 2.0, "claimed_n_kg": 240, "claimed_p_kg": 120, "claimed_k_kg": 120}
    Irrigation: {"reference_et0_mm_per_day": 5.0, "crop_coefficient": 1.15, "claimed_etc_mm_per_day": 5.75}
    Texture: {"sand_pct": 40, "silt_pct": 40, "clay_pct": 20, "claimed_texture_class": "loam"}"""
    return {"checks": [_r(r) for r in _soil_science.run({"SOIL_VERIFY": spec or {}})]}


# ---------------------------------------------------------------------
# Domain-attestation tools
# ---------------------------------------------------------------------

def _gate_results_to_payload(grs):
    items = [
        {"gate": gr.gate, "status": gr.status,
         "reasons": list(gr.reasons or []),
         "details": dict(gr.details or {})}
        for gr in (grs or [])
    ]
    overall = "PASS"
    for it in items:
        if it["status"] == "REJECT":
            overall = "REJECT"
            break
        if it["status"] == "QUARANTINE" and overall == "PASS":
            overall = "QUARANTINE"
    return {"overall": overall, "results": items}


def attest_red(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_red(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


def attest_floor(packet):
    from ..domains.base import load_domain_validator
    domain = (packet.get("domain") or "").lower()
    v = load_domain_validator(domain)
    if v is None:
        return {"status": "ERROR", "detail": f"unknown domain: {domain!r}"}
    try:
        grs = v.validate_floor(packet)
    except Exception as e:
        return {"status": "ERROR", "detail": f"{type(e).__name__}: {e}"}
    return _gate_results_to_payload(grs)


# ---------------------------------------------------------------------
# Layer 0 / Scripture tools
# ---------------------------------------------------------------------

def resolve_scripture_ref(ref):
    """Look up a scripture reference in the WEB and return its text.
    Accepts forms like "Jn3:16", "John 3:16", "1Co13:4". Returns
    `{ref, web_text, status, detail}`. Status `source_missing` means
    the Layer 0 data has not been provisioned yet — see the detail."""
    return scripture.resolve_ref(ref)


def word_study(strongs_num):
    """Strong's-keyed word study: definition, derivation, every verse
    where the word appears. Accepts "G26", "H2617", etc. Returns
    `{strongs, word, transliteration, definition, derivation, verses,
    occurrence_count}` or a `source_missing` status if Layer 0 has not
    been provisioned."""
    return scripture.word_study(strongs_num)


def verify_scripture_anchors(anchors):
    """Confirm each ref in `anchors` resolves to a real WEB verse.
    Used to catch fabricated scripture citations — the most common
    LLM-failure mode in this domain. Returns the standard verifier
    result shape (CONFIRMED / MISMATCH / SKIPPED)."""
    return _r(scripture.verify_scripture_anchors(list(anchors or [])))


def triangulate_claim(ref, claim, strongs_keys=None):
    """Triangulation: check whether an interpretation `claim` about a
    scripture verse `ref` is consistent with the original-language
    Strong's definitions.

    Without `strongs_keys`, returns NEEDS_MANUAL_VERIFICATION with the
    WEB text and instructions for completing the check. With Strong's
    numbers supplied (e.g. ['G142'] for airo), returns the per-word
    semantic range so a reviewer (or later automated tagging) can
    compare the claim to attested meaning."""
    return scripture.triangulate_claim(ref, claim, strongs_keys=strongs_keys)


def get_example_packet(name):
    examples_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "examples")
    candidates = [f"sample_packet_{name}.json", f"sample_packet_{name}_verify.json",
                  f"sample_packet_jda_{name}.json", f"{name}.json"]
    for c in candidates:
        path = os.path.join(examples_dir, c)
        if os.path.exists(path):
            with open(path) as f:
                return {"name": c, "packet": json.load(f)}
    available = sorted([f for f in os.listdir(examples_dir) if f.endswith(".json")])
    return {"error": f"no example named {name!r}", "available": available}


# ---------------------------------------------------------------------
# List-style API
# ---------------------------------------------------------------------

TOOLS: List[Dict[str, Any]] = [
    {"name": "validate_packet",
     "description": "Run a packet through the full Four-Gates engine.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"},
                                    "now_epoch": {"type": "integer"}},
                     "required": ["packet"]},
     "fn": lambda a: validate_packet(a["packet"], a.get("now_epoch"))},
    {"name": "verify_chemistry",
     "description": "Verify equation balance / suggest balancing coefficients. Optional temperature_K positivity.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "temperature_K": {"type": "number"}},
                     "required": ["equation"]},
     "fn": lambda a: verify_chemistry(a["equation"], a.get("temperature_K"))},
    {"name": "verify_physics_dimensional",
     "description": "Verify both sides of an equation reduce to identical SI units.",
     "inputSchema": {"type": "object",
                     "properties": {"equation": {"type": "string"},
                                    "symbols": {"type": "object"}},
                     "required": ["equation", "symbols"]},
     "fn": lambda a: verify_physics_dimensional(a["equation"], a["symbols"])},
    {"name": "verify_physics_conservation",
     "description": "Verify before/after match within tolerance. Optional 'law' (energy|momentum|charge|mass) enforces named-law key/unit profile.",
     "inputSchema": {"type": "object",
                     "properties": {"before": {"type": "object"},
                                    "after": {"type": "object"},
                                    "tolerance_relative": {"type": "number"},
                                    "tolerance_absolute": {"type": "number"},
                                    "law": {"type": "string"}},
                     "required": ["before", "after"]},
     "fn": lambda a: verify_physics_conservation(
        a["before"], a["after"],
        a.get("tolerance_relative", 1e-6), a.get("tolerance_absolute", 0.0),
        law=a.get("law"))},
    {"name": "verify_mathematics",
     "description": "Sympy verification. mode=equality|derivative|integral|limit|solve|matrix|inequality|series|ode.",
     "inputSchema": {"type": "object",
                     "properties": {"mode": {"type": "string"}, "params": {"type": "object"}},
                     "required": ["mode", "params"]},
     "fn": lambda a: verify_mathematics(a["mode"], a["params"])},
    {"name": "verify_statistics_pvalue",
     "description": "Recompute p from inputs and compare to claimed_p. Tests: two_sample_t, one_sample_t, paired_t, z, chi2, f, one_proportion_z, two_proportion_z, fisher_exact, mannwhitney, wilcoxon_signed_rank, regression_coefficient_t.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_statistics_pvalue(a["spec"])},
    {"name": "verify_statistics_multiple_comparisons",
     "description": "Bonferroni or BH/FDR adjustment with rejection-set verification.",
     "inputSchema": {"type": "object",
                     "properties": {"raw_p_values": {"type": "array"},
                                    "method": {"type": "string"},
                                    "alpha": {"type": "number"},
                                    "claimed_rejected_indices": {"type": "array"}},
                     "required": ["raw_p_values", "method"]},
     "fn": lambda a: verify_statistics_multiple_comparisons(
        a["raw_p_values"], a["method"], a.get("alpha", 0.05),
        a.get("claimed_rejected_indices"))},
    {"name": "verify_statistics_confidence_interval",
     "description": "Verify CI well-formed and contains estimate. With 'spec' raw inputs, recompute bounds.",
     "inputSchema": {"type": "object",
                     "properties": {"estimate": {"type": "number"},
                                    "ci_low": {"type": "number"},
                                    "ci_high": {"type": "number"},
                                    "spec": {"type": "object"}},
                     "required": ["estimate", "ci_low", "ci_high"]},
     "fn": lambda a: verify_statistics_confidence_interval(
        a["estimate"], a["ci_low"], a["ci_high"], spec=a.get("spec"))},
    {"name": "verify_computer_science",
     "description": "Verify Python: termination, correctness, runtime O(.), space O(.), determinism.",
     "inputSchema": {"type": "object",
                     "properties": {"code": {"type": "string"},
                                    "function_name": {"type": "string"},
                                    "test_cases": {"type": "array"},
                                    "input_generator": {"type": "string"},
                                    "claimed_class": {"type": "string"},
                                    "claimed_space_class": {"type": "string"},
                                    "sizes": {"type": "array"},
                                    "tolerance": {"type": "number"},
                                    "determinism_trials": {"type": "integer"}},
                     "required": ["code"]},
     "fn": lambda a: verify_computer_science(
        a["code"], a.get("function_name"), a.get("test_cases"),
        a.get("input_generator"), a.get("claimed_class"),
        a.get("sizes"), a.get("tolerance", 0.40),
        determinism_trials=a.get("determinism_trials"),
        claimed_space_class=a.get("claimed_space_class"))},
    {"name": "verify_biology",
     "description": (
         "Biology checks: replicates, assays, dose-response, power, Hardy-Weinberg, "
         "primer Tm/GC, molarity, Mendelian. "
         "Pass bio_control dict to verify nested health control system claims: "
         "failure_mode (setpoint_drift|loop_saturation|compensation_collapse|"
         "cross_layer_override|sensor_failure), failure_layer (L1-L6), "
         "intervention_layers, and required safety fields."
     ),
     "inputSchema": {"type": "object",
                     "properties": {"n_replicates": {"type": "integer"},
                                    "min_replicates": {"type": "integer"},
                                    "assay_classes": {"type": "array"},
                                    "min_assay_classes": {"type": "integer"},
                                    "dose_response": {"type": "object"},
                                    "power_analysis": {"type": "object"},
                                    "bio_control": {"type": "object"},
                                    "hardy_weinberg": {"type": "object"},
                                    "primer": {"type": "object"},
                                    "molarity": {"type": "object"},
                                    "mendelian": {"type": "object"}}},
     "fn": lambda a: verify_biology(
        a.get("n_replicates"), a.get("min_replicates", 3),
        a.get("assay_classes"), a.get("min_assay_classes", 2),
        a.get("dose_response"), a.get("power_analysis"),
        bio_control=a.get("bio_control"),
        hardy_weinberg=a.get("hardy_weinberg"), primer=a.get("primer"),
        molarity=a.get("molarity"), mendelian=a.get("mendelian"))},
    {"name": "verify_governance_decision_packet",
     "description": "Decision packet structural check. Optional 'domain' (governance|business|household|education|church) activates per-domain profile.",
     "inputSchema": {"type": "object",
                     "properties": {"decision_packet": {"type": "object"},
                                    "witness_count": {"type": "integer"},
                                    "domain": {"type": "string"}},
                     "required": ["decision_packet"]},
     "fn": lambda a: verify_governance_decision_packet(
        a["decision_packet"], a.get("witness_count"), domain=a.get("domain"))},
    {"name": "attest_red",
     "description": "Run only the RED-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_red(a["packet"])},
    {"name": "attest_floor",
     "description": "Run only the FLOOR-gate attestation validator for the packet's domain.",
     "inputSchema": {"type": "object",
                     "properties": {"packet": {"type": "object"}},
                     "required": ["packet"]},
     "fn": lambda a: attest_floor(a["packet"])},
    {"name": "resolve_scripture_ref",
     "description": (
         "Look up a scripture reference in the World English Bible and return "
         "its text. Accepts forms like 'Jn3:16', 'John 3:16', '1Co13:4'. "
         "Returns {ref, web_text, status, detail}. Status 'source_missing' "
         "means Layer 0 data has not been provisioned — run "
         "lw/00_source/fetch_sources.py once."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"}},
                     "required": ["ref"]},
     "fn": lambda a: resolve_scripture_ref(a["ref"])},
    {"name": "word_study",
     "description": (
         "Strong's-keyed word study. Pass a Strong's number like 'G26' "
         "(agape) or 'H2617' (chesed). Returns word, transliteration, "
         "definition, derivation, every verse where the word appears, "
         "and occurrence count."),
     "inputSchema": {"type": "object",
                     "properties": {"strongs_num": {"type": "string"}},
                     "required": ["strongs_num"]},
     "fn": lambda a: word_study(a["strongs_num"])},
    {"name": "verify_scripture_anchors",
     "description": (
         "Confirm each ref in 'anchors' resolves to a real WEB verse. Use "
         "this before citing scripture in a load-bearing claim — fabricated "
         "references are the most common LLM failure mode in this domain. "
         "Returns CONFIRMED / MISMATCH / SKIPPED."),
     "inputSchema": {"type": "object",
                     "properties": {"anchors": {"type": "array",
                                                "items": {"type": "string"}}},
                     "required": ["anchors"]},
     "fn": lambda a: verify_scripture_anchors(a["anchors"])},
    {"name": "triangulate_claim",
     "description": (
         "Triangulation: check whether an interpretation 'claim' about a "
         "verse 'ref' survives at all three layers (WEB text, Strong's "
         "original-language meaning, the claim itself). Without "
         "strongs_keys returns NEEDS_MANUAL_VERIFICATION + the WEB text "
         "and instructions. With Strong's numbers supplied, returns the "
         "per-word semantic range so the claim can be checked against "
         "attested meaning."),
     "inputSchema": {"type": "object",
                     "properties": {"ref": {"type": "string"},
                                    "claim": {"type": "string"},
                                    "strongs_keys": {"type": "array",
                                                     "items": {"type": "string"}}},
                     "required": ["ref", "claim"]},
     "fn": lambda a: triangulate_claim(a["ref"], a["claim"], a.get("strongs_keys"))},
    {"name": "get_example_packet",
     "description": "Return a canonical example packet by name.",
     "inputSchema": {"type": "object",
                     "properties": {"name": {"type": "string"}},
                     "required": ["name"]},
     "fn": lambda a: get_example_packet(a["name"])},
    # ── Extended domain verifiers ────────────────────────────────────
    {"name": "verify_energy",
     "description": "Off-grid sizing, wire voltage drop, battery/solar sizing, peak-load-vs-inverter, runtime, kWh↔Wh, efficiency, power balance. Pass spec as ENERGY_VERIFY contents.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_energy(a["spec"])},
    {"name": "verify_acoustics",
     "description": "Wave speed/frequency/wavelength (v=fλ), decibel ratios, Doppler shift, harmonic frequencies.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_acoustics(a["spec"])},
    {"name": "verify_agriculture",
     "description": "USDA hardiness zone lookup, soil pH range for crops, crop rotation compatibility, livestock stocking density.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_agriculture(a["spec"])},
    {"name": "verify_astronomy",
     "description": "Kepler's third law (T²∝a³), gravitational force, stellar parallax distance, distance modulus (m-M).",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_astronomy(a["spec"])},
    {"name": "verify_calendar_time",
     "description": "Gregorian leap-year rule, ISO 8601 datetime validity, day-of-week (Zeller/Tomohiko), duration addition.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_calendar_time(a["spec"])},
    {"name": "verify_combinatorics",
     "description": "Permutations P(n,k), combinations C(n,k), derangements D(n), multinomial coefficients.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_combinatorics(a["spec"])},
    {"name": "verify_cryptography",
     "description": "Hash match, hash strength, key strength. "
                    "Hash match: spec={\"message\":\"hello\",\"claimed_hash\":\"2cf24...\",\"algorithm\":\"sha256\"}. "
                    "Hash strength: spec={\"algorithm\":\"md5\",\"claimed_strong\":false}. "
                    "Key strength: spec={\"key_bits\":256,\"algorithm\":\"aes\",\"claimed_strong\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_cryptography(a["spec"])},
    {"name": "verify_document_validation",
     "description": "ISBN-13 check-digit and Luhn algorithm for credit card numbers. "
                    "ISBN-13: spec={\"isbn13\":\"9780306406157\",\"claimed_valid\":true}. "
                    "Luhn: spec={\"luhn\":\"4532015112830366\",\"claimed_valid\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_document_validation(a["spec"])},
    {"name": "verify_electrical",
     "description": "Ohm's law (V=IR), power (P=VI/I²R/V²/R), Kirchhoff voltage loop sum, RC time constant (τ=RC).",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_electrical(a["spec"])},
    {"name": "verify_exercise_science",
     "description": "Energy expenditure (MET×kg×hours), max heart rate Tanaka (208-0.7×age), Karvonen HR zone, MET lookup. "
                    "Energy: spec={\"claimed_met\":8,\"weight_kg\":70,\"duration_hours\":1,\"claimed_kcal\":560}. "
                    "Max HR: spec={\"age_years\":30,\"claimed_max_hr\":187}. "
                    "HR zone: spec={\"age_years\":30,\"resting_hr\":60,\"intensity_low\":0.7,\"intensity_high\":0.8,"
                    "\"claimed_zone_low_bpm\":149,\"claimed_zone_high_bpm\":162}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_exercise_science(a["spec"])},
    {"name": "verify_finance",
     "description": "Accounting identity (A=L+E), compound interest A=P(1+r/n)^(nt), NPV, present value PV=FV/(1+r)^t.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_finance(a["spec"])},
    {"name": "verify_formal_logic",
     "description": "Propositional logic: satisfiability, tautology, contradiction, entailment (premises→conclusion), logical equivalence.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_formal_logic(a["spec"])},
    {"name": "verify_genetics",
     "description": "DNA/RNA base complementarity, reverse complement, GC content, codon→amino-acid translation, ORF start/stop bounds.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_genetics(a["spec"])},
    {"name": "verify_geography",
     "description": "Lat/lon range validity, Haversine great-circle distance, initial bearing, UTM zone assignment.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geography(a["spec"])},
    {"name": "verify_geology",
     "description": "Radiometric decay dating (N=N₀·e^(−λt)), Mohs hardness scratch test, Richter scale amplitude ratio.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geology(a["spec"])},
    {"name": "verify_geometry",
     "description": "Areas and volumes of standard shapes, Pythagorean theorem, circle/sphere relationships, triangle angle sum.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_geometry(a["spec"])},
    {"name": "verify_hydrology",
     "description": "Manning's equation (open channel flow), Darcy's law (porous media), continuity equation Q=Av.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_hydrology(a["spec"])},
    {"name": "verify_information_theory",
     "description": "Shannon entropy H(X), channel capacity C=B·log₂(1+SNR), mutual information, Huffman minimum code length.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_information_theory(a["spec"])},
    {"name": "verify_linguistics",
     "description": "Strong's number resolution (G/H range), occurrence count, transliteration normalization, gloss consistency, cognate pair detection.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_linguistics(a["spec"])},
    {"name": "verify_manufacturing",
     "description": "Tolerance stack-up (worst-case/RSS), GD&T fit class (clearance/interference), surface roughness Ra, process capability Cp/Cpk.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_manufacturing(a["spec"])},
    {"name": "verify_meteorology",
     "description": "Dew point (Magnus formula), relative humidity, pressure altitude, wind chill (NWS), heat index.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_meteorology(a["spec"])},
    {"name": "verify_music_theory",
     "description": "Interval semitone counts, chord quality (major/minor/dom7/dim), frequency ratio for equal temperament.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_music_theory(a["spec"])},
    {"name": "verify_networking",
     "description": "Subnet mask validity, CIDR notation, IP address range, network/broadcast address computation.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_networking(a["spec"])},
    {"name": "verify_number_theory",
     "description": "Primality testing, GCD/LCM, modular arithmetic, Fibonacci membership, perfect/abundant/deficient classification.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_number_theory(a["spec"])},
    {"name": "verify_nutrition",
     "description": "Macro caloric values (4/4/9 kcal/g), BMR (Mifflin-St Jeor), TDEE with activity factor, nutrient density.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_nutrition(a["spec"])},
    {"name": "verify_optics",
     "description": "Snell's law (n₁sinθ₁=n₂sinθ₂), thin-lens equation (1/f=1/do+1/di), diffraction grating, Rayleigh criterion.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_optics(a["spec"])},
    {"name": "verify_photography",
     "description": "Exposure value (EV), equivalent exposures (aperture/shutter/ISO triangle), depth-of-field hyperfocal distance.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_photography(a["spec"])},
    {"name": "verify_sports_analytics",
     "description": "Batting average, ERA, NFL passer rating, Pythagorean win expectation, Elo rating change.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_sports_analytics(a["spec"])},
    {"name": "verify_witness",
     "description": "Gate-chain completeness, reasoning trace presence, anchor resolution, no-fabricated-answer check. Verifies a witness/attestation record is structurally sound.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_witness(a["spec"])},
    {"name": "verify_quantum_computing",
     "description": "Qubit normalization (Σ|aᵢ|²=1), Grover optimal iterations (T=floor(π√N/4)), "
                    "Shor period (a^r≡1 mod N), BB84 QKD security (QBER<11%), von Neumann entropy, fidelity. "
                    "Normalization: spec={\"amplitudes\":[0.6,0.8],\"claimed_normalized\":true}. "
                    "Grover: spec={\"n_items\":64,\"claimed_grover_iterations\":6}. "
                    "BB84: spec={\"qber\":0.09,\"claimed_secure\":true}.",
     "inputSchema": {"type": "object", "properties": {"spec": {"type": "object"}}, "required": ["spec"]},
     "fn": lambda a: verify_quantum_computing(a["spec"])},
]


TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def list_tools():
    return [{k: v for k, v in t.items() if k != "fn"} for t in TOOLS]


def call_tool(name, arguments):
    tool = TOOL_BY_NAME.get(name)
    if tool is None:
        return {"error": f"unknown tool {name!r}", "available": list(TOOL_BY_NAME.keys())}
    try:
        return tool["fn"](arguments or {})
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


ALL_TOOLS: Dict[str, Any] = {
    "validate_packet": validate_packet,
    "seal_packet": seal_packet,
    "walkthrough_packet": walkthrough_packet,
    "verify_chemistry": verify_chemistry,
    "verify_physics_dimensional": verify_physics_dimensional,
    "verify_physics_conservation": verify_physics_conservation,
    "verify_mathematics": verify_mathematics,
    "verify_statistics_pvalue": verify_statistics_pvalue,
    "verify_statistics_multiple_comparisons": verify_statistics_multiple_comparisons,
    "verify_statistics_confidence_interval": verify_statistics_confidence_interval,
    "verify_computer_science": verify_computer_science,
    "verify_biology": verify_biology,
    "verify_governance_decision_packet": verify_governance_decision_packet,
    "verify_energy": verify_energy,
    "verify_acoustics": verify_acoustics,
    "verify_agriculture": verify_agriculture,
    "verify_astronomy": verify_astronomy,
    "verify_calendar_time": verify_calendar_time,
    "verify_combinatorics": verify_combinatorics,
    "verify_cryptography": verify_cryptography,
    "verify_document_validation": verify_document_validation,
    "verify_electrical": verify_electrical,
    "verify_exercise_science": verify_exercise_science,
    "verify_finance": verify_finance,
    "verify_formal_logic": verify_formal_logic,
    "verify_genetics": verify_genetics,
    "verify_geography": verify_geography,
    "verify_geology": verify_geology,
    "verify_geometry": verify_geometry,
    "verify_hydrology": verify_hydrology,
    "verify_information_theory": verify_information_theory,
    "verify_linguistics": verify_linguistics,
    "verify_manufacturing": verify_manufacturing,
    "verify_meteorology": verify_meteorology,
    "verify_music_theory": verify_music_theory,
    "verify_networking": verify_networking,
    "verify_number_theory": verify_number_theory,
    "verify_nutrition": verify_nutrition,
    "verify_optics": verify_optics,
    "verify_photography": verify_photography,
    "verify_sports_analytics": verify_sports_analytics,
    "verify_witness": verify_witness,
    "verify_quantum_computing": verify_quantum_computing,
    "verify_medicine": verify_medicine,
    "verify_cybersecurity": verify_cybersecurity,
    "verify_economics": verify_economics,
    "verify_labor": verify_labor,
    "verify_real_estate": verify_real_estate,
    "verify_construction": verify_construction,
    "verify_soil_science": verify_soil_science,
    "attest_red": attest_red,
    "attest_floor": attest_floor,
    "resolve_scripture_ref": resolve_scripture_ref,
    "word_study": word_study,
    "verify_scripture_anchors": verify_scripture_anchors,
    "triangulate_claim": triangulate_claim,
    "get_example_packet": get_example_packet,
}
