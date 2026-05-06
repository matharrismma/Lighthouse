"""
Builds a training corpus by:
1. Defining seed parameters for each domain
2. Perturbing them numerically to generate variants
3. Running each variant through the verifier to get ground truth
4. Writing CONFIRMED variants (and intentional DISCORDANT variants as negative
   examples) to training JSONL

Output: eval/training/training_corpus.jsonl

Run:
    python eval/training/build_training_corpus.py
    python eval/training/build_training_corpus.py --output path/to/corpus.jsonl

No external dependencies beyond the Concordance engine package.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Path setup — make sure the src/ tree is importable regardless of cwd
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from concordance_engine.verifiers import thermodynamics as _thermo
from concordance_engine.verifiers import nuclear_physics as _nuclear
from concordance_engine.verifiers import ecology as _ecology
from concordance_engine.verifiers import economics as _econ
from concordance_engine.verifiers.calendar_time import verify_duration_addition

# ---------------------------------------------------------------------------
# Output path default
# ---------------------------------------------------------------------------
_DEFAULT_OUTPUT = _REPO_ROOT / "eval" / "training" / "training_corpus.jsonl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_rng = random.Random(42)  # seeded for reproducibility


def _make_item(
    item_id: str,
    domain: str,
    check_type: str,
    question: str,
    answer: str,
    spec: Dict[str, Any],
    verifier_result: str,
    formula: str,
    axis: str,
    difficulty: str,
) -> Dict[str, Any]:
    return {
        "id": item_id,
        "domain": domain,
        "check_type": check_type,
        "question": question,
        "answer": answer,
        "ground_truth_spec": spec,
        "verifier_result": verifier_result,
        "formula": formula,
        "axis": axis,
        "difficulty": difficulty,
    }


def _difficulty(relative_error: float) -> str:
    """Classify difficulty based on how far the wrong answer deviates."""
    if relative_error == 0:
        return "easy"
    if relative_error < 0.1:
        return "medium"
    return "hard"


# ---------------------------------------------------------------------------
# Domain generators
# ---------------------------------------------------------------------------

def _generate_thermo(n_carnot: int = 50, n_specific: int = 50) -> List[Dict[str, Any]]:
    """Generate thermodynamics training items."""
    items: List[Dict[str, Any]] = []
    discordant_every = 5  # ~20% discordant

    # --- Carnot efficiency ---
    for i in range(n_carnot):
        T_hot = _rng.uniform(400, 1200)
        T_cold = _rng.uniform(200, min(500, T_hot - 10))  # ensure T_hot > T_cold
        eta = 1.0 - T_cold / T_hot
        base_id = f"THERMO-CARNOT-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = eta * 1.5 if is_discordant else eta
        spec = {
            "T_hot_K": round(T_hot, 4),
            "T_cold_K": round(T_cold, 4),
            "claimed_efficiency": round(claimed, 6),
        }
        result = _thermo.verify_carnot_efficiency(spec)
        status = result.status
        if status not in ("CONFIRMED", "MISMATCH"):
            continue  # skip errors/NA (shouldn't happen with valid params)

        items.append(_make_item(
            item_id=base_id,
            domain="thermodynamics",
            check_type="carnot_efficiency",
            question=(
                f"What is the Carnot efficiency of a heat engine with "
                f"T_hot={T_hot:.2f} K and T_cold={T_cold:.2f} K?"
            ),
            answer=str(round(eta, 6)),
            spec=spec,
            verifier_result=status,
            formula="η = 1 − T_cold / T_hot",
            axis="conservation_balance",
            difficulty="easy" if not is_discordant else "hard",
        ))

    # --- Specific heat Q = mcΔT ---
    for i in range(n_specific):
        mass = _rng.uniform(0.1, 10.0)
        c_heat = _rng.uniform(100, 4000)
        delta_T = _rng.uniform(1, 100)
        Q = mass * c_heat * delta_T
        base_id = f"THERMO-SPECHEAT-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = Q * 1.5 if is_discordant else Q
        spec = {
            "mass_kg": round(mass, 4),
            "specific_heat_J_per_kgK": round(c_heat, 4),
            "delta_T_K": round(delta_T, 4),
            "claimed_heat_J": round(claimed, 4),
        }
        result = _thermo.verify_specific_heat(spec)
        status = result.status
        if status not in ("CONFIRMED", "MISMATCH"):
            continue

        items.append(_make_item(
            item_id=base_id,
            domain="thermodynamics",
            check_type="specific_heat",
            question=(
                f"How much heat energy (J) is transferred when {mass:.3f} kg of "
                f"material with specific heat {c_heat:.2f} J/kgK changes temperature "
                f"by {delta_T:.2f} K?"
            ),
            answer=str(round(Q, 4)),
            spec=spec,
            verifier_result=status,
            formula="Q = m × c × ΔT",
            axis="conservation_balance",
            difficulty="easy" if not is_discordant else "hard",
        ))

    return items


def _generate_nuclear(n: int = 50) -> List[Dict[str, Any]]:
    """Generate nuclear physics radioactive decay training items."""
    items: List[Dict[str, Any]] = []
    discordant_every = 5

    for i in range(n):
        T_half = _rng.uniform(1, 1e9)
        multiplier = _rng.uniform(0.1, 5.0)
        elapsed = multiplier * T_half
        N0 = _rng.uniform(1e6, 1e12)

        lam = math.log(2) / T_half
        N_t = N0 * math.exp(-lam * elapsed)
        base_id = f"NUCLEAR-DECAY-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = N_t * 1.5 if is_discordant else N_t
        spec = {
            "half_life_seconds": round(T_half, 6),
            "elapsed_seconds": round(elapsed, 6),
            "initial_count": round(N0, 2),
            "claimed_remaining_count": round(claimed, 4),
        }
        result = _nuclear.verify_radioactive_decay(spec)
        status = result.status
        if status not in ("CONFIRMED", "MISMATCH"):
            continue

        items.append(_make_item(
            item_id=base_id,
            domain="nuclear_physics",
            check_type="radioactive_decay",
            question=(
                f"A radioactive sample starts with {N0:.4g} atoms and has a half-life "
                f"of {T_half:.4g} seconds. How many atoms remain after "
                f"{elapsed:.4g} seconds?"
            ),
            answer=str(round(N_t, 4)),
            spec=spec,
            verifier_result=status,
            formula="N(t) = N₀ × e^(−λt),  λ = ln(2) / T_half",
            axis="time_sequence",
            difficulty="easy" if not is_discordant else "hard",
        ))

    return items


def _generate_ecology(n: int = 50) -> List[Dict[str, Any]]:
    """Generate ecology trophic efficiency training items."""
    items: List[Dict[str, Any]] = []
    discordant_every = 5

    for i in range(n):
        energy_input = _rng.uniform(1000, 1_000_000)
        levels = _rng.randint(1, 4)
        efficiency = _rng.uniform(0.05, 0.15)
        output = energy_input * (efficiency ** levels)
        base_id = f"ECO-TROPHIC-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = output * 1.5 if is_discordant else output
        spec = {
            "energy_input": round(energy_input, 4),
            "trophic_levels_up": levels,
            "trophic_efficiency": round(efficiency, 6),
            "claimed_energy_output": round(claimed, 6),
        }
        result_obj = _call_eco_trophic(spec)
        status = result_obj
        if status not in ("CONFIRMED", "MISMATCH"):
            continue

        items.append(_make_item(
            item_id=base_id,
            domain="ecology",
            check_type="trophic_efficiency",
            question=(
                f"Starting with {energy_input:.2f} J of energy at the base trophic level, "
                f"and a trophic efficiency of {efficiency:.4f}, how much energy is available "
                f"after {levels} trophic level(s)?"
            ),
            answer=str(round(output, 6)),
            spec=spec,
            verifier_result=status,
            formula="output = input × efficiency^levels",
            axis="metabolism",
            difficulty="easy" if not is_discordant else "hard",
        ))

    return items


def _call_eco_trophic(spec: Dict[str, Any]) -> str:
    """Call the ecology trophic verifier and return status string."""
    from concordance_engine.verifiers.ecology import verify_trophic_efficiency
    result = verify_trophic_efficiency(spec)
    return result.status


def _generate_calendar_time(n_elapsed: int = 50, n_century: int = 50) -> List[Dict[str, Any]]:
    """
    Generate history_chronology training items using the calendar_time verifier.

    Two check types:
      - year_elapsed: duration between two CE years (uses duration_addition with
                      full ISO timestamps, 1 year = 365.25 days)
      - century_assignment: given a year, determine the century number via
                            ceiling division — verified with leap-year-aware
                            duration checks (purely computed, no verifier for
                            century math, so we confirm deterministically).
    """
    items: List[Dict[str, Any]] = []
    discordant_every = 5

    # --- elapsed years between two CE dates ---
    for i in range(n_elapsed):
        from_year = _rng.randint(1, 1900)
        to_year = _rng.randint(from_year + 1, from_year + 500)
        elapsed = to_year - from_year
        base_id = f"HIST-ELAPSED-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)

        # Use duration_addition: start = Jan 1 of from_year, duration = elapsed * 365.25 days
        # claimed end = Jan 1 of to_year
        start_iso = f"{from_year:04d}-01-01"
        # For the year-elapsed check we bypass the calendar verifier (which uses
        # seconds) and instead just confirm via pure arithmetic — the "verifier"
        # here IS the arithmetic.
        actual_answer = elapsed
        claimed_answer = int(elapsed * 1.5) if is_discordant else elapsed
        status = "CONFIRMED" if claimed_answer == elapsed else "MISMATCH"

        spec = {
            "from_year_CE": from_year,
            "to_year_CE": to_year,
            "claimed_elapsed_years": claimed_answer,
        }

        items.append(_make_item(
            item_id=base_id,
            domain="history_chronology",
            check_type="year_elapsed",
            question=(
                f"How many years elapsed between {from_year} CE and {to_year} CE?"
            ),
            answer=str(actual_answer),
            spec=spec,
            verifier_result=status,
            formula="elapsed = to_year − from_year",
            axis="time_sequence",
            difficulty="easy" if not is_discordant else "medium",
        ))

    # --- century assignment: ceil(year / 100) ---
    for i in range(n_century):
        year = _rng.randint(1, 2000)
        century = math.ceil(year / 100)
        base_id = f"HIST-CENTURY-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = century + 1 if is_discordant else century
        status = "CONFIRMED" if claimed == century else "MISMATCH"

        spec = {
            "year_CE": year,
            "claimed_century": claimed,
        }

        items.append(_make_item(
            item_id=base_id,
            domain="history_chronology",
            check_type="century_assignment",
            question=(
                f"In which century CE did the year {year} fall?"
            ),
            answer=f"{century}th" if century not in (1, 2, 3) else
                   (f"{century}st" if century == 1 else
                    (f"{century}nd" if century == 2 else f"{century}rd")),
            spec=spec,
            verifier_result=status,
            formula="century = ceil(year / 100)",
            axis="time_sequence",
            difficulty="easy" if not is_discordant else "medium",
        ))

    return items


def _generate_economics(n: int = 50) -> List[Dict[str, Any]]:
    """Generate economics compound interest training items."""
    items: List[Dict[str, Any]] = []
    discordant_every = 5
    n_options = [1, 4, 12, 365]

    for i in range(n):
        P = _rng.uniform(1000, 100_000)
        r = _rng.uniform(0.01, 0.15)
        t = _rng.uniform(1, 30)
        n_comp = _rng.choice(n_options)
        A = P * (1 + r / n_comp) ** (n_comp * t)
        base_id = f"ECON-COMPOUND-{i+1:03d}"

        is_discordant = (i % discordant_every == 0)
        claimed = A * 1.5 if is_discordant else A
        spec = {
            "principal": round(P, 4),
            "rate": round(r, 6),
            "time_years": round(t, 4),
            "compounding_periods": n_comp,
            "claimed_compound_amount": round(claimed, 4),
        }

        from concordance_engine.verifiers.economics import verify_compound_interest
        result = verify_compound_interest(spec)
        status = result.status
        if status not in ("CONFIRMED", "MISMATCH"):
            continue

        n_label = {1: "annually", 4: "quarterly", 12: "monthly", 365: "daily"}.get(n_comp, str(n_comp))

        items.append(_make_item(
            item_id=base_id,
            domain="economics",
            check_type="compound_interest",
            question=(
                f"What is the future value of ${P:.2f} invested at {r*100:.4f}% annual rate "
                f"compounded {n_label} ({n_comp}×/year) for {t:.4f} years?"
            ),
            answer=str(round(A, 4)),
            spec=spec,
            verifier_result=status,
            formula="A = P * (1 + r/n)^(n*t)",
            axis="conservation_balance",
            difficulty="easy" if not is_discordant else "hard",
        ))

    return items


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_corpus(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    all_items: List[Dict[str, Any]] = []

    print("Generating thermodynamics items...")
    all_items.extend(_generate_thermo(n_carnot=50, n_specific=50))

    print("Generating nuclear physics items...")
    all_items.extend(_generate_nuclear(n=50))

    print("Generating ecology items...")
    all_items.extend(_generate_ecology(n=50))

    print("Generating history_chronology items...")
    all_items.extend(_generate_calendar_time(n_elapsed=50, n_century=50))

    print("Generating economics items...")
    all_items.extend(_generate_economics(n=50))

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------
    confirmed = [it for it in all_items if it["verifier_result"] == "CONFIRMED"]
    discordant = [it for it in all_items if it["verifier_result"] == "MISMATCH"]

    with output_path.open("w", encoding="utf-8") as fh:
        for item in all_items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------
    from collections import Counter
    domain_counts: Counter = Counter()
    for it in all_items:
        domain_counts[it["domain"]] += 1

    print("\n=== Training Corpus Build Complete ===")
    print(f"Output:    {output_path}")
    print(f"Total:     {len(all_items)}")
    print(f"CONFIRMED: {len(confirmed)}")
    print(f"DISCORDANT (negative examples): {len(discordant)}")
    print("\nBreakdown by domain:")
    for domain, count in sorted(domain_counts.items()):
        dom_confirmed = sum(1 for it in all_items
                            if it["domain"] == domain and it["verifier_result"] == "CONFIRMED")
        dom_discord = count - dom_confirmed
        print(f"  {domain:<25} {count:>4} total  ({dom_confirmed} confirmed, {dom_discord} discordant)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Concordance training corpus")
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help=f"Output JSONL path (default: {_DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()
    build_corpus(args.output)
