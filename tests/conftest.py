"""Make the script-style test files collectable by pytest.

Each `tests/test_*.py` file uses a top-level imperative harness that calls
`expect()` / `sys.exit()` instead of declaring `def test_*`. To preserve the
original layout while gaining pytest discovery, we expose one wrapper test
per file that re-executes the script in a subprocess and asserts exit code 0.

Run either way:
  PYTHONPATH=src python tests/test_engine.py    # legacy script mode
  pytest tests/                                  # pytest collection
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"

SCRIPT_TESTS = [
    "test_engine.py",
    "test_verifiers.py",
    "test_cli.py",
    "test_mcp_tools.py",
    "test_canon_validators.py",
]


@pytest.mark.parametrize("script_name", SCRIPT_TESTS)
def test_script(script_name):
    script = REPO_ROOT / "tests" / script_name
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (str(SRC) + os.pathsep + pp) if pp else str(SRC)
    proc = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        pytest.fail(f"{script_name} exited {proc.returncode}\n"
                    f"--- stdout ---\n{proc.stdout}\n"
                    f"--- stderr ---\n{proc.stderr}")
