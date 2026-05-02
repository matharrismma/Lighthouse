"""Concordance Engine v1.0 — comprehensive test suite.

Tests all domain validators and the full gate sequence.
Run: PYTHONPATH=src python tests/test_engine.py
"""
from concordance_engine.engine import EngineConfig, validate_packet

CFG = EngineConfig(schema_path="schema/packet.schema.json")
PASS_TIME = 1700000000
FUTURE = PASS_TIME + 100000  # well past any wait window


def test(name, packet, expected, now=FUTURE):
    res = validate_packet(packet, now_epoch=now, config=CFG)
    status = res.overall
    ok = status == expected
    icon = "✓" if ok else "✗"
    print(f"  {icon} {name}: {status}", end="")
    if not ok:
        print(f"  (expected {expected})")
        for gr in res.gate_results:
            print(f"      {gr.gate}: {gr.status} {gr.reasons}")
    else:
        # Show details for failures
        for gr in res.gate_results:
            if gr.status != "PASS":
                print(f"  [{gr.gate}: {gr.reasons[0][:60]}]", end="")
        print()
    assert ok, f"{name}: got {status}, expected {expected}"


def base_packet(**overrides):
    """Minimal valid packet that passes all 4 gates."""
    pkt = {
        "domain": "governance",
        "scope": "adapter",
        "created_epoch": PASS_TIME,
        "required_witnesses": 2,
        "witness_count": 3,
        "text": "A proposal for transparent community governance with shared resources.",
    }
    pkt.update(overrides)
    return pkt


if __name__ == "__main__":
    print("=" * 60)
    print("CONCORDANCE ENGINE v1.0 — Test Suite")
    print("=" * 60)

    # ── Governance domain ──
    print("\nGovernance / Business / Education / Church:")

    test("Clean governance proposal → PASS",
         base_packet(), "PASS")

    test("Fake testimonials → REJECT (RED: deception)",
         base_packet(text="Testimonials were written by employees pretending to be customers."), "REJECT")

    test("Church hides finances → REJECT (RED: accountability)",
         base_packet(domain="church",
                     text="Stop publishing financial statements because questions are divisive."), "REJECT")

    test("Predatory lending → REJECT (RED: exploitation)",
         base_packet(domain="business",
                     text="Payday lending targets captive audience with usury rates, no alternative services."), "REJECT")

    test("Shame vests for kids → REJECT (RED: identity branding)",
         base_packet(domain="education",
                     text="Students who misbehave must wear a vest labeled DISRUPTIVE."), "REJECT")

    test("License plates 5yr retention → PASS with FLOOR warning",
         base_packet(text="Install license-plate readers at every intersection retaining scans for 5 years."), "PASS")

    test("Missing witnesses → QUARANTINE",
         base_packet(witness_count=0), "QUARANTINE")

    test("Wait period not elapsed → QUARANTINE",
         base_packet(), "QUARANTINE", now=PASS_TIME + 10)

    # ── Mathematics domain ──
    print("\nMathematics:")

    test("Valid math packet → PASS",
         base_packet(domain="mathematics", text="",
                     MATH_RED={"well_formedness": {"symbols_defined": True, "quantifiers_scoped": True, "domains_declared": True},
                               "type_safety": {"objects_typed": True, "operations_valid": True},
                               "definitional_integrity": {"no_circular_definitions": True, "definitions_total": True},
                               "inference_integrity": {"rules_named": True, "steps_justified": True}},
                     MATH_FLOOR={"axioms_selected": ["ZFC"],
                                 "numerical_policy": {"tolerance": 1e-12, "stability_checks": True}}),
         "PASS")

    test("Math: undefined symbols → REJECT",
         base_packet(domain="mathematics", text="",
                     MATH_RED={"well_formedness": {"symbols_defined": False, "quantifiers_scoped": True, "domains_declared": True},
                               "type_safety": {"objects_typed": True, "operations_valid": True},
                               "inference_integrity": {"rules_named": True, "steps_justified": True}},
                     MATH_FLOOR={"axioms_selected": ["ZFC"], "numerical_policy": {"tolerance": 1e-12}}),
         "REJECT")

    test("Math: flat packet with claims → PASS",
         base_packet(domain="mathematics", text="",
                     claims=["theorem X"], artifacts={"proof": "ref"}),
         "PASS")

    # ── Physics domain ──
    print("\nPhysics:")

    test("Physics with conservation → PASS",
         base_packet(domain="physics", text="",
                     conservation_checks={"energy": True}, units="SI"),
         "PASS")

    test("Physics: no conservation field → REJECT",
         base_packet(domain="physics", text="", units="SI"),
         "REJECT")

    # ── Chemistry domain ──
    print("\nChemistry:")

    test("Valid chemistry packet → PASS",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed", "ideality_assumption": "ideal"},
                     CHEM_RED={"mass_conserved": True, "charge_conserved": True, "dimensional_consistency": True},
                     CHEM_FLOOR={"units_stated": True}),
         "PASS")

    test("Chemistry: mass violation → REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed"},
                     CHEM_RED={"mass_conserved": False, "charge_conserved": True}),
         "REJECT")

    test("Chemistry: negative temperature → REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": -10, "system_boundary": "closed"},
                     CHEM_RED={"mass_conserved": True}),
         "REJECT")


    # ── Biology domain ──
    print("\nBiology:")

    test("Valid biology packet -> PASS",
         base_packet(domain="biology", text="",
                     BIO_RED={"conservation": {"mass_balance": True, "charge_balance": True, "energy_budget": True},
                              "second_law_satisfied": True,
                              "causality": {"mechanism_specified": True},
                              "stoichiometry_balanced": True},
                     BIO_MEASUREMENT={"controls_included": True, "biological_replicates": 3}),
         "PASS")

    test("Biology: mass balance violation -> REJECT",
         base_packet(domain="biology", text="",
                     BIO_RED={"conservation": {"mass_balance": False}}),
         "REJECT")

    test("Biology: causality missing -> REJECT",
         base_packet(domain="biology", text="",
                     BIO_RED={"conservation": {"mass_balance": True},
                              "causality": {"mechanism_specified": False}}),
         "REJECT")

    test("Biology: decision-grade claim needs 2+ assay classes -> REJECT",
         base_packet(domain="biology", text="",
                     BIO_RED={"conservation": {"mass_balance": True}},
                     BIO_MEASUREMENT={"controls_included": True, "biological_replicates": 3,
                                      "decision_grade_claim": True,
                                      "orthogonal_assay_classes": ["qPCR"]}),
         "REJECT")

    test("Biology: insufficient replicates -> REJECT",
         base_packet(domain="biology", text="",
                     BIO_RED={"conservation": {"mass_balance": True}},
                     BIO_MEASUREMENT={"controls_included": True, "biological_replicates": 2}),
         "REJECT")

    test("Biology: flat packet with claims -> PASS",
         base_packet(domain="biology", text="",
                     claims=["Cell viability maintained"], artifacts={"assay": "MTT"}),
         "PASS")

    # ── Chemistry (enhanced) ──
    print("\nChemistry (enhanced):")

    test("Chemistry: equilibrium_in_activities violation -> REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed"},
                     CHEM_RED={"mass_conserved": True, "charge_conserved": True,
                               "equilibrium_in_activities": False}),
         "REJECT")

    test("Chemistry: hazardous with no safety notes -> REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed",
                                 "ideality_assumption": "ideal"},
                     CHEM_RED={"mass_conserved": True, "charge_conserved": True},
                     CHEM_FLOOR={"units_stated": True,
                                 "hazardous_conditions": True, "safety_notes_included": False}),
         "REJECT")

    test("Chemistry: limiting cases not checked -> REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed",
                                 "ideality_assumption": "ideal"},
                     CHEM_RED={"mass_conserved": True, "charge_conserved": True},
                     CHEM_FLOOR={"units_stated": True, "limiting_cases_checked": False}),
         "REJECT")

    test("Chemistry: state/path integrity violation -> REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15},
                     CHEM_RED={"mass_conserved": True, "state_path_integrity": False}),
         "REJECT")

    test("Chemistry: MODEL_MISMATCH diagnostic -> REJECT",
         base_packet(domain="chemistry", text="",
                     CHEM_SETUP={"temperature_K": 298.15, "system_boundary": "closed",
                                 "ideality_assumption": "ideal"},
                     CHEM_RED={"mass_conserved": True, "charge_conserved": True},
                     CHEM_FLOOR={"units_stated": True},
                     diagnostics=[{"diagnosis": "MODEL_MISMATCH", "action": "switch to activity model"}]),
         "REJECT")


    # ── Computer Science domain ──
    print("\nComputer Science:")

    test("CS: valid algorithm packet -> PASS",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": True, "no_undefined_behavior": True},
                     CS_COMPLEXITY={"time_bound": "O(n log n)", "space_bound": "O(n)",
                                    "input_variable": "n = number of elements", "case": "worst"},
                     CS_FLOOR={"input_output_declared": True, "case_analysis_stated": True}),
         "PASS")

    test("CS: termination unproven -> REJECT",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": False, "no_undefined_behavior": True}),
         "REJECT")

    test("CS: complexity missing input variable -> REJECT",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": True},
                     CS_COMPLEXITY={"time_bound": "O(n log n)", "case": "worst"}),
         "REJECT")

    test("CS: undefined behavior -> REJECT",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": True, "no_undefined_behavior": False}),
         "REJECT")

    test("CS: reduction direction missing -> REJECT",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": True, "reduction_direction_stated": False}),
         "REJECT")

    test("CS: distributed no consistency model -> REJECT",
         base_packet(domain="computer_science", text="",
                     CS_RED={"termination_proven": True, "consistency_model_cited": False}),
         "REJECT")

    test("CS: flat packet with claims -> PASS",
         base_packet(domain="computer_science", text="",
                     claims=["Merge sort is O(n log n)"], artifacts={"proof": "by recurrence"}),
         "PASS")

    # ── Statistics domain ──
    print("\nStatistics:")

    test("Statistics: valid inference packet -> PASS",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": True,
                               "effect_size_reported": True,
                               "pvalue_interpreted_correctly": True,
                               "multiple_comparisons_corrected": True},
                     STAT_INFERENCE={"p_value": 0.03, "alpha": 0.05,
                                     "effect_size": 0.42, "effect_size_type": "Cohen's d",
                                     "confidence_interval": [0.1, 0.74],
                                     "confidence_level": 0.95,
                                     "sample_size": 120},
                     STAT_FLOOR={"sampling_mechanism_stated": True,
                                 "distributional_assumptions_tested": True,
                                 "sample_size_justified": True}),
         "PASS")

    test("Statistics: p-value misinterpretation -> REJECT",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": True,
                               "pvalue_interpreted_correctly": False,
                               "effect_size_reported": True}),
         "REJECT")

    test("Statistics: effect size missing on significant result -> REJECT",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": True,
                               "pvalue_interpreted_correctly": True},
                     STAT_INFERENCE={"p_value": 0.01, "alpha": 0.05}),
         "REJECT")

    test("Statistics: post-hoc hypothesis -> REJECT",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": False,
                               "pvalue_interpreted_correctly": True,
                               "effect_size_reported": True}),
         "REJECT")

    test("Statistics: multiple comparisons not corrected -> REJECT",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": True,
                               "pvalue_interpreted_correctly": True,
                               "effect_size_reported": True,
                               "multiple_comparisons_corrected": False}),
         "REJECT")

    test("Statistics: distributional assumptions not tested -> REJECT (FLOOR)",
         base_packet(domain="statistics", text="",
                     STAT_RED={"hypothesis_prespecified": True,
                               "pvalue_interpreted_correctly": True,
                               "effect_size_reported": True},
                     STAT_FLOOR={"sampling_mechanism_stated": True,
                                 "distributional_assumptions_tested": False,
                                 "sample_size_justified": True}),
         "REJECT")

    test("Statistics: flat packet with claims -> PASS",
         base_packet(domain="statistics", text="",
                     claims=["RCT shows treatment effect"], artifacts={"table": "Table 2"}),
         "PASS")

    # ── Unknown domain ──
    print("\nEdge cases:")

    test("Unknown domain → PASS (no validator, passes generic)",
         base_packet(domain="astrology"), "PASS")

    # ── Negation handling (governance scanner brittleness fix) ──
    print("\nNegation handling:")

    test("Negated 'will not exploit' → PASS (negation suppresses match)",
         base_packet(text="We will not exploit anyone in this arrangement and no predatory terms are permitted."),
         "PASS")

    test("Negated 'do not deceive' → PASS",
         base_packet(text="Members do not deceive customers and never fabricate testimonials."),
         "PASS")

    test("Asserted 'we exploit' still → REJECT",
         base_packet(text="The plan is to exploit captive audiences with predatory pricing."),
         "REJECT")

    test("Negated 'never coerce' but later real coercion → REJECT",
         base_packet(text="We never coerce employees, but we will use mandatory surveillance to monitor them."),
         "REJECT")

    # ── Verifier layer (computational checks) ──
    print("\nVerifier layer (artifacts checked, not just attested):")

    # Chemistry: balanced equation should pass
    test("Chemistry: balanced equation → PASS",
         base_packet(domain="chemistry",
                     CHEM_RED={"mass_conserved": True, "charge_balanced": True,
                               "elements_consistent": True, "phases_specified": True},
                     CHEM_SETUP={"reagents": ["H2", "O2"], "products": ["H2O"],
                                 "temperature_K": 298.15},
                     CHEM_VERIFY={"equation": "2 H2 + O2 -> 2 H2O"}),
         "PASS")

    # Chemistry: unbalanced equation should fail RED on verifier
    test("Chemistry: unbalanced equation → REJECT",
         base_packet(domain="chemistry",
                     CHEM_RED={"mass_conserved": True, "charge_balanced": True,
                               "elements_consistent": True, "phases_specified": True},
                     CHEM_SETUP={"reagents": ["H2", "O2"], "products": ["H2O"],
                                 "temperature_K": 298.15},
                     CHEM_VERIFY={"equation": "H2 + O2 -> H2O"}),
         "REJECT")

    # Chemistry: redox with charges balances correctly
    test("Chemistry: balanced redox with charges → PASS",
         base_packet(domain="chemistry",
                     CHEM_RED={"mass_conserved": True, "charge_balanced": True,
                               "elements_consistent": True, "phases_specified": True},
                     CHEM_SETUP={"reagents": ["MnO4^-", "Fe^2+"], "products": ["Mn^2+", "Fe^3+"],
                                 "temperature_K": 298.15},
                     CHEM_VERIFY={"equation": "MnO4^- + 5 Fe^2+ + 8 H^+ -> Mn^2+ + 5 Fe^3+ + 4 H2O"}),
         "PASS")

    # Chemistry: negative temperature in CHEM_VERIFY fails on temperature alone
    test("Chemistry: T<0 K in CHEM_VERIFY → REJECT",
         base_packet(domain="chemistry",
                     CHEM_RED={"mass_conserved": True, "charge_balanced": True,
                               "elements_consistent": True, "phases_specified": True},
                     CHEM_SETUP={"reagents": ["H2"], "products": ["H2"], "temperature_K": 298.15},
                     CHEM_VERIFY={"equation": "2 H2 + O2 -> 2 H2O", "temperature_K": -5}),
         "REJECT")

    # Physics: F = m*a dimensional check passes
    test("Physics: F=ma dimensional → PASS",
         base_packet(domain="physics",
                     conservation_checks={"dimensional_consistency": {"required": True, "verified": True}},
                     units="SI",
                     PHYS_VERIFY={"equation": "F = m * a",
                                  "symbols": {"F": "newton", "m": "kilogram",
                                              "a": "meter/second**2"}}),
         "PASS")

    # Physics: dimensionally inconsistent equation rejected
    test("Physics: F=mv dimensional MISMATCH → REJECT",
         base_packet(domain="physics",
                     conservation_checks={"dimensional_consistency": {"required": True, "verified": True}},
                     units="SI",
                     PHYS_VERIFY={"equation": "F = m * v",
                                  "symbols": {"F": "newton", "m": "kilogram",
                                              "v": "meter/second"}}),
         "REJECT")

    # Physics: conservation arithmetic — drift within tolerance
    test("Physics: conservation within tol → PASS",
         base_packet(domain="physics",
                     conservation_checks={"dimensional_consistency": {"required": True, "verified": True}},
                     units="SI",
                     PHYS_VERIFY={"before": {"momentum": 12.5, "energy": 100.0},
                                  "after": {"momentum": 12.5, "energy": 100.0}}),
         "PASS")

    # Physics: conservation arithmetic — large drift rejected
    test("Physics: conservation drift → REJECT",
         base_packet(domain="physics",
                     conservation_checks={"dimensional_consistency": {"required": True, "verified": True}},
                     units="SI",
                     PHYS_VERIFY={"before": {"momentum": 12.5},
                                  "after": {"momentum": 11.0}}),
         "REJECT")

    # Mathematics: symbolic equality passes
    test("Mathematics: (x+1)^2 == x^2+2x+1 → PASS",
         base_packet(domain="mathematics",
                     MATH_RED={
                         "well_formedness": {"symbols_defined": True, "quantifiers_scoped": True,
                                             "domains_declared": True},
                         "type_safety": {"objects_typed": True, "operations_valid": True},
                         "definitional_integrity": {"no_circular_definitions": True},
                         "inference_integrity": {"rules_named": True, "steps_justified": True},
                     },
                     artifacts={"derivation": "expanded by hand"},
                     MATH_VERIFY={"expr_a": "(x+1)**2", "expr_b": "x**2 + 2*x + 1",
                                  "variables": ["x"]}),
         "PASS")

    # Mathematics: derivative claim wrong
    test("Mathematics: wrong derivative → REJECT",
         base_packet(domain="mathematics",
                     MATH_RED={
                         "well_formedness": {"symbols_defined": True, "quantifiers_scoped": True,
                                             "domains_declared": True},
                         "type_safety": {"objects_typed": True, "operations_valid": True},
                         "definitional_integrity": {"no_circular_definitions": True},
                         "inference_integrity": {"rules_named": True, "steps_justified": True},
                     },
                     artifacts={"derivation": "via chain rule"},
                     MATH_VERIFY={"function": "sin(x)", "variable": "x",
                                  "claimed_derivative": "-cos(x)"}),
         "REJECT")

    # Statistics: p-value recomputation matches claim
    test("Statistics: t-test p matches → PASS",
         base_packet(domain="statistics",
                     STAT_INFERENCE={"test_specified": True, "assumptions_tested": True,
                                     "p_value": 0.0003, "alpha": 0.05,
                                     "effect_size": 1.0, "effect_size_type": "cohen_d",
                                     "confidence_interval": [0.5, 1.5],
                                     "claimed_significance": "significant",
                                     "hypothesis_pre_specified": True,
                                     "multiple_comparisons_corrected": True},
                     STAT_VERIFY={"test": "two_sample_t",
                                  "n1": 30, "n2": 30,
                                  "mean1": 5.0, "mean2": 4.0,
                                  "sd1": 1.0, "sd2": 1.0,
                                  "tail": "two-sided",
                                  "claimed_p": 0.0003}),
         "PASS")

    # Statistics: Bonferroni claim wrong
    test("Statistics: Bonferroni rejection set wrong → REJECT",
         base_packet(domain="statistics",
                     STAT_INFERENCE={"test_specified": True, "assumptions_tested": True,
                                     "p_value": 0.001, "alpha": 0.05,
                                     "effect_size": 0.5, "effect_size_type": "cohen_d",
                                     "confidence_interval": [0.1, 0.9],
                                     "claimed_significance": "significant",
                                     "hypothesis_pre_specified": True,
                                     "multiple_comparisons_corrected": True},
                     STAT_VERIFY={"raw_p_values": [0.001, 0.008, 0.04, 0.05, 0.5],
                                  "method": "bonferroni",
                                  "alpha": 0.05,
                                  "claimed_rejected_indices": [0, 1, 2]}),
         "REJECT")

    # CS: well-formed function with correct test cases passes
    test("CS: linear scan with correct cases → PASS",
         base_packet(domain="computer_science",
                     CS_RED={"termination_proven": True, "memory_safety_addressed": True,
                             "no_undefined_behavior": True, "concurrency_correctness_addressed": True},
                     CS_COMPLEXITY={"case": "worst", "time": "O(n)", "space": "O(1)"},
                     CS_VERIFY={
                         "code": "def lsum(a):\n    s = 0\n    for x in a: s += x\n    return s",
                         "function_name": "lsum",
                         "test_cases": [
                             {"args": [[1, 2, 3, 4]], "expected": 10},
                             {"args": [[]], "expected": 0},
                         ],
                     }),
         "PASS")

    # CS: infinite loop static check fails
    test("CS: while True without break → REJECT",
         base_packet(domain="computer_science",
                     CS_RED={"termination_proven": True, "memory_safety_addressed": True,
                             "no_undefined_behavior": True, "concurrency_correctness_addressed": True},
                     CS_COMPLEXITY={"case": "worst", "time": "O(1)", "space": "O(1)"},
                     CS_VERIFY={
                         "code": "def loop():\n    while True:\n        x = 1",
                         "function_name": "loop",
                     }),
         "REJECT")

    # CS: function with failing test cases
    test("CS: wrong implementation → REJECT",
         base_packet(domain="computer_science",
                     CS_RED={"termination_proven": True, "memory_safety_addressed": True,
                             "no_undefined_behavior": True, "concurrency_correctness_addressed": True},
                     CS_COMPLEXITY={"case": "worst", "time": "O(1)", "space": "O(1)"},
                     CS_VERIFY={
                         "code": "def add(a, b):\n    return a - b",
                         "function_name": "add",
                         "test_cases": [{"args": [2, 3], "expected": 5}],
                     }),
         "REJECT")

    # CS: runtime complexity verification — bubble sort O(n^2) confirmed
    test("CS: bubble sort claimed O(n**2) → PASS",
         base_packet(domain="computer_science",
                     CS_RED={"termination_proven": True, "memory_safety_addressed": True,
                             "no_undefined_behavior": True, "concurrency_correctness_addressed": True},
                     CS_COMPLEXITY={"case": "worst", "time": "O(n**2)", "space": "O(1)"},
                     CS_VERIFY={
                         "code": ("def bsort(a):\n"
                                  "    a = list(a); n = len(a)\n"
                                  "    for i in range(n):\n"
                                  "        for j in range(n-1-i):\n"
                                  "            if a[j] > a[j+1]:\n"
                                  "                a[j], a[j+1] = a[j+1], a[j]\n"
                                  "    return a"),
                         "function_name": "bsort",
                         "input_generator": "def gen(n):\n    return [list(reversed(range(n)))]",
                         "claimed_class": "O(n**2)",
                         "sizes": [50, 100, 200, 400],
                     }),
         "PASS")

    # ── Biology verifier ──
    print("\nBiology verifier:")

    test("Biology: 4 replicates, 3 assay classes → PASS",
         base_packet(domain="biology",
                     BIO_RED={"orthogonal_assays_used": ["qPCR", "western_blot", "imaging"]},
                     artifacts={"protocol": "see methods"},
                     BIO_VERIFY={
                         "n_replicates": 4,
                         "min_replicates": 3,
                         "assay_classes": ["qPCR", "western_blot", "imaging"],
                         "min_assay_classes": 2,
                     }),
         "PASS")

    test("Biology: 2 replicates → REJECT",
         base_packet(domain="biology",
                     BIO_RED={"orthogonal_assays_used": ["qPCR", "western_blot"]},
                     artifacts={"protocol": "see methods"},
                     BIO_VERIFY={"n_replicates": 2, "min_replicates": 3,
                                 "assay_classes": ["qPCR", "western_blot"]}),
         "REJECT")

    test("Biology: monotonic dose-response → PASS",
         base_packet(domain="biology",
                     BIO_RED={"orthogonal_assays_used": ["functional_assay", "biochemical_assay"]},
                     artifacts={"protocol": "see methods"},
                     BIO_VERIFY={
                         "n_replicates": 3,
                         "assay_classes": ["functional_assay", "biochemical_assay"],
                         "dose_response": {
                             "doses": [0, 1, 5, 25, 125],
                             "responses": [0.1, 0.3, 0.5, 0.8, 0.95],
                             "expected_direction": "increasing",
                         },
                     }),
         "PASS")

    test("Biology: non-monotonic without justification → REJECT",
         base_packet(domain="biology",
                     BIO_RED={"orthogonal_assays_used": ["functional_assay", "biochemical_assay"]},
                     artifacts={"protocol": "see methods"},
                     BIO_VERIFY={
                         "n_replicates": 3,
                         "assay_classes": ["functional_assay", "biochemical_assay"],
                         "dose_response": {
                             "doses": [0, 1, 5, 25, 125],
                             "responses": [0.1, 0.3, 0.2, 0.8, 0.95],
                             "expected_direction": "increasing",
                         },
                     }),
         "REJECT")

    test("Biology: underpowered sample size → REJECT",
         base_packet(domain="biology",
                     BIO_RED={"orthogonal_assays_used": ["assay_a", "assay_b"]},
                     artifacts={"protocol": "see methods"},
                     BIO_VERIFY={
                         "n_replicates": 3,
                         "assay_classes": ["assay_a", "assay_b"],
                         "power_analysis": {"effect_size": 0.5, "alpha": 0.05,
                                            "n_per_group": 20},
                     }),
         "REJECT")

    # ── Governance verifier ──
    print("\nGovernance verifier (decision packet shape):")

    test("Governance: complete decision packet → PASS",
         base_packet(domain="governance",
                     text="The board considered the proposal carefully and recorded its concerns honestly.",
                     witness_count=3,
                     DECISION_PACKET={
                         "title": "Approve Hutcheson workforce-development RFP",
                         "scope": "canon",
                         "red_items": [
                             "no coercion of employees",
                             "no exploitation of trainees",
                             "no deception in financials",
                         ],
                         "floor_items": [
                             "budget within board-approved tolerance",
                             "covenant ground-lease structure preserved",
                         ],
                         "way_path": ("Issue RFP through GNWTC partnership; scope limited to "
                                      "trades programs aligned with regional employer demand."),
                         "execution_steps": ["Draft RFP", "Board review",
                                             "Issue", "Evaluate responses"],
                         "witnesses": ["JDA Board Chair", "GNWTC President",
                                       "County Commissioner Catoosa"],
                         "scripture_anchors": ["Prov 22:16", "Mic 6:8"],
                     }),
         "PASS")

    test("Governance: incomplete decision packet → REJECT",
         base_packet(domain="governance",
                     text="The proposal is acceptable in all respects.",
                     witness_count=0,
                     DECISION_PACKET={
                         "title": "TBD",
                         "scope": "adapter",
                         "red_items": [],
                         "floor_items": [],
                         "way_path": "do it",
                         "execution_steps": [],
                         "witnesses": [],
                     }),
         "REJECT")

    test("Governance: witness count mismatch → REJECT",
         base_packet(domain="governance",
                     text="The board recorded its concerns honestly.",
                     witness_count=5,  # claimed
                     DECISION_PACKET={
                         "title": "Approve grant disbursement",
                         "scope": "mesh",
                         "red_items": ["no exploitation"],
                         "floor_items": ["budget within tolerance"],
                         "way_path": "Disburse against milestone reports per the terms of the agreement.",
                         "execution_steps": ["Verify milestones", "Sign disbursement"],
                         "witnesses": ["Board Chair", "Treasurer"],  # only 2 named
                     }),
         "REJECT")

    # ── Summary ──
    print(f"\n{'=' * 60}")
    print("All tests passed.")
    print(f"{'=' * 60}")
