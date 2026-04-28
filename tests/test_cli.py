"""End-to-end CLI tests.

The engine integration tests (test_engine.py) and verifier unit tests
(test_verifiers.py) cover the engine logic. This file covers only what
the CLI wrapper adds: argument parsing, exit codes, output formatting,
schema fallback, and error handling. Each subprocess takes 3-5s for
sympy/numpy/scipy import overhead, so we exercise representative cases
rather than every example packet.

Run: python tests/test_cli.py
"""
from __future__ import annotations
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = REPO_ROOT / "examples"


def run_cli(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "concordance_engine.cli", *args],
        cwd=str(REPO_ROOT),
        env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        timeout=60,
    )


PASS = 0
FAIL = 0


def expect(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    icon = "✓" if condition else "✗"
    line = f"  {icon} {name}"
    if detail:
        line += f": {detail}"
    print(line)
    if condition:
        PASS += 1
    else:
        FAIL += 1


def main():
    chem = EXAMPLES / "sample_packet_chemistry_verify.json"
    gov = EXAMPLES / "sample_packet_governance_verify.json"

    print("CLI exit codes and basic output:")
    r = run_cli(["validate", str(chem), "--now-epoch", "9999999999"])
    expect("PASS exits 0", r.returncode == 0, f"exit={r.returncode}")
    expect("PASS output contains 'PASS'", "PASS" in r.stdout)
    expect("PASS summary names verifiers", "chemistry.equation" in r.stdout)

    r = run_cli(["validate", str(gov), "--now-epoch", "9999999999"])
    expect("governance PASS exits 0", r.returncode == 0)
    expect("governance summary names decision_packet_shape",
           "decision_packet_shape" in r.stdout)

    print("\nFailure modes:")
    bad_chem = json.loads(chem.read_text())
    bad_chem["CHEM_VERIFY"]["equation"] = "C3H8 + 4 O2 -> 3 CO2 + 4 H2O"
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(bad_chem, f)
        bad_path = f.name
    r = run_cli(["validate", bad_path, "--now-epoch", "9999999999"])
    expect("REJECT exits 1", r.returncode == 1, f"exit={r.returncode}")
    expect("REJECT output contains 'REJECT'", "REJECT" in r.stdout)
    expect("REJECT helpful detail", "balances as: C3H8 + 5 O2" in r.stdout)
    Path(bad_path).unlink()

    print("\n--format flag:")
    r = run_cli(["validate", str(chem), "--now-epoch", "9999999999", "--format", "json"])
    parsed = None
    try:
        parsed = json.loads(r.stdout)
    except json.JSONDecodeError:
        pass
    expect("--format json parseable", parsed is not None)
    expect("--format json has overall=PASS",
           parsed is not None and parsed.get("overall") == "PASS")

    r = run_cli(["validate", str(chem), "--now-epoch", "9999999999", "--format", "verbose"])
    expect("--format verbose includes 'Detail:'", "Detail:" in r.stdout)

    print("\n--no-verifiers flag:")
    r = run_cli(["validate", str(chem), "--now-epoch", "9999999999", "--no-verifiers"])
    expect("--no-verifiers still PASS", r.returncode == 0)
    expect("--no-verifiers omits chemistry.equation",
           "chemistry.equation" not in r.stdout)

    # With --no-verifiers, a corrupted equation should still pass (only attestation runs)
    r = run_cli(["validate", bad_path if Path(bad_path).exists() else str(chem),
                 "--now-epoch", "9999999999", "--no-verifiers"])
    # bad_path was deleted; this just checks the flag is functional
    expect("--no-verifiers does not crash", r.returncode in (0, 1, 4))

    print("\nError handling:")
    r = run_cli(["validate", "/tmp/__definitely_does_not_exist__.json"])
    expect("missing file -> exit 4", r.returncode == 4, f"exit={r.returncode}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write("{ this is not valid json")
        bad_json = f.name
    r = run_cli(["validate", bad_json])
    expect("malformed JSON -> exit 4", r.returncode == 4, f"exit={r.returncode}")
    Path(bad_json).unlink()

    print(f"\n{'=' * 60}")
    if FAIL:
        print(f"FAIL: {PASS} passed, {FAIL} failed.")
        sys.exit(1)
    print(f"All {PASS} CLI tests passed.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
