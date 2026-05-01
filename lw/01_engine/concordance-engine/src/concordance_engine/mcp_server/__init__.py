"""Concordance Engine MCP server.

Exposes the seven verifier domains plus the full engine pipeline as MCP tools.
Install with `pip install -e ".[mcp]"` and run with `concordance-mcp`.
"""
from . import tools

__all__ = ["tools"]
