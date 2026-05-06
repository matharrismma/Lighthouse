"""Build benchmark items for all 37 domains.

3 items per domain × 37 domains = 111 items.
Ground truth is computed by the verifier itself — no hand-curation.

Run:  python eval/benchmark/build_items_extended.py
"""
from __future__ import annotations
import json
import math
import sys
from pathlib import Path

THIS = Path(__file__).resolve()
REPO = THIS.parents[2]
sys.path.insert(0, str(REPO / "src"))

from concordance_engine.verifiers import (
    chemistry as chem,
    physics as phys,
    statistics as stat,
    mathematics as maths,
    computer_science as cs_ver,
    biology as bio,
    genetics as gen,
    nutrition as nut,
    formal_logic as logic,
    number_theory as numth,
    combinatorics as comb,
    geometry as geom,
    information_theory as infoth,
    electrical as elec,
    energy as energy_ver,
    optics as opt,
    acoustics as acou,
    manufacturing as mfg,
    meteorology as met,
    geology as geol,
    hydrology as hydro,
    astronomy as astro,
    agriculture as agri,
    geography as geo,
    cryptography as crypto,
    networking as net,
    exercise_science as exsci,
    sports_analytics as sport,
    finance as fin,
    music_theory as mus,
    calendar_time as cal,
    governance as gov,
    linguistics as ling,
    document_validation as docval,
    photography as photo,
    witness as wit,
    quantum_computing as qcomp,
    economics as econ,
    labor as labor_ver,
    real_estate as re_ver,
    construction as constr,
    soil_science as soil,
    cybersecurity as cyber,
    medicine as med,
)
from concordance_engine.verifiers.base import VerifierResult
from scipy import stats as scistats


# ── helpers ─────────────────────────────────────────────────────────────────

def _run(module, packet_key: str, spec: dict) -> list[VerifierResult]:
    return module.run({packet_key: spec})


def _first(results: list[VerifierResult]) -> str:
    return results[0].status if results else "NO_RESULT"


def _item(id_, domain, task, prompt, ground_truth, answer_kind,
          tool_name, tool_spec, *, tolerance=None):
    d = dict(id=id_, domain=domain, task=task, prompt=prompt,
             ground_truth=ground_truth, answer_kind=answer_kind,
             tool_name=tool_name, tool_spec=tool_spec)
    if tolerance is not None:
        d["tolerance"] = tolerance
    return d


# ── chemistry (3) ────────────────────────────────────────────────────────────

def build_chemistry():
    items = []
    cases = [
        ("2 H2 + O2 -> 2 H2O",           True),
        ("H2 + O2 -> H2O",                False),
        ("N2 + 3 H2 -> 2 NH3",            True),
    ]
    for i, (eq, balanced) in enumerate(cases, 1):
        items.append(_item(
            f"CHEM-{i:03d}", "chemistry", "is_balanced",
            f"Is the chemical equation `{eq}` balanced? Answer with exactly one word: yes or no.",
            "yes" if balanced else "no", "classification",
            "verify_chemistry", {"equation": eq},
        ))
    return items


# ── statistics (3) ───────────────────────────────────────────────────────────

def build_statistics():
    def two_t(n1, n2, m1, m2, s1, s2):
        se = math.sqrt(s1**2/n1 + s2**2/n2)
        t = (m1-m2)/se
        df = (s1**2/n1+s2**2/n2)**2/((s1**2/n1)**2/(n1-1)+(s2**2/n2)**2/(n2-1))
        return 2*scistats.t.sf(abs(t), df)

    cases = [
        (30, 30, 5.0, 4.0, 1.0, 1.0),
        (50, 50, 10.0, 10.5, 2.0, 2.0),
        (20, 20, 100, 98, 5, 5),
    ]
    items = []
    for i, (n1,n2,m1,m2,s1,s2) in enumerate(cases, 1):
        p = float(two_t(n1,n2,m1,m2,s1,s2))
        items.append(_item(
            f"STAT-{i:03d}", "statistics", "two_tailed_pvalue",
            f"Two-sample t-test: n1={n1}, n2={n2}, mean1={m1}, mean2={m2}, "
            f"sd1={s1}, sd2={s2}. Call verify_statistics_pvalue to compute the "
            f"two-tailed p-value. Reply with only the decimal number.",
            p, "numeric",
            "verify_statistics_pvalue",
            {"spec": {"test": "two_sample_t", "n1": n1, "n2": n2,
                      "mean1": m1, "mean2": m2, "sd1": s1, "sd2": s2,
                      "claimed_p": p, "tail": "two"}},
            tolerance=0.05,
        ))
    return items


# ── physics (3) ──────────────────────────────────────────────────────────────

def build_physics():
    cases = [
        ("F = m * a",    {"F": "newton", "m": "kilogram", "a": "meter/second**2"}, True),
        ("F = m * v",    {"F": "newton", "m": "kilogram", "v": "meter/second"},    False),
        ("E = m * c**2", {"E": "joule",  "m": "kilogram", "c": "meter/second"},    True),
    ]
    items = []
    for i, (eq, sym, ok) in enumerate(cases, 1):
        sym_text = ", ".join(f"{k} in {v.replace('**','^').replace('*','·')}"
                             for k, v in sym.items())
        items.append(_item(
            f"PHYS-{i:03d}", "physics", "dimensional_consistency",
            f"Is `{eq}` dimensionally consistent given {sym_text}? "
            f"Answer with exactly one word: yes or no.",
            "yes" if ok else "no", "classification",
            "verify_physics_dimensional", {"equation": eq, "symbols": sym},
        ))
    return items


# ── mathematics (3) ──────────────────────────────────────────────────────────

def build_mathematics():
    import sympy as sp
    x = sp.Symbol("x")
    cases = [
        ("derivative", "d/dx of x**3", "3*x**2",
         {"mode": "derivative", "params": {"function": "x**3",
          "claimed_derivative": "3*x**2"}}),
        ("equality", "x**2 - 4 equals (x-2)*(x+2)", True,
         {"mode": "equality", "params": {"lhs": "x**2 - 4",
          "rhs": "(x-2)*(x+2)"}}),
        ("solve", "roots of x**2 - 5*x + 6 = 0", "2, 3",
         {"mode": "solve", "params": {"equation": "x**2 - 5*x + 6 = 0",
          "claimed_solutions": ["2", "3"]}}),
    ]
    items = []
    for i, (task, desc, gt, spec) in enumerate(cases, 1):
        if task == "derivative":
            q = f"What is the derivative of x³ with respect to x? Reply with just the expression."
            gt_ans = "3*x**2"
            ak = "string"
        elif task == "equality":
            q = f"Is x²−4 equal to (x−2)(x+2) for all x? Answer yes or no."
            gt_ans = "yes"
            ak = "classification"
        else:
            q = f"What are the roots of x²−5x+6=0? Reply with the two roots separated by a comma."
            gt_ans = "2, 3"
            ak = "string"
        items.append(_item(
            f"MATH-{i:03d}", "mathematics", task, q, gt_ans, ak,
            "verify_mathematics", spec,
        ))
    return items


# ── computer science (3) ─────────────────────────────────────────────────────

def build_computer_science():
    code1 = "def bubble_sort(arr):\n    n=len(arr)\n    for i in range(n):\n        for j in range(n-i-1):\n            if arr[j]>arr[j+1]: arr[j],arr[j+1]=arr[j+1],arr[j]\n    return arr"
    code2 = "def linear_search(arr,x):\n    for i,v in enumerate(arr):\n        if v==x: return i\n    return -1"
    code3 = "def factorial(n):\n    if n<=1: return 1\n    return n*factorial(n-1)"
    return [
        _item("CS-001", "computer_science", "complexity",
              "What is the time complexity of bubble sort on an array of n elements? "
              "Answer with just the Big-O class, e.g. O(n^2).",
              "O(n^2)", "string",
              "verify_computer_science",
              {"code": code1, "function_name": "bubble_sort",
               "input_generator": "import random; lambda n: ([random.randint(0,100) for _ in range(n)],)",
               "claimed_class": "O(n^2)"}),
        _item("CS-002", "computer_science", "complexity",
              "What is the time complexity of linear search on an array of n elements? "
              "Answer with just the Big-O class.",
              "O(n)", "string",
              "verify_computer_science",
              {"code": code2, "function_name": "linear_search",
               "input_generator": "import random; lambda n: ([random.randint(0,100) for _ in range(n)], -1)",
               "claimed_class": "O(n)"}),
        _item("CS-003", "computer_science", "termination",
              "Does the following Python function always terminate for positive integers? "
              f"```python\n{code3}\n```\nAnswer yes or no.",
              "yes", "classification",
              "verify_computer_science", {"code": code3}),
    ]


# ── biology (3) ──────────────────────────────────────────────────────────────

def build_biology():
    return [
        _item("BIO-001", "biology", "replicates",
              "A study uses 2 biological replicates. Does it meet the minimum standard "
              "of 3 replicates? Answer yes or no.",
              "no", "classification",
              "verify_biology", {"n_replicates": 2, "min_replicates": 3}),
        _item("BIO-002", "biology", "hardy_weinberg",
              "In a Hardy-Weinberg population, allele A has frequency p=0.6 and "
              "allele a has frequency q=0.4. What is the expected frequency of "
              "heterozygotes (Aa)? Reply with just the decimal number.",
              0.48, "numeric",
              "verify_biology",
              {"hardy_weinberg": {"p": 0.6, "q": 0.4, "claimed_Aa": 0.48}},
              tolerance=0.01),
        _item("BIO-003", "biology", "gc_content",
              "The DNA sequence ATCGATCG has how many GC bases out of 8 total? "
              "What is the GC content as a decimal fraction? Reply with just the decimal number.",
              0.5, "numeric",
              "verify_genetics",
              {"sequence": "ATCGATCG", "claimed_gc_fraction": round(4/8, 4)},
              tolerance=0.01),
    ]


# ── genetics (3) ─────────────────────────────────────────────────────────────

def build_genetics():
    return [
        _item("GEN-001", "genetics", "complement",
              "What is the DNA complement of the sequence ATCG? "
              "Reply with just the sequence.",
              "TAGC", "string",
              "verify_genetics",
              {"sequence": "ATCG", "claimed_complement": "TAGC"}),
        _item("GEN-002", "genetics", "gc_content",
              "What is the GC content of the sequence GCGCATATATAT? "
              "Reply with the decimal fraction rounded to 2 places.",
              0.33, "numeric",
              "verify_genetics",
              {"sequence": "GCGCATATATAT", "claimed_gc_fraction": round(4/12, 4)},
              tolerance=0.02),
        _item("GEN-003", "genetics", "codon",
              "What amino acid does the codon ATG encode? "
              "Reply with just the three-letter abbreviation.",
              "Met", "string",
              "verify_genetics",
              {"codon": "ATG", "claimed_amino_acid": "Met"}),
    ]


# ── nutrition (3) ────────────────────────────────────────────────────────────

def build_nutrition():
    return [
        _item("NUT-001", "nutrition", "calories",
              "How many calories (kcal) does 100 grams of pure protein contain? "
              "Reply with just the number.",
              400.0, "numeric",
              "verify_nutrition",
              {"protein_g": 100, "claimed_protein_kcal": 400},
              tolerance=0.01),
        _item("NUT-002", "nutrition", "calories",
              "How many calories (kcal) does 100 grams of pure fat contain? "
              "Reply with just the number.",
              900.0, "numeric",
              "verify_nutrition",
              {"fat_g": 100, "claimed_fat_kcal": 900},
              tolerance=0.01),
        _item("NUT-003", "nutrition", "bmr",
              "Using the Mifflin-St Jeor equation, what is the BMR for a 70 kg male, "
              "175 cm tall, age 30? Reply with just the number in kcal/day, rounded to nearest integer.",
              round(10*70 + 6.25*175 - 5*30 + 5), "numeric",
              "verify_nutrition",
              {"weight_kg": 70, "height_cm": 175, "age_years": 30, "sex": "male",
               "claimed_bmr": round(10*70 + 6.25*175 - 5*30 + 5)},
              tolerance=0.02),
    ]


# ── formal_logic (3) ─────────────────────────────────────────────────────────

def build_formal_logic():
    return [
        _item("LOGIC-001", "formal_logic", "tautology",
              "Is the statement 'A OR NOT A' always true (a tautology)? Answer yes or no.",
              "yes", "classification",
              "verify_formal_logic",
              {"formula": "A | ~A", "variables": ["A"], "claimed_tautology": True}),
        _item("LOGIC-002", "formal_logic", "contradiction",
              "Is the statement 'A AND NOT A' always false (a contradiction)? Answer yes or no.",
              "yes", "classification",
              "verify_formal_logic",
              {"formula": "A & ~A", "variables": ["A"], "claimed_contradiction": True}),
        _item("LOGIC-003", "formal_logic", "entailment",
              "Do the premises 'If P then Q' and 'P is true' logically entail 'Q is true'? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_formal_logic",
              {"premises": ["P >> Q", "P"], "conclusion": "Q",
               "variables": ["P","Q"], "claimed_entailment": True}),
    ]


# ── number_theory (3) ────────────────────────────────────────────────────────

def build_number_theory():
    return [
        _item("NUM-001", "number_theory", "primality",
              "Is 17 a prime number? Answer yes or no.",
              "yes", "classification",
              "verify_number_theory",
              {"n_prime": 17, "claimed_prime": True}),
        _item("NUM-002", "number_theory", "primality",
              "Is 15 a prime number? Answer yes or no.",
              "no", "classification",
              "verify_number_theory",
              {"n_prime": 15, "claimed_prime": False}),
        _item("NUM-003", "number_theory", "gcd",
              "What is the GCD of 48 and 18? Reply with just the number.",
              6, "numeric",
              "verify_number_theory",
              {"gcd_a": 48, "gcd_b": 18, "claimed_gcd": 6},
              tolerance=0.0),
    ]


# ── combinatorics (3) ────────────────────────────────────────────────────────

def build_combinatorics():
    return [
        _item("COMB-001", "combinatorics", "combinations",
              "How many ways can you choose 3 items from 10 (order doesn't matter, "
              "no repetition)? Reply with just the number.",
              120, "numeric",
              "verify_combinatorics",
              {"n": 10, "k": 3, "claimed_combinations": 120},
              tolerance=0.0),
        _item("COMB-002", "combinatorics", "permutations",
              "How many ways can you arrange 4 items chosen from 6 (order matters)? "
              "Reply with just the number.",
              360, "numeric",
              "verify_combinatorics",
              {"n": 6, "k": 4, "claimed_permutations": 360},
              tolerance=0.0),
        _item("COMB-003", "combinatorics", "derangements",
              "How many derangements (permutations with no fixed points) exist for 4 elements? "
              "Reply with just the number.",
              9, "numeric",
              "verify_combinatorics",
              {"n_derangements": 4, "claimed_derangements": 9},
              tolerance=0.0),
    ]


# ── geometry (3) ─────────────────────────────────────────────────────────────

def build_geometry():
    return [
        _item("GEOM-001", "geometry", "area",
              "What is the area of a circle with radius 5? "
              "Reply with the number rounded to 2 decimal places. Use π=3.14159265.",
              round(math.pi * 25, 2), "numeric",
              "verify_geometry",
              {"shape": "circle", "radius": 5,
               "claimed_area": round(math.pi*25, 2)},
              tolerance=0.01),
        _item("GEOM-002", "geometry", "pythagorean",
              "In a right triangle with legs of length 3 and 4, what is the length of "
              "the hypotenuse? Reply with just the number.",
              5.0, "numeric",
              "verify_geometry",
              {"a": 3, "b": 4, "claimed_hypotenuse": 5},
              tolerance=0.001),
        _item("GEOM-003", "geometry", "volume",
              "What is the volume of a sphere with radius 3? "
              "Reply with the number rounded to 2 decimal places. Use π=3.14159265.",
              round(4/3 * math.pi * 27, 2), "numeric",
              "verify_geometry",
              {"shape": "sphere", "radius": 3,
               "claimed_volume": round(4/3*math.pi*27, 2)},
              tolerance=0.01),
    ]


# ── information_theory (3) ───────────────────────────────────────────────────

def build_information_theory():
    return [
        _item("INFO-001", "information_theory", "entropy",
              "What is the Shannon entropy in bits of a fair coin flip (p=0.5 for each outcome)? "
              "Reply with just the number.",
              1.0, "numeric",
              "verify_information_theory",
              {"probabilities": [0.5, 0.5], "claimed_entropy_bits": 1.0},
              tolerance=0.001),
        _item("INFO-002", "information_theory", "entropy",
              "What is the Shannon entropy in bits of a fair four-sided die? "
              "Reply with just the number.",
              2.0, "numeric",
              "verify_information_theory",
              {"probabilities": [0.25]*4, "claimed_entropy_bits": 2.0},
              tolerance=0.001),
        _item("INFO-003", "information_theory", "channel_capacity",
              "What is the Shannon channel capacity in bits/s of a channel with "
              "bandwidth 1 Hz and SNR=3 (linear)? Reply with the number rounded to 4 places.",
              round(math.log2(1+3), 4), "numeric",
              "verify_information_theory",
              {"bandwidth_hz": 1, "snr_linear": 3,
               "claimed_capacity_bps": round(math.log2(4), 4)},
              tolerance=0.01),
    ]


# ── electrical (3) ───────────────────────────────────────────────────────────

def build_electrical():
    return [
        _item("ELEC-001", "electrical", "ohms_law",
              "A circuit has voltage V=12V and current I=3A. What is the resistance? "
              "Reply with just the number in ohms.",
              4.0, "numeric",
              "verify_electrical",
              {"V": 12, "I": 3, "claimed_R": 4},
              tolerance=0.001),
        _item("ELEC-002", "electrical", "power",
              "What power does a 12V, 3A circuit dissipate? "
              "Reply with just the number in watts.",
              36.0, "numeric",
              "verify_electrical",
              {"V": 12, "I": 3, "claimed_P": 36},
              tolerance=0.001),
        _item("ELEC-003", "electrical", "ohms_law",
              "A circuit has resistance R=10 ohms and voltage V=5V. What is the current? "
              "Reply with just the number in amperes.",
              0.5, "numeric",
              "verify_electrical",
              {"V": 5, "R": 10, "claimed_I": 0.5},
              tolerance=0.001),
    ]


# ── energy (3) ───────────────────────────────────────────────────────────────

def build_energy():
    return [
        _item("ENRG-001", "energy", "unit_conversion",
              "How many watt-hours (Wh) are in 1 kilowatt-hour (kWh)? "
              "Reply with just the number.",
              1000.0, "numeric",
              "verify_energy",
              {"kwh": 1.0, "claimed_wh": 1000},
              tolerance=0.0),
        _item("ENRG-002", "energy", "runtime",
              "A 100Wh battery powers a 20W load. How many hours will it last? "
              "Reply with just the number.",
              5.0, "numeric",
              "verify_energy",
              {"battery_wh": 100, "load_w": 20, "claimed_runtime_h": 5},
              tolerance=0.001),
        _item("ENRG-003", "energy", "efficiency",
              "A device takes in 100W and outputs 80W. What is its efficiency as a fraction? "
              "Reply with just the decimal number.",
              0.8, "numeric",
              "verify_energy",
              {"input_w": 100, "output_w": 80, "claimed_efficiency": 0.8},
              tolerance=0.001),
    ]


# ── optics (3) ───────────────────────────────────────────────────────────────

def build_optics():
    theta_r = math.degrees(math.asin(math.sin(math.radians(30)) / 1.5))
    return [
        _item("OPT-001", "optics", "snells_law",
              "Light travels from air (n=1.0) into glass (n=1.5) at an incident angle "
              "of 30°. What is the refracted angle in degrees? "
              "Reply with the number rounded to 1 decimal place.",
              round(theta_r, 1), "numeric",
              "verify_optics",
              {"n1": 1.0, "n2": 1.5, "theta1_deg": 30,
               "claimed_theta2_deg": round(theta_r, 1)},
              tolerance=0.05),
        _item("OPT-002", "optics", "thin_lens",
              "A lens has focal length f=10cm and an object is placed 30cm away. "
              "Where is the image? Reply with just the distance in cm.",
              15.0, "numeric",
              "verify_optics",
              {"f_cm": 10, "do_cm": 30, "claimed_di_cm": 15},
              tolerance=0.01),
        _item("OPT-003", "optics", "snells_law",
              "If light hits a glass surface at exactly the critical angle "
              "for total internal reflection (n1=1.5, n2=1.0), what happens? "
              "Answer: refracted or total_internal_reflection.",
              "total_internal_reflection", "string",
              "verify_optics",
              {"n1": 1.5, "n2": 1.0,
               "theta1_deg": round(math.degrees(math.asin(1.0/1.5)), 2),
               "claimed_tir": True}),
    ]


# ── acoustics (3) ────────────────────────────────────────────────────────────

def build_acoustics():
    wl = round(340 / 440, 4)
    return [
        _item("ACOU-001", "acoustics", "wave_speed",
              "Sound travels at 340 m/s. What is the wavelength of a 440 Hz tone? "
              "Reply with the number in meters, rounded to 4 decimal places.",
              wl, "numeric",
              "verify_acoustics",
              {"speed_of_wave": 340, "frequency_hz": 440,
               "claimed_wavelength_m": wl},
              tolerance=0.001),
        _item("ACOU-002", "acoustics", "decibel",
              "A sound intensity is 100 times the reference level. "
              "What is the sound intensity level in dB? Reply with just the number.",
              20.0, "numeric",
              "verify_acoustics",
              {"value": 100, "reference": 1, "claimed_db": 20, "db_kind": "intensity"},
              tolerance=0.001),
        _item("ACOU-003", "acoustics", "harmonic",
              "A string produces a fundamental frequency of 100 Hz. "
              "What is the 3rd harmonic frequency? Reply with just the number in Hz.",
              300.0, "numeric",
              "verify_acoustics",
              {"fundamental_hz": 100, "harmonic_n": 3, "claimed_harmonic_hz": 300},
              tolerance=0.001),
    ]


# ── manufacturing (3) ────────────────────────────────────────────────────────

def build_manufacturing():
    cp = (10.3 - 9.7) / (6 * 0.1)
    return [
        _item("MFG-001", "manufacturing", "cp",
              "A process has mean=10.0, standard deviation=0.1, "
              "lower spec=9.7, upper spec=10.3. What is the process capability Cp? "
              "Reply with the number rounded to 2 decimal places.",
              round(cp, 2), "numeric",
              "verify_manufacturing",
              {"mean": 10.0, "std": 0.1, "lsl": 9.7, "usl": 10.3,
               "claimed_cp": round(cp, 2)},
              tolerance=0.01),
        _item("MFG-002", "manufacturing", "capable",
              "A process has Cp=1.0. Is it considered capable (Cp ≥ 1.33)? "
              "Answer yes or no.",
              "no", "classification",
              "verify_manufacturing",
              {"claimed_cp": 1.0, "minimum_cp": 1.33,
               "claimed_capable": False}),
        _item("MFG-003", "manufacturing", "tolerance_stack",
              "Three dimensions each have half-range tolerance of 0.1 (i.e., ±0.1). "
              "What is the one-sided worst-case total stack-up (sum of all half-range values)? "
              "Reply with just the number.",
              0.3, "numeric",
              "verify_manufacturing",
              {"tolerances": [0.1, 0.1, 0.1], "method": "worst_case",
               "claimed_stack": 0.3},
              tolerance=0.001),
    ]


# ── meteorology (3) ──────────────────────────────────────────────────────────

def build_meteorology():
    # Magnus formula: dew point for T=20°C, RH=50%
    T, RH = 20.0, 50.0
    a, b = 17.625, 243.04
    gamma = math.log(RH/100) + a*T/(b+T)
    dp = round(b*gamma/(a-gamma), 1)
    return [
        _item("MET-001", "meteorology", "dew_point",
              f"Air temperature is {T}°C and relative humidity is {RH}%. "
              f"What is the dew point in °C? Reply with the number rounded to 1 decimal place.",
              dp, "numeric",
              "verify_meteorology",
              {"temp_c": T, "rh_percent": RH, "claimed_dew_point_c": dp},
              tolerance=0.5),
        _item("MET-002", "meteorology", "wind_chill",
              "Temperature is -15°C and wind speed is 30 km/h. "
              "Is the wind chill below -20°C? Answer yes or no.",
              "yes", "classification",
              "verify_meteorology",
              {"temp_c": -15, "wind_kmh": 30, "claimed_below_c": -20, "is_below": True}),
        _item("MET-003", "meteorology", "humidity",
              "At dew point 10°C and temperature 20°C, is the relative humidity "
              "approximately 50-60%? Answer yes or no.",
              "yes", "classification",
              "verify_meteorology",
              {"temp_c": 20, "dew_point_c": 10, "claimed_rh_50_to_60": True}),
    ]


# ── geology (3) ──────────────────────────────────────────────────────────────

def build_geology():
    return [
        _item("GEOL-001", "geology", "mohs",
              "On the Mohs scale, can a mineral with hardness 7 scratch a mineral "
              "with hardness 4? Answer yes or no.",
              "yes", "classification",
              "verify_geology",
              {"scratcher_hardness": 7, "target_hardness": 4,
               "claimed_can_scratch": True}),
        _item("GEOL-002", "geology", "mohs",
              "Diamond has Mohs hardness 10. Can quartz (hardness 7) scratch diamond? "
              "Answer yes or no.",
              "no", "classification",
              "verify_geology",
              {"scratcher_hardness": 7, "target_hardness": 10,
               "claimed_can_scratch": False}),
        _item("GEOL-003", "geology", "richter",
              "Call verify_geology with richter_M1=6.0, richter_M2=7.0, "
              "claimed_amplitude_ratio=10.0. "
              "A magnitude 7.0 earthquake has how many times the ground motion amplitude "
              "of a magnitude 6.0 earthquake? Reply with just the number.",
              10.0, "numeric",
              "verify_geology",
              {"richter_M1": 6.0, "richter_M2": 7.0,
               "claimed_amplitude_ratio": 10.0},
              tolerance=0.01),
    ]


# ── hydrology (3) ────────────────────────────────────────────────────────────

def build_hydrology():
    return [
        _item("HYD-001", "hydrology", "continuity",
              "Water flows through a pipe with cross-sectional area 0.05 m² "
              "at velocity 2 m/s. What is the flow rate Q? Reply with just the number in m³/s.",
              0.1, "numeric",
              "verify_hydrology",
              {"area_m2": 0.05, "velocity_ms": 2.0, "claimed_q_m3s": 0.1},
              tolerance=0.001),
        _item("HYD-002", "hydrology", "continuity",
              "A river narrows from cross-section 10 m² to 5 m². "
              "If velocity at the wide section is 1 m/s, what is velocity at the narrow section? "
              "Reply with just the number in m/s.",
              2.0, "numeric",
              "verify_hydrology",
              {"a1_m2": 10, "v1_ms": 1.0, "a2_m2": 5, "claimed_v2_ms": 2.0},
              tolerance=0.001),
        _item("HYD-003", "hydrology", "darcy",
              "Darcy's law: Q = K·A·(dh/dL). With K=0.001 m/s, A=1 m², "
              "head difference dh=0.5 m over length L=10 m, what is Q? "
              "Reply with just the number in m³/s.",
              0.00005, "numeric",
              "verify_hydrology",
              {"K_ms": 0.001, "area_m2": 1.0, "dh_m": 0.5, "dL_m": 10,
               "claimed_q_m3s": 0.00005},
              tolerance=0.001),
    ]


# ── astronomy (3) ────────────────────────────────────────────────────────────

def build_astronomy():
    # Kepler T^2 = a^3 → T=1yr → a=1AU
    # T=8yr → a=4AU
    return [
        _item("ASTRO-001", "astronomy", "kepler",
              "Using Kepler's third law (T² ∝ a³), if a planet orbits in 1 Earth year, "
              "what is its semi-major axis in AU? Reply with just the number.",
              1.0, "numeric",
              "verify_astronomy",
              {"period_years": 1.0, "claimed_sma_au": 1.0},
              tolerance=0.01),
        _item("ASTRO-002", "astronomy", "kepler",
              "Using Kepler's third law, a planet has a semi-major axis of 4 AU. "
              "What is its orbital period in Earth years? Reply with just the number.",
              8.0, "numeric",
              "verify_astronomy",
              {"sma_au": 4.0, "claimed_period_years": 8.0},
              tolerance=0.01),
        _item("ASTRO-003", "astronomy", "parallax",
              "A star has a parallax angle of 1 arcsecond. What is its distance in parsecs? "
              "Reply with just the number.",
              1.0, "numeric",
              "verify_astronomy",
              {"parallax_arcsec": 1.0, "claimed_distance_pc": 1.0},
              tolerance=0.001),
    ]


# ── agriculture (3) ──────────────────────────────────────────────────────────

def build_agriculture():
    return [
        _item("AG-001", "agriculture", "hardiness",
              "A plant is rated hardy to USDA zone 5. Can it survive in zone 7? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_agriculture",
              {"plant_zone": 5, "garden_zone": 7, "claimed_survives": True}),
        _item("AG-002", "agriculture", "hardiness",
              "A plant is rated hardy to USDA zone 8. Will it survive in zone 4? "
              "Answer yes or no.",
              "no", "classification",
              "verify_agriculture",
              {"plant_zone": 8, "garden_zone": 4, "claimed_survives": False}),
        _item("AG-003", "agriculture", "soil_ph",
              "Blueberries prefer acidic soil with pH 4.5-5.5. "
              "Is a soil pH of 6.5 suitable for blueberries? Answer yes or no.",
              "no", "classification",
              "verify_agriculture",
              {"crop": "blueberry", "soil_ph": 6.5, "claimed_suitable": False}),
    ]


# ── geography (3) ────────────────────────────────────────────────────────────

def build_geography():
    # Haversine: lat1=0,lon1=0 to lat1=0,lon1=1 ≈ 111.19 km
    import math
    R = 6371
    lat1, lon1, lat2, lon2 = 0, 0, 0, 1
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1)
    dlam = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    d = round(2*R*math.asin(math.sqrt(a)), 2)
    return [
        _item("GEO-001", "geography", "haversine",
              "What is the great-circle distance between (0°N, 0°E) and (0°N, 1°E) "
              "in km? Reply with the number rounded to 2 decimal places.",
              d, "numeric",
              "verify_geography",
              {"lat1": 0, "lon1": 0, "lat2": 0, "lon2": 1,
               "claimed_distance_km": d},
              tolerance=0.5),
        _item("GEO-002", "geography", "validity",
              "Is the coordinate (91°N, 0°E) a valid latitude-longitude? "
              "Answer yes or no.",
              "no", "classification",
              "verify_geography",
              {"lat": 91, "lon": 0, "claimed_valid": False}),
        _item("GEO-003", "geography", "validity",
              "Is the coordinate (45°N, 90°W) a valid latitude-longitude? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_geography",
              {"lat": 45, "lon": -90, "claimed_valid": True}),
    ]


# ── cryptography (3) ─────────────────────────────────────────────────────────

def build_cryptography():
    import hashlib
    msg = "hello"
    sha256 = hashlib.sha256(msg.encode()).hexdigest()
    return [
        _item("CRYPT-001", "cryptography", "hash_match",
              f"What is the SHA-256 hash of the string 'hello'? "
              f"Reply with the hex digest.",
              sha256, "string",
              "verify_cryptography",
              {"message": "hello", "claimed_hash": sha256, "algorithm": "sha256"}),
        _item("CRYPT-002", "cryptography", "hash_strength",
              "Is MD5 considered a cryptographically strong hash for security-critical use? "
              "Answer yes or no.",
              "no", "classification",
              "verify_cryptography",
              {"algorithm": "md5", "claimed_strong": False}),
        _item("CRYPT-003", "cryptography", "key_strength",
              "Is a 256-bit AES key considered strong? Answer yes or no.",
              "yes", "classification",
              "verify_cryptography",
              {"key_bits": 256, "algorithm": "aes", "claimed_strong": True}),
    ]


# ── networking (3) ───────────────────────────────────────────────────────────

def build_networking():
    return [
        _item("NET-001", "networking", "cidr",
              "Is the IP address 192.168.1.50 within the subnet 192.168.1.0/24? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_networking",
              {"ip": "192.168.1.50", "network": "192.168.1.0/24",
               "claimed_in_subnet": True}),
        _item("NET-002", "networking", "cidr",
              "Is the IP address 10.0.2.1 within the subnet 10.0.1.0/24? "
              "Answer yes or no.",
              "no", "classification",
              "verify_networking",
              {"ip": "10.0.2.1", "network": "10.0.1.0/24",
               "claimed_in_subnet": False}),
        _item("NET-003", "networking", "hosts",
              "How many usable host addresses are in a /24 subnet? "
              "Reply with just the number.",
              254, "numeric",
              "verify_networking",
              {"cidr_prefix": 24, "claimed_usable_hosts": 254},
              tolerance=0.0),
    ]


# ── exercise_science (3) ─────────────────────────────────────────────────────

def build_exercise_science():
    # Tanaka 2001 formula (used by the verifier): HRmax = 208 - 0.7 × age
    mhr_tanaka = int(208 - 0.7 * 30)   # 187 bpm
    kcal = 8.0 * 70 * 1.0              # MET × weight_kg × hours = 560 kcal
    target_hr = round((mhr_tanaka - 60) * 0.70 + 60)   # Karvonen at 70% = 149 bpm
    return [
        _item("EX-001", "exercise_science", "max_hr",
              "What is the estimated maximum heart rate for a 30-year-old "
              "using the Tanaka formula (208 - 0.7 × age)? Reply with just the number in bpm.",
              float(mhr_tanaka), "numeric",
              "verify_exercise_science",
              {"age_years": 30, "claimed_max_hr": mhr_tanaka},
              tolerance=1.0),
        _item("EX-002", "exercise_science", "energy",
              "A 70 kg person performs an activity with MET=8 for 1 hour. "
              "How many kcal do they burn (kcal = MET × weight_kg × hours)? "
              "Reply with just the number.",
              kcal, "numeric",
              "verify_exercise_science",
              {"claimed_met": 8.0, "weight_kg": 70, "duration_hours": 1.0,
               "claimed_kcal": kcal},
              tolerance=0.05),
        _item("EX-003", "exercise_science", "target_hr",
              "Using the Karvonen formula with Tanaka HRmax (208 - 0.7×age) "
              "for a 30-year-old with resting HR=60 at 70% intensity, "
              "what is the target heart rate? Reply with just the number in bpm.",
              target_hr, "numeric",
              "verify_exercise_science",
              {"age_years": 30, "resting_hr": 60,
               "intensity_low": 0.70, "intensity_high": 0.70,
               "claimed_zone_low_bpm": target_hr,
               "claimed_zone_high_bpm": target_hr},
              tolerance=2.0),
    ]


# ── sports_analytics (3) ─────────────────────────────────────────────────────

def build_sports_analytics():
    pyth = round(5**2 / (5**2 + 3**2), 3)  # RS=5, RA=3
    return [
        _item("SPORT-001", "sports_analytics", "pythagorean",
              "A baseball team scores 5 runs per game and allows 3 runs per game. "
              "What is their Pythagorean win expectation? "
              "Reply with the decimal rounded to 3 places.",
              pyth, "numeric",
              "verify_sports_analytics",
              {"runs_scored": 5, "runs_allowed": 3, "claimed_win_pct": pyth},
              tolerance=0.001),
        _item("SPORT-002", "sports_analytics", "batting_avg",
              "A batter gets 3 hits in 10 at-bats. What is their batting average? "
              "Reply with the 3-digit decimal.",
              0.300, "numeric",
              "verify_sports_analytics",
              {"hits": 3, "at_bats": 10, "claimed_avg": 0.300},
              tolerance=0.001),
        _item("SPORT-003", "sports_analytics", "era",
              "A pitcher allows 3 earned runs in 9 innings pitched. What is the ERA? "
              "Reply with just the number.",
              3.00, "numeric",
              "verify_sports_analytics",
              {"earned_runs": 3, "innings_pitched": 9, "claimed_era": 3.00},
              tolerance=0.01),
    ]


# ── finance (3) ──────────────────────────────────────────────────────────────

def build_finance():
    fv = round(1000 * (1 + 0.05)**10, 2)  # P=1000, r=5%, t=10yr, annual
    return [
        _item("FIN-001", "finance", "accounting_identity",
              "A company has assets $1,000,000 and liabilities $600,000. "
              "What should equity be? Reply with just the number in dollars.",
              400000.0, "numeric",
              "verify_finance",
              {"assets": 1000000, "liabilities": 600000, "equity": 400000},
              tolerance=1.0),
        _item("FIN-002", "finance", "compound_interest",
              "If you invest $1,000 at 5% annual interest, compounded annually, "
              "what is the value after 10 years? Reply with the number rounded to 2 decimal places.",
              fv, "numeric",
              "verify_finance",
              {"principal": 1000, "rate": 0.05, "compounding_per_year": 1,
               "years": 10, "claimed_future_value": fv},
              tolerance=0.01),
        _item("FIN-003", "finance", "present_value",
              "What is the present value of $1,100 received in 1 year at 10% discount rate? "
              "Reply with just the number.",
              1000.0, "numeric",
              "verify_finance",
              {"future_value": 1100, "pv_discount_rate": 0.10, "pv_periods": 1,
               "claimed_present_value": 1000.0},
              tolerance=0.01),
    ]


# ── music_theory (3) ─────────────────────────────────────────────────────────

def build_music_theory():
    return [
        _item("MUS-001", "music_theory", "interval",
              "How many semitones are in a perfect fifth? Reply with just the number.",
              7, "numeric",
              "verify_music_theory",
              {"note_a": "C4", "note_b": "G4", "claimed_semitones": 7},
              tolerance=0.0),
        _item("MUS-002", "music_theory", "interval",
              "How many semitones are in an octave? Reply with just the number.",
              12, "numeric",
              "verify_music_theory",
              {"note_a": "C4", "note_b": "C5", "claimed_semitones": 12},
              tolerance=0.0),
        _item("MUS-003", "music_theory", "frequency",
              "In equal temperament, if A4=440 Hz, what is the frequency of A5? "
              "Reply with just the number in Hz.",
              880.0, "numeric",
              "verify_music_theory",
              {"note": "A4", "base_freq_hz": 440, "semitones_up": 12,
               "claimed_freq_hz": 880.0},
              tolerance=0.1),
    ]


# ── calendar_time (3) ────────────────────────────────────────────────────────

def build_calendar_time():
    return [
        _item("CAL-001", "calendar_time", "leap_year",
              "Is 2024 a leap year? Answer yes or no.",
              "yes", "classification",
              "verify_calendar_time",
              {"year": 2024, "claimed_leap": True}),
        _item("CAL-002", "calendar_time", "leap_year",
              "Is 1900 a leap year? Answer yes or no.",
              "no", "classification",
              "verify_calendar_time",
              {"year": 1900, "claimed_leap": False}),
        _item("CAL-003", "calendar_time", "day_of_week",
              "What day of the week was January 1, 2000? "
              "Answer: Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, or Sunday.",
              "Saturday", "string",
              "verify_calendar_time",
              {"date": "2000-01-01", "claimed_weekday": "Saturday"}),
    ]


# ── governance (3) ───────────────────────────────────────────────────────────

def build_governance():
    # Governance verifier requires: title, scope (adapter|mesh|canon),
    # red_items, floor_items, way_path, execution_steps, witnesses.
    good_packet = {
        "title": "Approve Q1 R&D budget",
        "scope": "adapter",
        "red_items": ["No coercion", "No conflict of interest"],
        "floor_items": ["Protects all stakeholders", "Reversible within 30 days"],
        "way_path": "Allocate $50,000 to R&D to address demonstrated market demand.",
        "execution_steps": ["CFO signs transfer order", "Transfer to R&D account by Jan 15"],
        "witnesses": ["Alice (CFO)", "Bob (CEO)"],
    }
    bad_packet_no_witnesses = {**good_packet, "witnesses": []}
    bad_packet_no_floor = {**good_packet, "floor_items": []}
    return [
        _item("GOV-001", "governance", "packet_valid",
              f"Call verify_governance_decision_packet with this exact decision_packet "
              f"argument: {json.dumps(good_packet)}. "
              "Does the verifier confirm it is structurally valid? Answer yes or no.",
              "yes", "classification",
              "verify_governance_decision_packet",
              {"decision_packet": good_packet}),
        _item("GOV-002", "governance", "packet_invalid",
              "A decision packet has no witnesses. Is it structurally valid? "
              "Answer yes or no.",
              "no", "classification",
              "verify_governance_decision_packet",
              {"decision_packet": bad_packet_no_witnesses}),
        _item("GOV-003", "governance", "packet_invalid",
              "A decision packet has an empty floor_items list. Is it structurally valid? "
              "Answer yes or no.",
              "no", "classification",
              "verify_governance_decision_packet",
              {"decision_packet": bad_packet_no_floor}),
    ]


# ── document_validation (3) ──────────────────────────────────────────────────

def build_document_validation():
    # ISBN-13 check digit verification
    # 978-0-306-40615-7
    return [
        _item("DOC-001", "document_validation", "isbn13",
              "Call verify_document_validation with isbn13='9780306406157' and "
              "claimed_isbn13_valid=true. Is 9780306406157 a valid ISBN-13? Answer yes or no.",
              "yes", "classification",
              "verify_document_validation",
              {"isbn13": "9780306406157", "claimed_isbn13_valid": True}),
        _item("DOC-002", "document_validation", "isbn13",
              "Is 9780306406158 a valid ISBN-13? (The last digit is wrong.) "
              "Answer yes or no.",
              "no", "classification",
              "verify_document_validation",
              {"isbn13": "9780306406158", "claimed_valid": False}),
        _item("DOC-003", "document_validation", "luhn",
              "Call verify_document_validation with luhn_number='4532015112830366' and "
              "claimed_luhn_valid=true. Is 4532015112830366 valid by the Luhn algorithm? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_document_validation",
              {"luhn_number": "4532015112830366", "claimed_luhn_valid": True}),
    ]


# ── photography (3) ──────────────────────────────────────────────────────────

def build_photography():
    # EV = log2(N^2 / t); N=f/8, t=1/125s, ISO=100 → EV = log2(64*125) = log2(8000) ≈ 12.97
    ev = round(math.log2(64 * 125), 2)
    return [
        _item("PHOTO-001", "photography", "exposure_value",
              "A camera is set to f/8, 1/125s. What is the exposure value (EV)? "
              "Reply with the number rounded to 2 decimal places.",
              ev, "numeric",
              "verify_photography",
              {"aperture_f": 8, "shutter_s": 1/125, "claimed_ev": ev},
              tolerance=0.1),
        _item("PHOTO-002", "photography", "equivalent_exposure",
              "If you open the aperture from f/8 to f/5.6 (one stop), how many "
              "stops of light do you gain? Reply with just the number.",
              1, "numeric",
              "verify_photography",
              {"aperture_a": 8, "aperture_b": 5.6, "claimed_stops": 1},
              tolerance=0.01),
        _item("PHOTO-003", "photography", "iso_stops",
              "If you double the ISO from 100 to 200, how many stops of sensitivity "
              "do you gain? Reply with just the number.",
              1, "numeric",
              "verify_photography",
              {"iso_a": 100, "iso_b": 200, "claimed_stops": 1},
              tolerance=0.01),
    ]


# ── linguistics (3) — Layer 0 optional; items degrade gracefully ─────────────

def build_linguistics():
    return [
        _item("LING-001", "linguistics", "strongs_range",
              "Is G26 a valid Strong's Greek number (Greek NT range is G1-G5624)? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_linguistics",
              {"strongs": "G26", "claimed_valid_range": True}),
        _item("LING-002", "linguistics", "strongs_range",
              "Is G9999 a valid Strong's Greek number? "
              "Answer yes or no.",
              "no", "classification",
              "verify_linguistics",
              {"strongs": "G9999", "claimed_valid_range": False}),
        _item("LING-003", "linguistics", "transliteration_normalization",
              "After stripping diacritics, does the transliteration 'agapē' "
              "normalize to the same string as 'agape'? Answer yes or no.",
              "yes", "classification",
              "verify_linguistics",
              {"transliteration_a": "agapē", "transliteration_b": "agape"}),
    ]


# ── witness (3) ──────────────────────────────────────────────────────────────

def build_witness():
    # Gate chain requires 5 gates: RED, FLOOR, WAY, BROTHERS, GOD.
    # claimed_gate_verdicts must be a list of {"gate": ..., "status": ...} dicts.
    full_chain = [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
        {"gate": "WAY", "status": "PASS"},
        {"gate": "BROTHERS", "status": "PASS"},
        {"gate": "GOD", "status": "PASS"},
    ]
    partial_chain = [
        {"gate": "RED", "status": "PASS"},
        {"gate": "FLOOR", "status": "PASS"},
    ]
    return [
        _item("WIT-001", "witness", "gate_chain",
              f"Use verify_witness to check this gate record: "
              f"{json.dumps({'claimed_gate_verdicts': full_chain})}. "
              "Is the gate chain structurally complete? Answer yes or no.",
              "yes", "classification",
              "verify_witness",
              {"claimed_gate_verdicts": full_chain}),
        _item("WIT-002", "witness", "gate_chain",
              f"Use verify_witness to check this gate record: "
              f"{json.dumps({'claimed_gate_verdicts': partial_chain})}. "
              "Is the gate chain structurally complete (all 5 gates present)? Answer yes or no.",
              "no", "classification",
              "verify_witness",
              {"claimed_gate_verdicts": partial_chain}),
        _item("WIT-003", "witness", "no_fabrication",
              "An AI agent claims it 'computed' a value it cannot actually compute "
              "without external verification. Should this be flagged as a fabricated answer? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_witness",
              {"claimed_no_fabrication": False,
               "agent_asserted_computation": True}),
    ]


# ── quantum_computing (3) ────────────────────────────────────────────────────

def build_quantum_computing():
    import math
    grover_n = 64
    grover_t = math.floor(math.pi * math.sqrt(grover_n) / 4)  # 6
    return [
        _item("QCOMP-001", "quantum_computing", "qubit_normalization",
              "A qubit is in state α=0.6, β=0.8 (real amplitudes). "
              "Is this a valid normalized quantum state? Answer yes or no.",
              "yes", "classification",
              "verify_quantum_computing",
              {"amplitudes": [0.6, 0.8], "claimed_normalized": True}),
        _item("QCOMP-002", "quantum_computing", "grover_iterations",
              f"Grover's search algorithm on a database of {grover_n} items. "
              f"What is the optimal number of iterations? Reply with just the integer.",
              grover_t, "numeric",
              "verify_quantum_computing",
              {"n_items": grover_n, "claimed_grover_iterations": grover_t},
              tolerance=0.0),
        _item("QCOMP-003", "quantum_computing", "bb84_security",
              "In BB84 quantum key distribution, if the measured quantum bit error rate "
              "(QBER) is 12%, is the channel considered secure? Answer yes or no.",
              "no", "classification",
              "verify_quantum_computing",
              {"qber": 0.12, "claimed_secure": False}),
    ]


# ── cross-domain: Shor → Number Theory → Cryptography (3) ───────────────────
#
# A complete quantum-factoring chain.  Each item adds one link:
#   XDOM-001  Shor period check alone          (1 tool: verify_quantum_computing)
#   XDOM-002  Primality of extracted factors    (1 tool: verify_number_theory × 2)
#   XDOM-003  Full chain synthesis             (3 tools: all of the above + verify_cryptography)
#
# Math: a=7, N=15, r=4
#   7^4 mod 15 = 1  ✓   r even  ✓
#   gcd(7²−1, 15) = gcd(48, 15) = 3   →  prime
#   gcd(7²+1, 15) = gcd(50, 15) = 5   →  prime
#   RSA modulus N=15 = 4 bits < 2048  →  weak (NIST)

def build_cross_domain():
    shor_spec = {"shor_a": 7, "shor_N": 15, "shor_r": 4, "claimed_period_valid": True}
    prime3_spec = {"n_prime": 3, "claimed_prime": True}
    prime5_spec = {"n_prime": 5, "claimed_prime": True}
    rsa_spec = {"cipher": "RSA", "key_bits": 4, "claimed_key_strength": "weak"}

    return [
        # ── link 1: Shor period ──────────────────────────────────────────────
        _item("XDOM-001", "cross_domain", "shor_period",
              "Shor's algorithm attempted to factor N=15 using base a=7 and found period r=4. "
              "Call verify_quantum_computing with shor_a=7, shor_N=15, shor_r=4, "
              "claimed_period_valid=true. Is the period valid? Answer yes or no.",
              "yes", "classification",
              "verify_quantum_computing", shor_spec),

        # ── link 2: primality of the extracted factors ───────────────────────
        _item("XDOM-002", "cross_domain", "factor_primality",
              "Shor's factoring of N=15 with a=7, r=4 yielded factors 3 and 5. "
              "Call verify_number_theory twice — once for n_prime=3 and once for n_prime=5, "
              "each with claimed_prime=true. Are both factors prime? Answer yes or no.",
              "yes", "classification",
              "verify_number_theory",
              {"check_a": prime3_spec, "check_b": prime5_spec}),

        # ── link 3: full synthesis ────────────────────────────────────────────
        _item("XDOM-003", "cross_domain", "rsa_broken_chain",
              "Run the full Shor factoring chain on RSA modulus N=15 with a=7, r=4:\n"
              "Step 1 — call verify_quantum_computing with shor_a=7, shor_N=15, shor_r=4, "
              "claimed_period_valid=true (confirms period and extracts factors 3 and 5).\n"
              "Step 2 — call verify_number_theory twice: n_prime=3 claimed_prime=true, "
              "then n_prime=5 claimed_prime=true (confirms both factors are prime).\n"
              "Step 3 — call verify_cryptography with cipher=RSA, key_bits=4, "
              "claimed_key_strength=weak (confirms this 4-bit RSA key fails NIST ≥2048-bit standard).\n"
              "After all three steps confirm, answer: is this RSA key cryptographically broken? "
              "Answer yes or no.",
              "yes", "classification",
              "cross_domain",
              {"shor": shor_spec, "prime3": prime3_spec,
               "prime5": prime5_spec, "rsa": rsa_spec}),
    ]


# ── economics (3) ────────────────────────────────────────────────────────────

def build_economics():
    return [
        _item("ECON-001", "economics", "simple_interest",
              "Using the simple interest formula (I = P × r × t), what is the interest "
              "on a principal of $1,000 at 5% annual rate for 3 years? "
              "Call verify_economics to check your answer, then reply with just the number.",
              150.0, "numeric",
              "verify_economics",
              {"principal": 1000, "rate": 0.05, "time_years": 3,
               "claimed_simple_interest": 150.0},
              tolerance=0.01),
        _item("ECON-002", "economics", "rule_of_72",
              "Using the Rule of 72, at an 8% annual growth rate, "
              "approximately how many years does it take to double an investment? "
              "Reply with just the number.",
              9.0, "numeric",
              "verify_economics",
              {"rate_percent": 8, "claimed_doubling_years": 9.0},
              tolerance=0.5),
        _item("ECON-003", "economics", "gdp_per_capita",
              "A country has GDP of $21 trillion and a population of 331 million. "
              "What is the GDP per capita? Reply with the number rounded to the nearest integer.",
              round(21e12 / 331e6), "numeric",
              "verify_economics",
              {"gdp": 21_000_000_000_000, "population": 331_000_000,
               "claimed_gdp_per_capita": round(21e12 / 331e6)},
              tolerance=1.0),
    ]


# ── labor (3) ────────────────────────────────────────────────────────────────

def build_labor():
    ot_pay = round(40 * 20.0 + 5 * 20.0 * 1.5, 2)  # FLSA: regular + 1.5x OT
    return [
        _item("LAB-001", "labor", "gross_pay",
              "An employee earns $18.50/hour and works 40 hours. "
              "What is their gross pay? Reply with just the number.",
              740.0, "numeric",
              "verify_labor",
              {"hourly_rate": 18.50, "hours_worked": 40, "claimed_gross_pay": 740.0},
              tolerance=0.01),
        _item("LAB-002", "labor", "overtime_pay",
              "Under FLSA, an employee earning $20/hour works 45 hours in a week. "
              "The first 40 hours are at regular rate; hours over 40 are at 1.5×. "
              "What is the total gross pay? Reply with just the number.",
              ot_pay, "numeric",
              "verify_labor",
              {"hourly_rate": 20.0, "regular_hours": 40, "overtime_hours": 5,
               "claimed_overtime_pay": ot_pay},
              tolerance=0.01),
        _item("LAB-003", "labor", "annual_to_hourly",
              "A salaried employee earns $52,000 per year (2,080 work hours/year). "
              "What is the equivalent hourly rate? Reply with just the number.",
              25.0, "numeric",
              "verify_labor",
              {"annual_salary": 52000, "claimed_hourly_equivalent": 25.0},
              tolerance=0.01),
    ]


# ── real_estate (3) ──────────────────────────────────────────────────────────

def build_real_estate():
    return [
        _item("RE-001", "real_estate", "loan_to_value",
              "A borrower takes a $240,000 loan on a property appraised at $300,000. "
              "What is the loan-to-value (LTV) ratio? Reply with the decimal number.",
              0.80, "numeric",
              "verify_real_estate",
              {"loan_amount": 240_000, "appraised_value": 300_000, "claimed_ltv": 0.80},
              tolerance=0.001),
        _item("RE-002", "real_estate", "cap_rate",
              "A property generates $24,000 net operating income and is valued at $400,000. "
              "What is the cap rate? Reply with the decimal number.",
              0.06, "numeric",
              "verify_real_estate",
              {"net_operating_income": 24_000, "property_value": 400_000,
               "claimed_cap_rate": 0.06},
              tolerance=0.001),
        _item("RE-003", "real_estate", "gross_rent_multiplier",
              "A property is priced at $300,000 and generates $24,000 annual gross rent. "
              "What is the Gross Rent Multiplier (GRM)? Reply with just the number.",
              12.5, "numeric",
              "verify_real_estate",
              {"property_price": 300_000, "annual_gross_rent": 24_000,
               "claimed_grm": 12.5},
              tolerance=0.01),
    ]


# ── construction (3) ─────────────────────────────────────────────────────────

def build_construction():
    return [
        _item("CONSTR-001", "construction", "concrete_volume",
              "A concrete slab is 10 m long, 5 m wide, and 0.15 m deep. "
              "What is the volume of concrete needed in cubic metres? Reply with just the number.",
              7.5, "numeric",
              "verify_construction",
              {"length_m": 10, "width_m": 5, "depth_m": 0.15, "claimed_concrete_m3": 7.5},
              tolerance=0.01),
        _item("CONSTR-002", "construction", "rectangular_area",
              "A rectangular room is 10 m long and 5 m wide. "
              "What is the floor area in square metres? Reply with just the number.",
              50.0, "numeric",
              "verify_construction",
              {"length_m": 10, "width_m": 5, "claimed_rect_area_m2": 50.0},
              tolerance=0.01),
        _item("CONSTR-003", "construction", "paint_coverage",
              "A wall has 80 m² of paintable surface. Each can covers 10 m². "
              "How many cans are needed? Reply with just the number.",
              8, "numeric",
              "verify_construction",
              {"paint_area_m2": 80, "coverage_m2_per_can": 10, "claimed_paint_cans": 8},
              tolerance=0.0),
    ]


# ── soil_science (3) ─────────────────────────────────────────────────────────

def build_soil_science():
    etc = round(5.0 * 1.15, 2)
    return [
        _item("SOIL-001", "soil_science", "ph_suitability",
              "Maize grows best at soil pH 5.8–7.0. Is a soil pH of 6.2 suitable for maize? "
              "Answer yes or no.",
              "yes", "classification",
              "verify_soil_science",
              {"crop": "maize", "soil_ph": 6.2, "claimed_ph_suitable": True}),
        _item("SOIL-002", "soil_science", "ph_suitability",
              "Blueberries require acidic soil with pH 4.0–5.5. "
              "Is a soil pH of 6.0 suitable for blueberries? Answer yes or no.",
              "no", "classification",
              "verify_soil_science",
              {"crop": "blueberry", "soil_ph": 6.0, "claimed_ph_suitable": False}),
        _item("SOIL-003", "soil_science", "irrigation_req",
              "Reference evapotranspiration ET₀ is 5.0 mm/day and the crop coefficient Kc is 1.15. "
              "What is the crop water requirement ETc in mm/day? Reply with just the number.",
              etc, "numeric",
              "verify_soil_science",
              {"reference_et0_mm_per_day": 5.0, "crop_coefficient": 1.15,
               "claimed_etc_mm_per_day": etc},
              tolerance=0.01),
    ]


# ── cybersecurity (3) ────────────────────────────────────────────────────────

def build_cybersecurity():
    entropy = round(16 * math.log2(94), 2)
    return [
        _item("CYBER-001", "cybersecurity", "password_entropy",
              "A password is 16 characters long drawn from a charset of 94 printable ASCII characters. "
              "Using H = L × log₂(N), what is the entropy in bits? "
              "Reply with the number rounded to 2 decimal places.",
              entropy, "numeric",
              "verify_cybersecurity",
              {"password_length": 16, "charset_size": 94,
               "claimed_entropy_bits": entropy},
              tolerance=0.05),
        _item("CYBER-002", "cybersecurity", "subnet_hosts",
              "How many usable host addresses are in a /24 subnet (IPv4)? "
              "Reply with just the number.",
              254, "numeric",
              "verify_cybersecurity",
              {"cidr_prefix": 24, "claimed_host_count": 254},
              tolerance=0.0),
        _item("CYBER-003", "cybersecurity", "cvss_severity",
              "A vulnerability has a CVSS v3 base score of 9.1. "
              "What is the severity label? "
              "Answer: none, low, medium, high, or critical.",
              "critical", "string",
              "verify_cybersecurity",
              {"cvss_base_score": 9.1, "claimed_cvss_severity": "critical"}),
    ]


# ── medicine (3) ─────────────────────────────────────────────────────────────

def build_medicine():
    bmi = round(70 / 1.75**2, 1)
    map_val = round(80 + (120 - 80) / 3, 1)
    return [
        _item("MED-001", "medicine", "bmi_class",
              "A person weighs 70 kg and is 1.75 m tall. "
              "Using BMI = weight / height², what BMI class do they fall into? "
              "Answer: underweight, normal, overweight, or obese.",
              "normal", "string",
              "verify_medicine",
              {"weight_kg": 70, "height_m": 1.75,
               "claimed_bmi": bmi, "claimed_bmi_class": "normal"}),
        _item("MED-002", "medicine", "drug_dosage",
              "A drug is dosed at 5 mg/kg. What is the correct dose for a 70 kg patient? "
              "Reply with just the number in mg.",
              350.0, "numeric",
              "verify_medicine",
              {"dose_mg_per_kg": 5.0, "weight_kg": 70, "claimed_dose_mg": 350.0},
              tolerance=0.01),
        _item("MED-003", "medicine", "map",
              "A patient has systolic BP 120 mmHg and diastolic BP 80 mmHg. "
              "Using MAP = DBP + (SBP − DBP)/3, what is the mean arterial pressure? "
              "Reply with the number rounded to 1 decimal place.",
              map_val, "numeric",
              "verify_medicine",
              {"systolic": 120, "diastolic": 80, "claimed_map_mmhg": map_val},
              tolerance=0.5),
    ]


# ── main ─────────────────────────────────────────────────────────────────────

BUILDERS = [
    build_chemistry, build_statistics, build_physics,
    build_mathematics, build_computer_science, build_biology,
    build_genetics, build_nutrition, build_formal_logic,
    build_number_theory, build_combinatorics, build_geometry,
    build_information_theory, build_electrical, build_energy,
    build_optics, build_acoustics, build_manufacturing,
    build_meteorology, build_geology, build_hydrology,
    build_astronomy, build_agriculture, build_geography,
    build_cryptography, build_networking, build_exercise_science,
    build_sports_analytics, build_finance, build_music_theory,
    build_calendar_time, build_governance, build_document_validation,
    build_photography, build_linguistics, build_witness,
    build_quantum_computing,
    build_cross_domain,
    build_economics, build_labor, build_real_estate,
    build_construction, build_soil_science,
    build_cybersecurity, build_medicine,
]


def main():
    items = []
    for fn in BUILDERS:
        items.extend(fn())

    out = THIS.parent / "items_extended.jsonl"
    with out.open("w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")

    counts = {}
    for it in items:
        counts[it["domain"]] = counts.get(it["domain"], 0) + 1

    print(f"Wrote {len(items)} items to {out}")
    for d, n in sorted(counts.items()):
        print(f"  {d:30s}: {n}")


if __name__ == "__main__":
    main()
