"""Shim for tests so `from lighthouse_all import ...` works when run from 05_TESTS."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
code = root / "04_CODE"
sys.path.insert(0, str(code))

from lighthouse_all import *  # noqa
