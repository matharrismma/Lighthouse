"""
Concordance Agent Manifest
--------------------------
OpenAI-compatible tool definitions and context block for any AI agent —
Grok, GPT, Gemini, Claude, or any future agent that speaks function-calling.

The manifest is the public face of the engine to the agent ecosystem.
Every description is load-bearing: it is what agents will read to understand
what they are working with and what CONFIRMED means.

Key concepts every agent should hold:
  - CONFIRMED   : the claim aligns with the structure of the created order in
                  that domain, verified by independent computation, not inference.
  - DISCORDANT  : the claim contradicts the created order. The detail field says
                  what the actual value is.
  - NOT_APPLICABLE : the spec did not contain the fields needed to run this check.
  - Axes        : every domain touches one or more of six axes of the grid —
                  conservation_balance, information_encoding, formal_reasoning,
                  physical_substance, authority_trust, time_sequence.
  - Precedent   : the engine keeps a ledger of sealed, verified records. A new
                  claim is overlaid on the closest prior case so reasoning can
                  be traced, not just answered.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── engine import ──────────────────────────────────────────────────────────────
_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

try:
    from concordance_engine.mcp_server.tools import ALL_TOOLS
    _TOOLS_AVAILABLE = True
except ImportError:
    ALL_TOOLS = {}
    _TOOLS_AVAILABLE = False

_BENCH_DIR = _REPO / "eval" / "benchmark"


# ── axis tags (for agent orientation) ─────────────────────────────────────────

_AXES = {
    "conservation_balance":  "The created order conserves. Energy, mass, charge, and momentum are never created from nothing or destroyed — only transformed. Every physical law is a statement of conservation.",
    "information_encoding":  "Meaning is encoded precisely. DNA, language, code, cryptographic keys, and musical notation are all information systems with exact rules for encoding and decoding.",
    "formal_reasoning":      "Logic and mathematics are the language of necessity. A proof either holds or it does not. An algorithm either terminates correctly or it does not. There is no middle ground.",
    "physical_substance":    "The material creation occupies space and time. Geographic coordinates, geological strata, and material properties are verifiable facts about physical reality.",
    "authority_trust":       "Legitimate claims require witnesses. Governance decisions, legal instruments, identity assertions, and sealed records derive authority from a verifiable chain of witnesses.",
    "time_sequence":         "Events have order. Causality, chronology, and sequence are not negotiable. What precedes what is a fact about the structure of time.",
}


# ── manifest entries ───────────────────────────────────────────────────────────
# Each entry is OpenAI function-calling format.
# "spec" is a flat dict — pass the fields the domain verifier expects directly.

def _tool(name: str, description: str, spec_description: str) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {
                    "spec": {
                        "type": "object",
                        "description": spec_description,
                    }
                },
                "required": ["spec"],
            },
        },
    }


_MANIFEST: List[Dict[str, Any]] = [

    # ── physics ─────────────────────────────────────────────────────────────
    _tool(
        "verify_physics_dimensional",
        (
            "Verify that both sides of a physical equation reduce to identical SI units. "
            "Dimensional consistency is the first gate of any physical claim: F = m·a is "
            "valid because both sides reduce to kg·m/s². A dimensionally inconsistent "
            "equation cannot describe reality regardless of the numbers. "
            "CONFIRMED means the equation is dimensionally consistent. "
            "Axis: conservation_balance, formal_reasoning."
        ),
        (
            "Pass the equation as a string and a symbol→SI-unit dict. "
            "KE check:    {\"equation\": \"KE = 0.5 * m * v**2\", \"symbols\": {\"KE\": \"joule\", \"m\": \"kilogram\", \"v\": \"meter/second\"}} "
            "Force check: {\"equation\": \"F = m * a\", \"symbols\": {\"F\": \"newton\", \"m\": \"kilogram\", \"a\": \"meter/second**2\"}}"
        ),
    ),
    _tool(
        "verify_physics_conservation",
        (
            "Verify that a physical quantity is conserved between a before and after state. "
            "The physical realm maintains exact conservation: energy, momentum, and charge "
            "are never created or destroyed, only transformed. Any before/after mismatch "
            "beyond tolerance is a physical impossibility. "
            "CONFIRMED means the quantity is conserved. DISCORDANT means it is not. "
            "Axis: conservation_balance."
        ),
        (
            "Pass before and after as dicts with matching quantity keys. "
            "Energy: {\"before\": {\"kinetic_energy_j\": 100.0}, \"after\": {\"kinetic_energy_j\": 100.0}} "
            "With law: {\"before\": {\"momentum_kgms\": 6.0}, \"after\": {\"momentum_kgms\": 6.0}, \"law\": \"momentum\"}"
        ),
    ),

    # ── chemistry ───────────────────────────────────────────────────────────
    _tool(
        "verify_chemistry",
        (
            "Verify chemical equation balance — that atoms are neither created nor destroyed "
            "in a reaction. Mass conservation is absolute in the chemical realm: every atom "
            "on the left must appear on the right. CONFIRMED means the equation is balanced. "
            "DISCORDANT means atoms are unaccounted for. "
            "Axis: conservation_balance."
        ),
        (
            "Balance check:    {\"equation\": \"2 H2 + O2 -> 2 H2O\"} "
            "With temperature: {\"equation\": \"N2 + 3 H2 -> 2 NH3\", \"temperature_K\": 500}"
        ),
    ),

    # ── mathematics ─────────────────────────────────────────────────────────
    _tool(
        "verify_mathematics",
        (
            "Verify mathematical claims using symbolic computation — derivatives, integrals, "
            "algebraic equalities, limits, solutions to equations, matrix properties, "
            "inequalities, series expansions, and ODEs. Mathematics is the language of "
            "necessity: a proof either holds or it does not. CONFIRMED means the claim is "
            "mathematically true. DISCORDANT means it is false. "
            "Axis: formal_reasoning."
        ),
        (
            "Derivative:  {\"mode\": \"derivative\", \"params\": {\"function\": \"x**3\", \"claimed_derivative\": \"3*x**2\"}} "
            "Integral:    {\"mode\": \"integral\",   \"params\": {\"integrand\": \"x**2\", \"claimed_antiderivative\": \"x**3/3\"}} "
            "Equality:    {\"mode\": \"equality\",   \"params\": {\"expr_a\": \"sin(x)**2+cos(x)**2\", \"expr_b\": \"1\"}} "
            "Solve:       {\"mode\": \"solve\",      \"params\": {\"equation\": \"x**2 - 4\", \"claimed_solutions\": \"[-2, 2]\"}}"
        ),
    ),

    # ── statistics ──────────────────────────────────────────────────────────
    _tool(
        "verify_statistics_pvalue",
        (
            "Recompute a p-value from raw inputs and compare to a claimed value. "
            "Statistical inference extracts signal from noise — but only if the computation "
            "is exact. CONFIRMED means the claimed p-value matches the independent recomputation. "
            "Supported tests: two_sample_t, one_sample_t, paired_t, z, chi2, f, "
            "one_proportion_z, two_proportion_z, fisher_exact, mannwhitney, wilcoxon_signed_rank, "
            "regression_coefficient_t. "
            "Axis: formal_reasoning, information_encoding."
        ),
        (
            "Two-sample t: {\"test\": \"two_sample_t\", \"mean1\": 5.0, \"mean2\": 4.0, "
            "\"sd1\": 1.0, \"sd2\": 1.0, \"n1\": 30, \"n2\": 30, \"claimed_p\": 0.000276}"
        ),
    ),

    # ── computer science ────────────────────────────────────────────────────
    _tool(
        "verify_computer_science",
        (
            "Verify claims about algorithm complexity, termination, and correctness. "
            "Algorithms are formal objects — their time complexity, space complexity, and "
            "termination behavior follow from their structure with mathematical certainty. "
            "CONFIRMED means the algorithmic claim is correct. "
            "Axis: formal_reasoning, information_encoding."
        ),
        (
            "Complexity:   {\"algorithm\": \"bubble_sort\", \"claimed_complexity\": \"O(n^2)\"} "
            "Termination:  {\"algorithm\": \"binary_search\", \"claimed_terminates\": true}"
        ),
    ),

    # ── biology ─────────────────────────────────────────────────────────────
    _tool(
        "verify_biology",
        (
            "Verify biological claims — Hardy-Weinberg equilibrium frequencies, "
            "experimental replicate standards, and population genetics. Living systems "
            "are governed by precise chemical and statistical laws. "
            "CONFIRMED means the biological claim holds under the relevant law. "
            "Axis: conservation_balance, time_sequence."
        ),
        (
            "Replicates:         {\"n_replicates\": 3, \"min_replicates\": 3} "
            "Hardy-Weinberg Aa:  {\"hardy_weinberg\": {\"p\": 0.6, \"q\": 0.4, \"claimed_Aa\": 0.48}}"
        ),
    ),

    # ── genetics ────────────────────────────────────────────────────────────
    _tool(
        "verify_genetics",
        (
            "Verify DNA/RNA claims — base complementarity, reverse complement, GC content, "
            "codon to amino acid translation. DNA is the most precisely encoded information "
            "system in the known creation: A pairs with T, G pairs with C, no exceptions. "
            "CONFIRMED means the genetic claim is exact. "
            "Axis: information_encoding, conservation_balance."
        ),
        (
            "Complement:   {\"sequence\": \"ATCG\",   \"claimed_complement\": \"TAGC\"} "
            "GC content:   {\"sequence\": \"GCGCATCG\", \"claimed_gc_fraction\": 0.5} "
            "Codon:        {\"codon\": \"ATG\",        \"claimed_amino_acid\": \"Met\"}"
        ),
    ),

    # ── formal logic ────────────────────────────────────────────────────────
    _tool(
        "verify_formal_logic",
        (
            "Verify logical validity, tautologies, contradictions, and inference rules — "
            "modus ponens, modus tollens, disjunctive syllogism, De Morgan's laws, "
            "transitivity. Logic is the structure of valid inference: a valid argument "
            "cannot have true premises and a false conclusion. "
            "CONFIRMED means the logical claim is valid. "
            "Axis: formal_reasoning."
        ),
        (
            "Tautology:      {\"claimed_tautology\": \"p OR NOT p\"} "
            "Modus ponens:   {\"premises\": [\"p -> q\", \"p\"], \"conclusion\": \"q\", \"claimed_valid\": true} "
            "Contradiction:  {\"claimed_contradiction\": \"p AND NOT p\"}"
        ),
    ),

    # ── information theory ──────────────────────────────────────────────────
    _tool(
        "verify_information_theory",
        (
            "Verify Shannon entropy, channel capacity, mutual information, and "
            "Kolmogorov complexity estimates. Information is a measurable quantity — "
            "the entropy of a source is determined exactly by its probability distribution. "
            "CONFIRMED means the claimed information-theoretic value is exact. "
            "Axis: information_encoding."
        ),
        (
            "Shannon entropy:  {\"probabilities\": [0.5, 0.5], \"claimed_entropy_bits\": 1.0} "
            "Channel capacity: {\"bandwidth_hz\": 3000, \"snr_linear\": 7, \"claimed_capacity_bps\": 9000}"
        ),
    ),

    # ── cryptography ────────────────────────────────────────────────────────
    _tool(
        "verify_cryptography",
        (
            "Verify cryptographic claims — SHA-256 hash values, RSA key strength, "
            "HMAC integrity, AES key adequacy, ECC curve security levels. Cryptography "
            "is the marriage of information encoding and authority trust: a hash either "
            "matches or it does not; a key is either strong enough or it is not. "
            "CONFIRMED means the cryptographic claim is exact. "
            "Axis: information_encoding, authority_trust."
        ),
        (
            "SHA-256:       {\"input_string\": \"hello\", \"claimed_sha256\": \"2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c\"} "
            "Key strength:  {\"cipher\": \"AES\", \"key_bits\": 256, \"claimed_key_strength\": \"strong\"} "
            "HMAC:          {\"key\": \"secret\", \"message\": \"data\", \"claimed_hmac\": \"...\"}"
        ),
    ),

    # ── document validation ─────────────────────────────────────────────────
    _tool(
        "verify_document_validation",
        (
            "Verify document integrity checksums — ISBN-13 check digits and Luhn algorithm "
            "(credit cards, IMEI). These checksums are authority-binding: a valid ISBN-13 "
            "means the publisher registered that exact number; a valid Luhn means the card "
            "number was correctly issued. CONFIRMED means the checksum holds. "
            "Axis: information_encoding, authority_trust."
        ),
        (
            "ISBN-13:  {\"isbn13\": \"9780306406157\", \"claimed_isbn13_valid\": true} "
            "Luhn:     {\"luhn_number\": \"4532015112830366\", \"claimed_luhn_valid\": true}"
        ),
    ),

    # ── governance ──────────────────────────────────────────────────────────
    _tool(
        "verify_governance_decision_packet",
        (
            "Verify decision packet structure — whether a governance record has the required "
            "witnesses, a non-empty rationale, valid gate verdicts, and proper timestamp. "
            "Authority requires witnesses. A decision without a witness chain is not a "
            "legitimate decision — it is an assertion. CONFIRMED means the governance "
            "record meets the structural requirements of legitimate authority. "
            "Axis: authority_trust."
        ),
        (
            "Pass the decision packet directly (not nested under 'spec'). "
            "Fields: decision_text, rationale, witnesses (list), timestamp (unix epoch). "
            "Example: {\"decision_packet\": {\"decision_text\": \"Approve budget\", "
            "\"rationale\": \"Reviewed by committee\", "
            "\"witnesses\": [{\"name\": \"Alice\", \"role\": \"Elder\"}], "
            "\"timestamp\": 1700000000}}"
        ),
    ),

    # ── witness ─────────────────────────────────────────────────────────────
    _tool(
        "verify_witness",
        (
            "Verify the structural completeness of a gate chain record — whether all five "
            "gates (RED, FLOOR, WAY, BROTHERS, GOD) are present and passed. The four-gate "
            "protocol is the engine's core witness structure: RED filters falsehood, FLOOR "
            "filters harm, WAY filters alignment with the path, BROTHERS filters communal "
            "sanity, GOD filters ultimate authority. A complete chain is a sealed witness. "
            "CONFIRMED means the chain is structurally complete and all gates passed. "
            "Axis: authority_trust, time_sequence."
        ),
        (
            "Full chain:    {\"claimed_gate_verdicts\": [{\"gate\": \"RED\", \"status\": \"PASS\"}, "
            "{\"gate\": \"FLOOR\", \"status\": \"PASS\"}, {\"gate\": \"WAY\", \"status\": \"PASS\"}, "
            "{\"gate\": \"BROTHERS\", \"status\": \"PASS\"}, {\"gate\": \"GOD\", \"status\": \"PASS\"}]} "
            "No fabrication: {\"claimed_no_fabrication\": true, \"agent_asserted_computation\": false}"
        ),
    ),

    # ── scripture ────────────────────────────────────────────────────────────
    _tool(
        "verify_scripture_anchors",
        (
            "Verify that Bible references actually exist in Scripture — resolves each "
            "cited reference against the public-domain World English Bible (WEB). "
            "This tool implements Proverbs 30:5-6: 'Every word of God proves true; "
            "do not add to his words.' An agent that cites a reference that does not "
            "exist in Scripture is fabricating authority it was never given. "
            "CONFIRMED means every cited reference resolved to a real verse. "
            "MISMATCH means at least one reference could not be found — the claim "
            "cannot be grounded in that verse because the verse does not say what is claimed, "
            "or does not exist. "
            "Axis: authority_trust, information_encoding. "
            "This is the primary theological grounding tool. Use it before citing any "
            "Scripture reference in a response."
        ),
        (
            "Pass a list of anchor objects under key 'anchors'. Each anchor needs 'ref' (e.g. 'John 3:16'), "
            "'layer' ('bible'), and 'derivation' (how the claim connects to the verse). "
            "Example: {\"anchors\": [{\"ref\": \"John 3:16\", \"layer\": \"bible\", "
            "\"derivation\": \"God's love for the world motivates this claim\"}]}"
        ),
    ),

    # ── networking ──────────────────────────────────────────────────────────
    _tool(
        "verify_networking",
        (
            "Verify network addressing claims — subnet membership, CIDR usable host count, "
            "port class (well-known/registered/dynamic). IP addressing is a formal system: "
            "an address either belongs to a subnet or it does not. "
            "CONFIRMED means the addressing claim is correct. "
            "Axis: information_encoding, authority_trust."
        ),
        (
            "Subnet member:  {\"ip\": \"192.168.1.100\", \"subnet\": \"192.168.1.0/24\", \"claimed_member\": true} "
            "Usable hosts:   {\"cidr\": \"/24\", \"claimed_usable_hosts\": 254} "
            "Port class:     {\"port_number\": 443, \"claimed_port_class\": \"well_known\"}"
        ),
    ),

    # ── cybersecurity ───────────────────────────────────────────────────────
    _tool(
        "verify_cybersecurity",
        (
            "Verify cybersecurity claims — entropy of passwords/keys, usable host counts, "
            "CVSS severity ratings. Security is a formal property: a 128-bit key has exactly "
            "2^128 possibilities; a CVSS score of 9.8 is critical by definition. "
            "CONFIRMED means the security claim is exact. "
            "Axis: information_encoding, authority_trust."
        ),
        (
            "Entropy:        {\"charset_size\": 95, \"length\": 16, \"claimed_entropy_bits\": 104.9} "
            "CVSS severity:  {\"cvss_score\": 9.8, \"claimed_severity\": \"critical\"} "
            "Usable hosts:   {\"cidr\": \"/24\", \"claimed_usable_hosts\": 254}"
        ),
    ),

    # ── linguistics ─────────────────────────────────────────────────────────
    _tool(
        "verify_linguistics",
        (
            "Verify linguistic claims — morpheme counts, syllable structure, vowel harmony, "
            "phonological validity. Language has formal structure: a word either contains "
            "the claimed number of morphemes or it does not. "
            "CONFIRMED means the linguistic claim holds by formal rule. "
            "Axis: information_encoding, formal_reasoning."
        ),
        (
            "Morpheme count:  {\"word\": \"unhappiness\", \"claimed_morpheme_count\": 3} "
            "Syllable count:  {\"word\": \"elephant\",   \"claimed_syllable_count\": 3}"
        ),
    ),

    # ── quantum computing ────────────────────────────────────────────────────
    _tool(
        "verify_quantum_computing",
        (
            "Verify quantum computing claims — qubit state vectors, gate operations, "
            "Grover's search speedup, quantum volume. Quantum mechanics has exact laws: "
            "a valid qubit state must have norm 1; Hadamard applied to |0⟩ gives exactly "
            "|+⟩. CONFIRMED means the quantum computing claim is exact. "
            "Axis: information_encoding, formal_reasoning."
        ),
        (
            "Qubit state:     {\"state_vector\": [0.707, 0.707], \"claimed_valid_qubit\": true} "
            "Grover speedup:  {\"n_items\": 1000000, \"claimed_queries\": 1000, \"claimed_speedup\": \"quadratic\"}"
        ),
    ),

    # ── electrical ──────────────────────────────────────────────────────────
    _tool(
        "verify_electrical",
        (
            "Verify electrical claims — Ohm's law (V=IR), power (P=VI), Kirchhoff's voltage "
            "law, RC time constants. Electrical circuits obey conservation of charge and energy "
            "with absolute precision. CONFIRMED means the electrical claim is correct. "
            "Axis: conservation_balance."
        ),
        (
            "Ohm's law:  {\"voltage_v\": 12, \"resistance_ohm\": 4, \"claimed_current_a\": 3.0} "
            "Power:      {\"voltage_v\": 12, \"current_a\": 3.0, \"claimed_power_w\": 36} "
            "Time const: {\"resistance_ohm\": 1000, \"capacitance_f\": 0.001, \"claimed_tau_s\": 1.0}"
        ),
    ),

    # ── energy ──────────────────────────────────────────────────────────────
    _tool(
        "verify_energy",
        (
            "Verify energy claims — work done, gravitational potential energy, efficiency, "
            "power output, Carnot efficiency. Energy is the most fundamental conserved "
            "quantity in the physical creation — it cannot be created from nothing or "
            "destroyed into nothing. CONFIRMED means the energy claim is consistent with "
            "conservation. Axis: conservation_balance."
        ),
        (
            "Work:               {\"force_n\": 100, \"distance_m\": 10, \"claimed_work_j\": 1000} "
            "Potential energy:   {\"mass_kg\": 2.0, \"height_m\": 5.0, \"claimed_pe_j\": 98.1} "
            "Efficiency:         {\"useful_output_j\": 800, \"total_input_j\": 1000, \"claimed_efficiency\": 0.8}"
        ),
    ),

    # ── optics ──────────────────────────────────────────────────────────────
    _tool(
        "verify_optics",
        (
            "Verify optical claims — Snell's law refraction angles, thin-lens focal length, "
            "critical angle for total internal reflection. Light follows precise geometric "
            "laws: the angle of refraction is uniquely determined by Snell's law. "
            "CONFIRMED means the optical claim is exact. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Snell's law:  {\"n1\": 1.0, \"n2\": 1.5, \"angle_i_deg\": 30, \"claimed_angle_r_deg\": 19.47} "
            "Thin lens:    {\"object_distance_m\": 0.3, \"focal_length_m\": 0.1, \"claimed_image_distance_m\": 0.15}"
        ),
    ),

    # ── acoustics ───────────────────────────────────────────────────────────
    _tool(
        "verify_acoustics",
        (
            "Verify acoustic claims — Doppler shift, decibel levels, speed of sound. "
            "Sound is a physical wave obeying conservation laws: its speed, frequency shift, "
            "and intensity are all exactly determined by the physical parameters. "
            "CONFIRMED means the acoustic claim is correct. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Doppler:    {\"source_freq_hz\": 440, \"source_speed_ms\": 10, \"observer_speed_ms\": 0, \"claimed_observed_freq_hz\": 452.9} "
            "Decibels:   {\"intensity_wm2\": 0.01, \"claimed_db\": 100} "
            "Sound speed: {\"claimed_speed_ms\": 343}"
        ),
    ),

    # ── geology ─────────────────────────────────────────────────────────────
    _tool(
        "verify_geology",
        (
            "Verify geological claims — radiometric dating, Mohs hardness scratch tests, "
            "Richter scale amplitude ratios. The geological record is a precise archive of "
            "deep time: radioactive decay follows exponential law exactly; the Richter scale "
            "is logarithmic with exact ratios. CONFIRMED means the geological claim is exact. "
            "Axis: time_sequence, physical_substance, conservation_balance."
        ),
        (
            "Richter ratio:    {\"richter_M1\": 6.0, \"richter_M2\": 7.0, \"claimed_amplitude_ratio\": 10.0} "
            "Mohs scratch:     {\"mineral_hardness\": 7.0, \"tool_hardness\": 5.5, \"claimed_can_scratch\": false} "
            "Radiometric date: {\"N_remaining\": 0.5, \"N_original\": 1.0, \"half_life_years\": 5730, \"claimed_age_years\": 5730}"
        ),
    ),

    # ── hydrology ───────────────────────────────────────────────────────────
    _tool(
        "verify_hydrology",
        (
            "Verify hydrological claims — continuity equation flow rates, Darcy's law "
            "groundwater flux, Reynolds number. Water obeys conservation of mass precisely: "
            "what enters a system must exit or be stored. "
            "CONFIRMED means the hydrological claim is consistent with conservation. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Continuity:   {\"area1_m2\": 2.0, \"velocity1_ms\": 3.0, \"area2_m2\": 6.0, \"claimed_velocity2_ms\": 1.0} "
            "Darcy:        {\"K\": 0.0001, \"area_m2\": 100, \"gradient\": 0.01, \"claimed_flux_m3s\": 0.0001}"
        ),
    ),

    # ── meteorology ─────────────────────────────────────────────────────────
    _tool(
        "verify_meteorology",
        (
            "Verify meteorological claims — dew point temperature, NOAA wind chill, "
            "relative humidity. Atmospheric physics is governed by thermodynamic laws: "
            "the dew point is exactly determined by temperature and humidity. "
            "CONFIRMED means the meteorological claim is correct. "
            "Axis: conservation_balance, physical_substance, time_sequence."
        ),
        (
            "Dew point:   {\"temperature_c\": 20, \"relative_humidity_pct\": 60, \"claimed_dew_point_c\": 11.89} "
            "Wind chill:  {\"temp_f\": 32, \"wind_mph\": 15, \"claimed_wind_chill_f\": 23}"
        ),
    ),

    # ── astronomy ───────────────────────────────────────────────────────────
    _tool(
        "verify_astronomy",
        (
            "Verify astronomical claims — Kepler's third law orbital periods, stellar "
            "parallax distances, light travel time. The heavens obey precise physical law: "
            "Kepler's relationship between orbital period and semi-major axis is exact. "
            "CONFIRMED means the astronomical claim is correct. "
            "Axis: time_sequence, conservation_balance, physical_substance."
        ),
        (
            "Kepler's 3rd:     {\"semi_major_axis_au\": 1.0, \"claimed_period_years\": 1.0} "
            "Parallax distance: {\"parallax_arcsec\": 0.1, \"claimed_distance_parsec\": 10} "
            "Light travel:     {\"distance_ly\": 8.0, \"claimed_travel_time_minutes\": 8}"
        ),
    ),

    # ── geography ───────────────────────────────────────────────────────────
    _tool(
        "verify_geography",
        (
            "Verify geographic claims — coordinate validity, great-circle distances, "
            "initial bearing, UTM zone assignment. Physical place has exact rules: "
            "latitude is bounded by [-90, 90]; a great-circle distance follows the "
            "Haversine formula exactly. CONFIRMED means the geographic claim is correct. "
            "Axis: physical_substance."
        ),
        (
            "Coord valid:  {\"latitude\": 45.0, \"longitude\": -90.0, \"claimed_valid\": true} "
            "Distance:     {\"lat1\": 40.7128, \"lon1\": -74.0060, \"lat2\": 51.5074, \"lon2\": -0.1278, \"claimed_distance_km\": 5570}"
        ),
    ),

    # ── agriculture ─────────────────────────────────────────────────────────
    _tool(
        "verify_agriculture",
        (
            "Verify agricultural claims — USDA hardiness zone temperature ranges, "
            "soil pH effects, nutrient deficiency symptoms, Growing Degree Days. "
            "Crop growth follows precise biological and physical rules. "
            "CONFIRMED means the agricultural claim is correct. "
            "Axis: conservation_balance, physical_substance, time_sequence."
        ),
        (
            "Hardiness zone:  {\"zone\": \"7b\", \"min_temp_f\": 5, \"claimed_in_range\": true} "
            "GDD:             {\"t_max_f\": 85, \"t_min_f\": 55, \"t_base_f\": 50, \"claimed_gdd\": 20}"
        ),
    ),

    # ── nutrition ───────────────────────────────────────────────────────────
    _tool(
        "verify_nutrition",
        (
            "Verify nutritional claims — caloric content (Atwater factors: protein/carb = 4 "
            "kcal/g, fat = 9 kcal/g), Mifflin-St Jeor BMR, macronutrient gram-to-calorie "
            "conversion. Nutrition is a conservation problem: calories in are exactly "
            "determined by macronutrient composition. "
            "CONFIRMED means the nutritional claim is exact. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Calories:    {\"protein_g\": 30, \"carbs_g\": 50, \"fat_g\": 10, \"claimed_calories\": 410} "
            "BMR (male):  {\"weight_kg\": 80, \"height_cm\": 175, \"age_years\": 30, \"sex\": \"male\", \"claimed_bmr\": 1853}"
        ),
    ),

    # ── manufacturing ───────────────────────────────────────────────────────
    _tool(
        "verify_manufacturing",
        (
            "Verify manufacturing quality claims — process capability index (Cp/Cpk), "
            "tolerance stack-up, yield rate. Manufacturing precision is measurable: "
            "a process with Cp > 1.33 has a defined defect rate. "
            "CONFIRMED means the manufacturing claim is correct. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Cp index:  {\"usl\": 10.5, \"lsl\": 9.5, \"process_std\": 0.1666, \"claimed_cp\": 1.0} "
            "Tolerance: {\"tolerances\": [0.1, 0.1, 0.1], \"claimed_stack\": 0.3}"
        ),
    ),

    # ── finance ─────────────────────────────────────────────────────────────
    _tool(
        "verify_finance",
        (
            "Verify financial claims — compound interest, present value, bond pricing, "
            "mortgage payments, break-even analysis. Money is a conservative system: "
            "compound interest follows an exact formula; a payment stream has a precise "
            "present value. CONFIRMED means the financial claim is mathematically exact. "
            "Axis: conservation_balance, authority_trust."
        ),
        (
            "Compound interest: {\"principal\": 1000, \"rate\": 0.05, \"periods\": 10, \"claimed_amount\": 1628.89} "
            "Present value:     {\"future_value\": 1000, \"rate\": 0.05, \"periods\": 10, \"claimed_pv\": 613.91} "
            "Mortgage:          {\"principal\": 200000, \"annual_rate\": 0.04, \"years\": 30, \"claimed_monthly_payment\": 954.83}"
        ),
    ),

    # ── economics ───────────────────────────────────────────────────────────
    _tool(
        "verify_economics",
        (
            "Verify economic claims — simple interest, Rule of 72, inflation adjustment, "
            "GDP per capita, price elasticity. Economic quantities follow precise formulas: "
            "simple interest is I = P × r × t exactly. "
            "CONFIRMED means the economic claim is mathematically correct. "
            "Axis: conservation_balance, authority_trust."
        ),
        (
            "Simple interest: {\"principal\": 1000, \"rate\": 0.05, \"time_years\": 3, \"claimed_simple_interest\": 150} "
            "Rule of 72:      {\"rate_percent\": 8, \"claimed_doubling_years\": 9} "
            "GDP per capita:  {\"gdp\": 21000000000000, \"population\": 331000000, \"claimed_gdp_per_capita\": 63445}"
        ),
    ),

    # ── labor ────────────────────────────────────────────────────────────────
    _tool(
        "verify_labor",
        (
            "Verify labor and wage claims — overtime pay (FLSA 1.5× rule), annual salary "
            "from hourly rate, minimum wage compliance. Labor law creates binding floor "
            "constraints: overtime is exactly 1.5× the regular rate for hours over 40. "
            "CONFIRMED means the labor claim is legally and mathematically correct. "
            "Axis: authority_trust, conservation_balance."
        ),
        (
            "Overtime:       {\"hourly_rate\": 20, \"regular_hours\": 40, \"overtime_hours\": 5, \"claimed_weekly_pay\": 950} "
            "Annual salary:  {\"hourly_rate\": 25, \"hours_per_week\": 40, \"claimed_annual_salary\": 52000}"
        ),
    ),

    # ── real estate ─────────────────────────────────────────────────────────
    _tool(
        "verify_real_estate",
        (
            "Verify real estate claims — cap rate, loan-to-value ratio, gross rent multiplier, "
            "debt service coverage ratio. Real estate valuation uses precise ratios; a cap rate "
            "is exactly NOI / property value. "
            "CONFIRMED means the real estate claim is mathematically correct. "
            "Axis: authority_trust, physical_substance."
        ),
        (
            "Cap rate:  {\"noi\": 80000, \"property_value\": 1000000, \"claimed_cap_rate\": 0.08} "
            "LTV:       {\"loan_amount\": 750000, \"property_value\": 1000000, \"claimed_ltv\": 0.75} "
            "GRM:       {\"property_value\": 300000, \"annual_rent\": 24000, \"claimed_grm\": 12.5}"
        ),
    ),

    # ── construction ────────────────────────────────────────────────────────
    _tool(
        "verify_construction",
        (
            "Verify construction claims — concrete mix water-cement ratio, steel rebar "
            "spacing, stair riser height codes. Construction is governed by physical laws "
            "and codes: a w/c ratio determines strength exactly; code specifies riser height. "
            "CONFIRMED means the construction claim meets the relevant standard. "
            "Axis: conservation_balance, physical_substance."
        ),
        (
            "Water-cement ratio: {\"water_kg\": 180, \"cement_kg\": 400, \"claimed_wc_ratio\": 0.45} "
            "Stair riser:        {\"riser_height_in\": 7.5, \"claimed_code_compliant\": true}"
        ),
    ),

    # ── soil science ────────────────────────────────────────────────────────
    _tool(
        "verify_soil_science",
        (
            "Verify soil science claims — soil pH classification, soil texture triangle "
            "(USDA), bulk density. Soil properties follow classification schemes with "
            "precise boundaries: a pH of 6.2 is mildly acidic by exact definition. "
            "CONFIRMED means the soil classification is correct. "
            "Axis: conservation_balance, physical_substance, time_sequence."
        ),
        (
            "pH class:    {\"ph\": 6.2, \"claimed_class\": \"slightly_acidic\"} "
            "Texture:     {\"sand_pct\": 50, \"silt_pct\": 30, \"clay_pct\": 20, \"claimed_texture\": \"loam\"}"
        ),
    ),

    # ── medicine ────────────────────────────────────────────────────────────
    _tool(
        "verify_medicine",
        (
            "Verify medical claims — BMI classification, normal reference ranges (heart rate, "
            "blood pressure, glucose, creatinine), medication dosage weight-based calculations. "
            "Clinical medicine uses precisely defined normal ranges: a heart rate of 120 bpm "
            "at rest is tachycardic by exact clinical definition. "
            "CONFIRMED means the medical claim is correct by clinical standard. "
            "Axis: conservation_balance, physical_substance, time_sequence."
        ),
        (
            "BMI class:   {\"weight_kg\": 70, \"height_m\": 1.75, \"claimed_bmi_class\": \"normal\"} "
            "Heart rate:  {\"heart_rate_bpm\": 75, \"claimed_classification\": \"normal\"} "
            "Dosage:      {\"dose_mg_per_kg\": 10, \"weight_kg\": 70, \"claimed_dose_mg\": 700}"
        ),
    ),

    # ── exercise science ────────────────────────────────────────────────────
    _tool(
        "verify_exercise_science",
        (
            "Verify exercise science claims — VO2max estimation, target heart rate zones, "
            "caloric expenditure by MET, one-rep max estimation. Exercise physiology has "
            "precise formulas: target heart rate is exactly (220 - age) × intensity. "
            "CONFIRMED means the exercise science claim is correct. "
            "Axis: conservation_balance, physical_substance, time_sequence."
        ),
        (
            "Target HR:   {\"age\": 30, \"intensity\": 0.7, \"claimed_target_hr\": 133} "
            "MET calories: {\"met\": 8.0, \"weight_kg\": 70, \"duration_min\": 30, \"claimed_calories\": 280}"
        ),
    ),

    # ── sports analytics ────────────────────────────────────────────────────
    _tool(
        "verify_sports_analytics",
        (
            "Verify sports statistics — batting average, ERA, Pythagorean win expectation, "
            "passer rating, team efficiency metrics. Sports statistics are computed by exact "
            "formulas: a batting average is hits / at-bats to four decimal places. "
            "CONFIRMED means the sports statistic is correctly computed. "
            "Axis: formal_reasoning, time_sequence."
        ),
        (
            "Batting avg:   {\"hits\": 150, \"at_bats\": 500, \"claimed_avg\": 0.300} "
            "Pythagorean:   {\"runs_scored\": 850, \"runs_allowed\": 750, \"claimed_win_pct\": 0.563} "
            "ERA:           {\"earned_runs\": 80, \"innings_pitched\": 200, \"claimed_era\": 3.60}"
        ),
    ),

    # ── music theory ────────────────────────────────────────────────────────
    _tool(
        "verify_music_theory",
        (
            "Verify music theory claims — interval semitone counts, frequency ratios in "
            "equal temperament, scale degree counts, chord membership. Music is encoded "
            "mathematics: equal temperament divides the octave into exactly 12 equal "
            "semitones; each interval has an exact frequency ratio. "
            "CONFIRMED means the music theory claim is exact. "
            "Axis: information_encoding, formal_reasoning, time_sequence."
        ),
        (
            "Interval:     {\"interval_name\": \"perfect_fifth\", \"claimed_semitones\": 7} "
            "Frequency:    {\"note\": \"A4\", \"claimed_frequency_hz\": 440} "
            "Scale:        {\"scale\": \"major\", \"claimed_note_count\": 7}"
        ),
    ),

    # ── calendar / time ──────────────────────────────────────────────────────
    _tool(
        "verify_calendar_time",
        (
            "Verify calendar and time claims — leap year rules (Gregorian), day-of-week "
            "calculation (Zeller's congruence), Unix epoch conversion, timezone offset. "
            "Time has exact structure: 1900 is not a leap year because the Gregorian reform "
            "is deterministic. CONFIRMED means the calendar claim is correct. "
            "Axis: time_sequence."
        ),
        (
            "Leap year:    {\"year\": 1900, \"claimed_is_leap\": false} "
            "Day of week:  {\"date\": \"2000-01-01\", \"claimed_day\": \"Saturday\"} "
            "Epoch:        {\"datetime_utc\": \"1970-01-01T00:00:00Z\", \"claimed_unix_epoch\": 0}"
        ),
    ),

    # ── number theory ───────────────────────────────────────────────────────
    _tool(
        "verify_number_theory",
        (
            "Verify number theory claims — primality, GCD, LCM, modular arithmetic, "
            "Euler's totient, Chinese Remainder Theorem. Number theory is pure formal "
            "reasoning: a number is prime or it is not, with no ambiguity. "
            "CONFIRMED means the number-theoretic claim is correct. "
            "Axis: formal_reasoning."
        ),
        (
            "Primality:  {\"n\": 97, \"claimed_prime\": true} "
            "GCD:        {\"a\": 48, \"b\": 18, \"claimed_gcd\": 6} "
            "Modular:    {\"a\": 7, \"b\": 3, \"mod\": 5, \"claimed_result\": 1}"
        ),
    ),

    # ── combinatorics ───────────────────────────────────────────────────────
    _tool(
        "verify_combinatorics",
        (
            "Verify combinatorial claims — permutations, combinations, binomial coefficients, "
            "derangements, Catalan numbers. Counting has exact answers: C(10,3) = 120 "
            "with no approximation. CONFIRMED means the combinatorial claim is exact. "
            "Axis: formal_reasoning."
        ),
        (
            "Permutation:  {\"n\": 5,  \"r\": 5,  \"claimed_permutations\": 120} "
            "Combination:  {\"n\": 10, \"r\": 3,  \"claimed_combinations\": 120} "
            "Derangement:  {\"n\": 4,             \"claimed_derangements\": 9}"
        ),
    ),

    # ── geometry ─────────────────────────────────────────────────────────────
    _tool(
        "verify_geometry",
        (
            "Verify geometric claims — area, perimeter, volume, surface area, angle sums, "
            "Pythagorean theorem. Geometry is formal: the area of a circle is exactly π r². "
            "CONFIRMED means the geometric claim is exact. "
            "Axis: physical_substance, formal_reasoning."
        ),
        (
            "Circle area:    {\"radius\": 5, \"claimed_area\": 78.54} "
            "Pythagorean:    {\"a\": 3, \"b\": 4, \"claimed_c\": 5} "
            "Sphere volume:  {\"radius\": 3, \"claimed_volume\": 113.10}"
        ),
    ),

    # ── photography ─────────────────────────────────────────────────────────
    _tool(
        "verify_photography",
        (
            "Verify photography and optics claims — exposure value (EV), depth of field, "
            "hyperfocal distance, lens magnification. Photography applies exact physical "
            "optics: EV is log₂(N²/t) exactly. "
            "CONFIRMED means the photographic claim is correct. "
            "Axis: physical_substance, information_encoding."
        ),
        (
            "EV:           {\"aperture_f\": 2.8, \"shutter_s\": 0.01, \"claimed_ev\": 12.97} "
            "Magnification: {\"image_distance_mm\": 150, \"object_distance_mm\": 1000, \"claimed_magnification\": 0.15}"
        ),
    ),
]


# ── context block ──────────────────────────────────────────────────────────────

def context_block() -> str:
    """System prompt fragment for any agent operator to include.

    This text orients an agent to what Concordance is, what CONFIRMED means,
    and how to interpret verifier output in terms of the created order.
    """
    return """\
You have access to the Concordance verification engine — a system that verifies \
claims against the precise structure of the created order across 45 domains.

When you call a Concordance tool and receive CONFIRMED, that means the claim was \
independently computed and found to match — not inferred, not approximated, verified. \
When you receive DISCORDANT, the claim contradicts the created order in that domain; \
the detail field says what the actual value is. When you receive NOT_APPLICABLE, the \
spec did not contain the required fields for that check.

Every domain in Concordance connects to one or more axes of the created order:
  conservation_balance  — energy, mass, charge, and momentum are conserved exactly
  information_encoding  — DNA, code, language, and keys encode meaning precisely
  formal_reasoning      — logic and mathematics are the language of necessity
  physical_substance    — matter occupies place with verifiable properties
  authority_trust       — legitimate claims require a witness chain
  time_sequence         — events have exact order and causality

Use Concordance tools when a user makes a factual claim in a covered domain. \
Surface the verification result and the detail field — do not hide DISCORDANT results. \
A DISCORDANT finding is the most useful output: it is the engine saying "this \
contradicts how the realm was built." \

Benchmark accuracy: 135/135 items verified correctly (100%) across all 45 domains \
using claude-haiku-4-5. This is not a calculator. It is a witness to the structure \
of the created order.\
"""


# ── manifest builder ───────────────────────────────────────────────────────────

def build_manifest() -> Dict[str, Any]:
    """Return the full OpenAI-compatible manifest."""
    return {
        "schema_version": "1.0",
        "engine": "concordance",
        "benchmark": {"score": "135/135", "accuracy": 1.0, "domains": 45},
        "axes": _AXES,
        "tools": _MANIFEST,
        "context_block": context_block(),
    }


# ── dispatch ───────────────────────────────────────────────────────────────────

def dispatch(tool_name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    """Call a verifier by name and return its result.

    spec is a flat dict of arguments. The dispatch tries fn(**spec) first
    (for kwarg-style tools like verify_physics_dimensional) then fn(spec)
    (for single-argument spec-style tools like verify_acoustics).

    Returns {"ok": True, "result": ...} or {"ok": False, "error": "..."}.
    """
    if not _TOOLS_AVAILABLE:
        return {"ok": False, "error": "concordance engine not available"}

    fn = ALL_TOOLS.get(tool_name)
    if fn is None:
        available = sorted(k for k in ALL_TOOLS if k.startswith("verify"))
        return {"ok": False, "error": f"unknown tool: {tool_name!r}",
                "available": available}

    def _normalise(result: Any) -> Any:
        if isinstance(result, list):
            return [(r.to_dict() if hasattr(r, "to_dict") else r) for r in result]
        return result

    try:
        result = fn(**spec)
        return {"ok": True, "result": _normalise(result)}
    except TypeError:
        pass
    try:
        result = fn(spec)
        return {"ok": True, "result": _normalise(result)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ── benchmark summary ─────────────────────────────────────────────────────────

def benchmark_summary() -> Dict[str, Any]:
    """Return the latest benchmark results from the eval/ directory."""
    results_file = _BENCH_DIR / "results_ext_claude_haiku_4_5_20251001_tools.jsonl"
    if not results_file.exists():
        return {"ok": False, "error": "benchmark results not found"}

    items: List[Dict] = []
    with results_file.open() as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    if not items:
        return {"ok": False, "error": "benchmark results file is empty"}

    correct = sum(1 for i in items if i.get("correct"))
    total = len(items)

    domain_scores: Dict[str, Dict] = {}
    for item in items:
        d = item.get("domain", "unknown")
        if d not in domain_scores:
            domain_scores[d] = {"correct": 0, "total": 0}
        domain_scores[d]["total"] += 1
        if item.get("correct"):
            domain_scores[d]["correct"] += 1

    domain_summary = {
        d: f"{v['correct']}/{v['total']}"
        for d, v in sorted(domain_scores.items())
    }

    timings = [i.get("elapsed_s", 0) for i in items if i.get("elapsed_s")]
    avg_s = round(sum(timings) / len(timings), 2) if timings else None

    return {
        "ok": True,
        "model": "claude-haiku-4-5-20251001",
        "mode": "with_tools",
        "score": f"{correct}/{total}",
        "accuracy": round(correct / total, 4) if total else 0,
        "avg_time_s": avg_s,
        "domains": domain_summary,
    }
