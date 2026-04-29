"""Canon-validator smoke test.

Run: python tests/test_canon_validators.py
Set CONCORDANCE_CANON_ROOT to override canon discovery; otherwise the test
probes top-level ``canons/``, ``lw/02_canons/``, and historical paths.
"""
from __future__ import annotations
import importlib.util
import os
import sys
from pathlib import Path


def _resolve_canon_root() -> Path:
    here = Path(__file__).resolve()
    env = os.environ.get("CONCORDANCE_CANON_ROOT")
    candidates = []
    if env:
        candidates.append(Path(env))
    for ancestor in [here.parent, *here.parents]:
        candidates.append(ancestor / "canons")
        candidates.append(ancestor / "02_canons")
        candidates.append(ancestor / "lw" / "02_canons")
    for c in candidates:
        if (c / "biology" / "tools").exists() or (c / "mathematics" / "tools").exists():
            return c
    return here.parents[3] / "02_canons" if len(here.parents) > 3 else here.parent


REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_ROOT = _resolve_canon_root()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def expect_validator_runs(domain, validator_filename, entry_function,
                           sample_packet, should_pass):
    path = CANON_ROOT / domain / "tools" / validator_filename
    if not path.exists():
        try:
            rel = path.relative_to(REPO_ROOT)
        except ValueError:
            rel = path
        return False, f"missing: {rel}"
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
    return True, f"passed={passed}, errors={len(result.get('errors', []))}, warnings={len(result.get('warnings', []))}"


def main():
    results = []

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

    good_phys = {
        "conservation_checks": {"dimensional_consistency": {"required": True, "verified": True}},
        "units": "SI",
    }
    results.append(("physics good", expect_validator_runs(
        "physics", "validator_physics.py", "validate_physics_packet",
        good_phys, True)))

    good_bio = {
        "BIO_RED": {
            "non_contradiction": True, "conservation_declared": True,
            "second_law_respected": True, "causality_respected": True,
            "stoichiometry_balanced": True, "nonnegativity_respected": True,
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

    good_cs = {
        "CS_RED": {"termination_proven": True, "memory_safety_addressed": True,
                   "no_undefined_behavior": True,
                   "concurrency_correctness_addressed": True},
        "CS_COMPLEXITY": {"case": "worst", "time": "O(n)", "space": "O(1)"},
    }
    results.append(("computer_science good", expect_validator_runs(
        "computer_science", "validator_computer_science.py", "validate_cs_packet",
        good_cs, True)))

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

    passes = 0
    fails = 0
    for name, (ok, detail) in results:
        icon = "OK" if ok else "FAIL"
        print(f"  [{icon}] {name}: {detail}")
        if ok:
            passes += 1
        else:
            fails += 1

    print("\n" + "=" * 60)
    if fails:
        print(f"FAIL: {passes} passed, {fails} failed.")
        print(f"  CANON_ROOT was: {CANON_ROOT}")
        sys.exit(1)
    print(f"All {passes} canon-validator smoke tests passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
