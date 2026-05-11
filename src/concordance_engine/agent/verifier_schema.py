"""Verifier-schema introspection.

Reads the source of each verifier's ``run(packet)`` function and extracts
the field names it actually checks. The result is an authoritative
field-spec block that gets injected into the polymathic classifier
prompt at module load time. Hand-maintaining field names in a giant
system prompt produces silent drift; introspection keeps the prompt in
sync with the code.

What this does NOT do:
  - parse Python (just regex-scans for quoted field names inside run())
  - guarantee field-name completeness for verifiers without a run()
  - distinguish required vs optional keys

What it DOES do:
  - extract the set of keys each verifier looks at (matches the actual
    code, by definition)
  - return a formatted block suitable for stuffing into the classifier
    system prompt
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

_VERIFIERS_DIR = Path(__file__).resolve().parents[1] / "verifiers"

# Some verifiers don't use the packet-key pattern (chemistry, mathematics,
# physics_dimensional, etc.) — they take a flat spec or named args. For
# those, we hand-curate the field set since the run() introspection won't
# capture them.
_HAND_CURATED: Dict[str, List[str]] = {
    "chemistry":               ["equation"],
    "physics_dimensional":     ["equation", "symbols"],
    "physics_conservation":    ["before", "after", "law"],
    "physics":                 ["equation", "symbols", "before", "after", "law"],
    "mathematics":             ["mode", "params"],
    "thermodynamics": [
        "T_hot_K", "T_cold_K", "claimed_efficiency",
        "pressure_Pa", "volume_m3", "moles", "temperature_K",
        "claimed_pressure_Pa", "claimed_volume_m3", "claimed_temperature_K",
        "mass_kg", "specific_heat_J_per_kgK", "delta_T_K", "claimed_heat_J",
        "heat_J", "claimed_entropy_change_J_per_K",
        # phase points at 1 atm (water, ethanol, iron, mercury, etc.):
        "substance",
        "claimed_boiling_point_C", "claimed_boiling_point_F", "claimed_boiling_point_K",
        "claimed_melting_point_C", "claimed_melting_point_F", "claimed_melting_point_K",
    ],
    "energy": [
        "mass_kg", "height_m", "claimed_potential_energy_J",
        "velocity_m_per_s", "claimed_kinetic_energy_J",
        "power_W", "time_s", "claimed_energy_J",
    ],
    "biology": [
        "n_replicates", "claimed_powered",
        "dose", "response", "claimed_monotonic",
        "p_allele", "q_allele", "claimed_AA", "claimed_Aa", "claimed_aa",
        "primer_seq", "claimed_tm_c", "claimed_gc_pct",
        "molarity_M", "volume_L", "claimed_moles",
        "parent1_genotype", "parent2_genotype", "claimed_ratio",
    ],
    "statistics_pvalue":       ["test", "n1", "n2", "mean1", "mean2", "sd1", "sd2", "claimed_p", "tail"],
    "statistics_multiple_comparisons": ["p_values", "alpha", "method", "claimed_significant"],
    "statistics_confidence_interval": ["mean", "sd", "n", "confidence_level", "claimed_lower", "claimed_upper"],
    "statistics":              ["test", "p_values", "alpha", "method", "mean", "sd", "n", "confidence_level"],
    "labor":                   ["hourly_rate", "hours_worked", "claimed_gross_pay",
                                "regular_hours", "overtime_hours", "claimed_overtime_pay",
                                "annual_salary", "claimed_hourly_equivalent"],
    "economics":               ["principal", "rate", "time_years", "claimed_simple_interest",
                                "rate_percent", "claimed_doubling_years",
                                "gdp", "population", "claimed_gdp_per_capita"],
    "real_estate":             ["loan_amount", "appraised_value", "claimed_ltv",
                                "net_operating_income", "property_value", "claimed_cap_rate"],
    "music_theory":            ["note_a", "note_b", "claimed_semitones"],
    "calendar_time":           ["year", "claimed_leap", "date", "claimed_weekday"],
    "ecology":                 ["births", "deaths", "immigrants", "emigrants", "claimed_growth_rate"],
    "soil_science":            ["sand_pct", "silt_pct", "clay_pct", "claimed_texture_class"],
    "construction":            ["length_m", "width_m", "depth_m", "claimed_volume_m3",
                                "area_m2", "coverage_m2_per_L", "claimed_liters"],
    "architecture":            ["floor_area_m2", "lot_area_m2", "claimed_FAR",
                                "claimed_occupants", "occupant_load_factor"],
    "materials_science":       ["material", "stress_Pa", "strain", "claimed_youngs_modulus_Pa"],
    "operations_research":     ["capacity", "demand", "costs", "claimed_optimal_allocation"],
    "law":                     ["statute_or_rule", "facts", "claimed_applies"],
    "history_chronology":      ["event", "claimed_year", "event_a", "event_b", "claimed_event_a_before_event_b"],
    "scripture_anchors":       ["refs", "claimed_pattern"],
    "theology_doctrine":       ["claim", "claimed_orthodox"],
    "governance_decision_packet": ["packet"],
    "philosophy":              ["argument_form", "premises", "conclusion", "claimed_valid"],
    "rhetoric":                ["argument", "claimed_fallacy"],
    "medicine":                ["dose_mg", "weight_kg", "claimed_mg_per_kg",
                                "drug_name", "indication", "claimed_appropriate"],
    "cybersecurity":           ["password", "claimed_entropy_bits", "cipher", "key_length", "claimed_secure"],
    "quantum_computing":       ["n_qubits", "claimed_state_space", "gate", "claimed_unitary"],
    "nuclear_physics":         ["nuclide", "claimed_half_life_s", "mass_defect_kg", "claimed_energy_J"],
    "computer_science":        ["complexity_class", "function_string", "claimed_O",
                                "algo_name", "input_size", "claimed_runtime_ms"],
    "oceanography":            ["temperature_C", "salinity_psu", "claimed_density_kg_per_m3"],
    "phase":                   ["domain", "claim", "expected_phase"],
}


def _extract_run_keys(verifier_path: Path) -> List[str]:
    """Read a verifier's source and pull out every quoted field name
    referenced inside its run() function. Best-effort regex; misses
    field names built dynamically."""
    try:
        src = verifier_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    # Grab the body of run(packet, ...) up to the next top-level def
    m = re.search(r"^def run\(packet[^)]*\)[^:]*:(.+?)(?=^\S|\Z)", src, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    body = m.group(1)
    # All quoted strings that look like field names: lowercase + underscore
    raw = re.findall(r"""['"]([a-zA-Z][a-zA-Z_0-9]+)['"]""", body)
    # Filter out obvious non-field strings (verbs, log fragments)
    blacklist = {
        "claim", "claims", "name", "spec", "checks", "detail",
        "verify", "verdict", "data", "status",
    }
    seen = set()
    out: List[str] = []
    for k in raw:
        kl = k.lower()
        if kl in blacklist:
            continue
        if kl == verifier_path.stem.lower():  # drop the domain self-tag
            continue
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _collect_all() -> Dict[str, List[str]]:
    """Return {domain: [field, ...]} merging hand-curated + introspected."""
    out: Dict[str, List[str]] = {}
    if _VERIFIERS_DIR.exists():
        for path in sorted(_VERIFIERS_DIR.glob("*.py")):
            if path.stem.startswith("_") or path.stem == "base":
                continue
            keys = _extract_run_keys(path)
            if keys:
                out[path.stem] = keys
    # Layer hand-curated on top (overrides where present)
    for domain, fields in _HAND_CURATED.items():
        out[domain] = fields
    return out


def format_field_spec_block() -> str:
    """Return a multi-line string suitable for embedding in a system
    prompt. Each line: "domain: {field1, field2, ...}".
    """
    domains = _collect_all()
    lines: List[str] = []
    for domain in sorted(domains):
        fields = domains[domain]
        if not fields:
            continue
        # Cap field listing length so a runaway introspection doesn't
        # explode the prompt. Most verifiers have ≤ 20 fields.
        fields_to_show = fields[:24]
        lines.append(f"  {domain:30} {{{', '.join(fields_to_show)}}}")
    return "\n".join(lines)


# Cached at module load — the verifier source doesn't change during a process.
FIELD_SPEC_BLOCK: str = format_field_spec_block()
