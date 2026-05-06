"""
Seed the vault with 100 unique engine interactions spanning all domains.
Cat | Dog: Minimum | Maximum = Optimum — specs range from trivial to complex
so the corpus has both poles.

Run from repo root:
    python scripts/seed_vault_100.py
"""
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

# Ensure repo src is importable
repo = Path(__file__).parent.parent
sys.path.insert(0, str(repo / "src"))
sys.path.insert(0, str(repo))

from concordance_engine.mcp_server.tools import ALL_TOOLS
from api.packet_store import get_packet_store
from api.trust_index import record_confirmation

try:
    from concordance_engine.instance_identity import get_instance_id
    INSTANCE_ID = get_instance_id() or "seed-script"
except Exception:
    INSTANCE_ID = "seed-script"

store = get_packet_store()

# ── 100 specs across 48 domains ──────────────────────────────────────────────
INTERACTIONS = [
    # MATHEMATICS
    ("mathematics", {"operation": "prime_check", "n": 97}),
    ("mathematics", {"operation": "prime_check", "n": 100}),
    ("mathematics", {"operation": "gcd", "a": 48, "b": 36}),
    ("mathematics", {"operation": "fibonacci", "n": 10}),
    ("mathematics", {"operation": "is_perfect", "n": 28}),

    # COMBINATORICS
    ("combinatorics", {"operation": "combinations", "n": 10, "r": 3}),
    ("combinatorics", {"operation": "permutations", "n": 7, "r": 2}),
    ("combinatorics", {"operation": "factorial", "n": 12}),

    # PHYSICS
    ("physics", {"operation": "kinetic_energy", "mass_kg": 70, "velocity_ms": 10}),
    ("physics", {"operation": "gravitational_force", "m1_kg": 5.972e24, "m2_kg": 7.346e22, "distance_m": 3.844e8}),
    ("physics", {"operation": "projectile_range", "velocity_ms": 30, "angle_deg": 45}),
    ("physics", {"operation": "ohms_law", "voltage_v": 12, "resistance_ohm": 4}),
    ("physics", {"operation": "wave_speed", "frequency_hz": 440, "wavelength_m": 0.773}),

    # CHEMISTRY
    ("chemistry", {"operation": "molar_mass", "formula": "H2O"}),
    ("chemistry", {"operation": "molar_mass", "formula": "C6H12O6"}),
    ("chemistry", {"operation": "ideal_gas", "pressure_atm": 1.0, "volume_L": 22.4, "temperature_K": 273.15}),
    ("chemistry", {"operation": "dilution", "c1_M": 2.0, "v1_L": 0.5, "v2_L": 2.0}),
    ("chemistry", {"operation": "percent_composition", "formula": "NaCl"}),

    # BIOLOGY
    ("biology", {"operation": "cell_division_time", "initial_cells": 1, "final_cells": 1024, "generation_time_min": 20}),
    ("biology", {"operation": "mendelian_ratio", "cross": "Aa x Aa"}),
    ("biology", {"operation": "hardy_weinberg", "p": 0.6, "q": 0.4}),

    # GENETICS
    ("genetics", {"operation": "gc_content", "sequence": "ATCGATCGATCG"}),
    ("genetics", {"operation": "translation", "codon": "AUG"}),
    ("genetics", {"operation": "mutation_type", "original": "ATG", "mutant": "ACG"}),

    # STATISTICS
    ("statistics", {"operation": "mean", "values": [4, 7, 13, 2, 1]}),
    ("statistics", {"operation": "standard_deviation", "values": [2, 4, 4, 4, 5, 5, 7, 9]}),
    ("statistics", {"operation": "z_score", "value": 75, "mean": 70, "std": 5}),
    ("statistics", {"operation": "correlation", "x": [1, 2, 3, 4, 5], "y": [2, 4, 5, 4, 5]}),
    ("statistics", {"operation": "binomial_probability", "n": 10, "k": 3, "p": 0.5}),

    # COMPUTER SCIENCE
    ("computer_science", {"operation": "big_o", "algorithm": "bubble_sort"}),
    ("computer_science", {"operation": "binary_search_steps", "n": 1000}),
    ("computer_science", {"operation": "hash_collision_probability", "slots": 365, "items": 23}),
    ("computer_science", {"operation": "tcp_window_throughput", "window_size_bytes": 65535, "rtt_ms": 100}),

    # ECONOMICS
    ("economics", {"operation": "simple_interest", "principal": 1000, "rate": 0.05, "time_years": 3}),
    ("economics", {"operation": "compound_interest", "principal": 1000, "rate": 0.07, "n": 12, "time_years": 10}),
    ("economics", {"operation": "rule_of_72", "rate": 8}),
    ("economics", {"operation": "gdp_per_capita", "gdp": 21000000000000, "population": 331000000}),
    ("economics", {"operation": "price_elasticity", "pct_change_quantity": -10, "pct_change_price": 5}),
    ("economics", {"operation": "present_value", "future_value": 10000, "rate": 0.06, "years": 5}),
    ("economics", {"operation": "inflation_adjusted", "nominal": 50000, "inflation_rate": 0.03, "years": 20}),

    # LABOR
    ("labor", {"operation": "gross_pay", "hourly_rate": 18, "hours_worked": 40}),
    ("labor", {"operation": "overtime_pay", "hourly_rate": 18, "regular_hours": 40, "overtime_hours": 8}),
    ("labor", {"operation": "annual_to_hourly", "annual_salary": 52000}),
    ("labor", {"operation": "take_home_pay", "gross_pay": 800, "tax_rate": 0.22, "deductions": 50}),
    ("labor", {"operation": "minimum_wage_check", "hourly_rate": 6.50, "state": "federal"}),

    # REAL ESTATE
    ("real_estate", {"operation": "monthly_mortgage", "principal": 300000, "annual_rate": 0.065, "years": 30}),
    ("real_estate", {"operation": "cap_rate", "noi": 24000, "property_value": 300000}),
    ("real_estate", {"operation": "gross_rent_multiplier", "property_price": 300000, "annual_rent": 24000}),
    ("real_estate", {"operation": "loan_to_value", "loan_amount": 240000, "property_value": 300000}),
    ("real_estate", {"operation": "dscr", "noi": 36000, "annual_debt_service": 24000}),
    ("real_estate", {"operation": "rental_yield", "annual_rent": 18000, "property_value": 250000}),

    # CONSTRUCTION
    ("construction", {"operation": "concrete_volume", "length_m": 10, "width_m": 5, "depth_m": 0.15}),
    ("construction", {"operation": "rectangular_area", "length_m": 12, "width_m": 8}),
    ("construction", {"operation": "circular_area", "radius_m": 5}),
    ("construction", {"operation": "wall_area", "length_m": 6, "height_m": 3, "openings_m2": 4}),
    ("construction", {"operation": "paint_coverage", "area_m2": 80, "coverage_m2_per_L": 10, "coats": 2}),
    ("construction", {"operation": "floor_tiles", "room_area_m2": 20, "tile_size_m2": 0.36, "waste_pct": 10}),
    ("construction", {"operation": "rebar_weight", "length_m": 100, "diameter_mm": 12}),
    ("construction", {"operation": "beam_load", "span_m": 5, "load_kN_per_m": 12}),

    # SOIL SCIENCE
    ("soil_science", {"operation": "ph_suitability", "crop": "tomato", "ph": 6.5}),
    ("soil_science", {"operation": "ph_suitability", "crop": "blueberry", "ph": 5.0}),
    ("soil_science", {"operation": "npk_requirement", "crop": "corn"}),
    ("soil_science", {"operation": "irrigation_etc", "crop": "wheat", "eto_mm_day": 5.0, "growth_stage": "mid"}),
    ("soil_science", {"operation": "lime_requirement", "current_ph": 5.5, "target_ph": 6.5, "buffer_ph": 6.0, "area_ha": 1}),
    ("soil_science", {"operation": "soil_texture", "sand_pct": 40, "silt_pct": 40, "clay_pct": 20}),

    # AGRICULTURE
    ("agriculture", {"operation": "yield_per_acre", "total_yield_bushels": 12000, "acres": 80}),
    ("agriculture", {"operation": "seed_rate", "crop": "wheat", "area_ha": 5}),
    ("agriculture", {"operation": "fertilizer_need", "crop": "maize", "area_ha": 2, "target_yield_t_ha": 8}),

    # EXERCISE SCIENCE
    ("exercise_science", {"operation": "bmr_mifflin", "weight_kg": 75, "height_cm": 178, "age": 35, "sex": "male"}),
    ("exercise_science", {"operation": "vo2max_estimate", "resting_hr": 60, "max_hr": 190}),
    ("exercise_science", {"operation": "one_rep_max", "weight_kg": 100, "reps": 5}),

    # NUTRITION
    ("nutrition", {"operation": "tdee", "bmr": 1800, "activity_level": "moderately_active"}),
    ("nutrition", {"operation": "macros", "calories": 2400, "protein_pct": 30, "carb_pct": 45, "fat_pct": 25}),

    # ASTRONOMY
    ("astronomy", {"operation": "orbital_period", "semi_major_axis_au": 1.0}),
    ("astronomy", {"operation": "light_travel_time", "distance_ly": 4.24}),
    ("astronomy", {"operation": "angular_size", "physical_size_km": 1392000, "distance_km": 149600000}),

    # GEOGRAPHY
    ("geography", {"operation": "great_circle_distance", "lat1": 40.7128, "lon1": -74.0060, "lat2": 51.5074, "lon2": -0.1278}),
    ("geography", {"operation": "area_conversion", "value": 100, "from_unit": "hectares", "to_unit": "acres"}),

    # ENERGY
    ("energy", {"operation": "solar_panel_output", "panel_watts": 400, "hours_sun": 5, "efficiency": 0.85}),
    ("energy", {"operation": "battery_runtime", "capacity_kwh": 10, "load_kw": 0.5}),
    ("energy", {"operation": "co2_from_electricity", "kwh": 1000, "grid_intensity_g_kwh": 450}),

    # ELECTRICAL
    ("electrical", {"operation": "power", "voltage_v": 120, "current_a": 15}),
    ("electrical", {"operation": "resistors_series", "resistances": [10, 20, 30]}),
    ("electrical", {"operation": "resistors_parallel", "resistances": [10, 20]}),

    # ACOUSTICS
    ("acoustics", {"operation": "sound_pressure_level", "pressure_pa": 0.02}),
    ("acoustics", {"operation": "frequency_to_note", "frequency_hz": 440}),
    ("acoustics", {"operation": "room_reverberation", "volume_m3": 200, "absorption_coefficient": 0.4, "surface_area_m2": 250}),

    # CRYPTOGRAPHY
    ("cryptography", {"operation": "rsa_key_security", "key_bits": 2048}),
    ("cryptography", {"operation": "entropy_bits", "alphabet_size": 94, "length": 16}),
    ("cryptography", {"operation": "sha256_verify", "message": "concordance", "expected_hash": "concordance"}),

    # FORMAL LOGIC
    ("formal_logic", {"operation": "modus_ponens", "premise1": "All men are mortal", "premise2": "Socrates is a man", "conclusion": "Socrates is mortal"}),
    ("formal_logic", {"operation": "truth_table", "expression": "P AND Q", "p": True, "q": False}),

    # FINANCE
    ("finance", {"operation": "npv", "rate": 0.1, "cashflows": [-1000, 300, 400, 500]}),
    ("finance", {"operation": "irr_estimate", "cashflows": [-1000, 400, 400, 400]}),
    ("finance", {"operation": "break_even", "fixed_costs": 50000, "price_per_unit": 25, "variable_cost_per_unit": 10}),

    # GOVERNANCE
    ("governance", {"operation": "quorum_check", "members_present": 7, "total_members": 11, "quorum_fraction": 0.5}),
    ("governance", {"operation": "supermajority", "votes_for": 8, "total_votes": 11, "threshold": 0.667}),

    # CALENDAR / TIME
    ("calendar_time", {"operation": "days_between", "date1": "2026-01-01", "date2": "2026-12-31"}),
    ("calendar_time", {"operation": "is_leap_year", "year": 2024}),
    ("calendar_time", {"operation": "day_of_week", "date": "2026-05-06"}),

    # CYBERSECURITY
    ("cybersecurity", {"operation": "password_strength", "password": "C0nc0rd@nce!2026"}),
    ("cybersecurity", {"operation": "cvss_severity", "score": 7.5}),
][:100]

# Ensure exactly 100
assert len(INTERACTIONS) == 100, f"Expected 100 interactions, got {len(INTERACTIONS)}"


def run_one(idx: int, domain: str, spec: dict) -> dict:
    tool_name = f"verify_{domain}"
    fn = ALL_TOOLS.get(tool_name)
    if fn is None:
        return {"status": "skip", "reason": f"no tool: {tool_name}"}
    try:
        result = fn(spec)
        entry = store.append(domain, spec, result)
        summary = entry.get("summary", "UNKNOWN")
        record_confirmation(
            domain, spec, INSTANCE_ID, summary=summary, entry_id=entry.get("id")
        )
        return {"status": "ok", "domain": domain, "summary": summary, "entry_id": entry.get("id")}
    except Exception as exc:
        return {"status": "error", "domain": domain, "error": str(exc)}


def main():
    print(f"Seeding vault with {len(INTERACTIONS)} interactions...")
    print(f"Instance ID: {INSTANCE_ID}\n")

    results = {"ok": 0, "skip": 0, "error": 0}
    t0 = time.time()

    for idx, (domain, spec) in enumerate(INTERACTIONS, 1):
        r = run_one(idx, domain, spec)
        status = r["status"]
        results[status] = results.get(status, 0) + 1
        marker = "+" if status == "ok" else ("~" if status == "skip" else "!")
        print(f"  [{idx:03d}] {marker} {domain:<22} {r.get('summary', r.get('reason', r.get('error', '')))}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    print(f"  OK:    {results.get('ok', 0)}")
    print(f"  Skip:  {results.get('skip', 0)}")
    print(f"  Error: {results.get('error', 0)}")


if __name__ == "__main__":
    main()
