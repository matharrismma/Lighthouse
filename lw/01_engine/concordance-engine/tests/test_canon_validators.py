"""Canon-validator smoke test.

Each canon directory has a `tools/validator_<domain>.py` that's a parallel
implementation of the corresponding engine validator. The canon directory
exists so it can be forked or re-implemented in another language without
dragging in the engine package.

This test confirms each canon validator imports cleanly and runs against
a representative packet. It does NOT check that the canon validator and
the engine validator agree exactly — that would require a full
equivalence proof and isn't in scope. It does catch import errors,
syntax errors, and obviously broken validators.

Run: python tests/test_canon_validators.py
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CANON_ROOT = REPO_ROOT / "02_canons"


def load_module(path: Path):
    """Load a Python file as a module by absolute path."""
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def expect_validator_runs(domain: str, validator_filename: str,
                          entry_function: str, sample_packet: dict,
                          should_pass: bool):
    """Load a canon validator and run it on a sample packet."""
    path = CANON_ROOT / domain / "tools" / validator_filename
    if not path.exists():
        return False, f"missing: {path.relative_to(REPO_ROOT)}"

    try:
        module = load_module(path)
    except Exception as e:
        return False, f"import failed: {e}"

    fn = getattr(module, entry_function, None)
    if fn is None:
        return False, f"no function {entry_function!r} in {validator_filename}"

    try:
        result = fn(sample_packet)
    except Exception as e:
        return False, f"validator raised: {e}"

    if not isinstance(result, dict):
        return False, f"validator returned {type(result).__name__}, expected dict"

    passed = result.get("passed", not result.get("errors"))
    if passed != should_pass:
        return False, (f"expected passed={should_pass}, got passed={passed}, "
                       f"errors={result.get('errors', [])}")

    return True, f"passed={passed}, errors={len(result.get('errors', []))}, " \
                 f"warnings={len(result.get('warnings', []))}"


def main():
    results = []

    # Mathematics
    good_math = {
        "MATH_RED": {
            "well_formedness": {"symbols_defined": True, "quantifiers_scoped": True,
                                "domains_declared": True},
            "type_safety": {"objects_typed": True, "operations_valid": True},
            "definitional_integrity": {"no_circular_definitions": True},
            "inference_integrity": {"rules_named": True, "steps_justified": True},
        },
        "artifacts": {"derivation": "by hand"},
    }
    results.append(("mathematics good", expect_validator_runs(
        "mathematics", "validator_mathematics.py", "validate_math_packet",
        good_math, True)))

    # Physics
    good_phys = {
        "conservation_checks": {"dimensional_consistency": {"required": True, "verified": True}},
        "units": "SI",
    }
    results.append(("physics good", expect_validator_runs(
        "physics", "validator_physics.py", "validate_physics_packet",
        good_phys, True)))

    # Biology
    good_bio = {
        "BIO_RED": {
            "non_contradiction": True,
            "conservation_declared": True,
            "second_law_respected": True,
            "causality_respected": True,
            "stoichiometry_balanced": True,
            "nonnegativity_respected": True,
            "channel_limits_respected": True,
            "orthogonal_assays_used": ["qPCR", "western_blot"],
        },
        "BIO_FLOOR": {
            "measurement_doctrine": {"controls_used": True, "calibrated": True,
                                     "uncertainty_reported": True, "replicated": True},
            "orthogonality": {"required": True,
                              "orthogonal_assays_used": ["qPCR", "western_blot"]},
            "replicates_minimum": 3, "replicates": 4,
        },
    }
    results.append(("biology good", expect_validator_runs(
        "biology", "validator_biology.py", "validate_bio_packet",
        good_bio, True)))

    # Computer Science
    good_cs = {
        "CS_RED": {"termination_proven": True, "memory_safety_addressed": True,
                   "no_undefined_behavior": True,
                   "concurrency_correctness_addressed": True},
        "CS_COMPLEXITY": {"case": "worst", "time": "O(n)", "space": "O(1)"},
    }
    results.append(("computer_science good", expect_validator_runs(
        "computer_science", "validator_computer_science.py", "validate_cs_packet",
        good_cs, True)))

    # Statistics
    good_stat = {
        "STAT_INFERENCE": {"test_specified": True, "assumptions_tested": True,
                           "p_value": 0.0003, "alpha": 0.05,
                           "effect_size": 0.5, "effect_size_type": "cohen_d",
                           "confidence_interval": [0.1, 0.9],
                           "claimed_significance": "significant",
                           "hypothesis_pre_specified": True,
                           "multiple_comparisons_corrected": True},
    }
    results.append(("statistics good", expect_validator_runs(
        "statistics", "validator_statistics.py", "validate_stats_packet",
        good_stat, True)))

    # Print summary
    passes = 0
    fails = 0
    for name, (ok, detail) in results:
        icon = "✓" if ok else "✗"
        print(f"  {icon} {name}: {detail}")
        if ok:
            passes += 1
        else:
            fails += 1

    print(f"\n{'=' * 60}")
    if fails:
        print(f"FAIL: {passes} passed, {fails} failed.")
        sys.exit(1)
    print(f"All {passes} canon-validator smoke tests passed.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
