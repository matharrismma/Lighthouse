"""Shim: launch the canonical concordance-engine MCP server.

The real implementation lives in ``concordance_engine.mcp_server.server``.
This file exists only so existing instructions that reference a top-level
launcher ("python concordance_mcp_server.py") keep working. The supported
invocation is ``concordance-mcp`` (installed via ``pip install -e .[mcp]``).
"""
import sys
from pathlib import Path

# Make ``src/`` importable when launched directly.
_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from concordance_engine.mcp_server.server import main  # noqa: E402

if __name__ == "__main__":
    main()
