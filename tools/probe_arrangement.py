"""probe_arrangement.py — make the gaps DO the search (honestly), as a CLI.

The map's arrangement is a placeholder to truth (api/placeholders.py) that
ADVANCES ONLY BY SURVIVING its own disconfirmers. This runs them against the
LIVE grid and reports survived / weakened / untestable, plainly — the
exploration term of the search made real. Map never launders: an inconvenient
result is reported as found.

The probe core now lives in api/arrangement.py so the operator (this CLI), a
person, and an agent (GET /grid/probe, MCP `arrangement_probe`) all run the same
honest test. This file is a thin wrapper.

    PYTHONPATH=src python tools/probe_arrangement.py
"""
from __future__ import annotations

import os
import sys

# Make the probe runnable as a plain script: put repo root (for `api`) and src
# (for `concordance_engine`) on the path regardless of cwd / PYTHONPATH.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.arrangement import probe, fmt

if __name__ == "__main__":
    print(fmt(probe()))
