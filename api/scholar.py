"""scholar.py — compatibility re-export.

The scholarly-grounding logic now lives in the SOVEREIGN engine package
(`concordance_engine.scholar`) so it ships with — and is importable from — the
standalone stdio MCP server, which has no access to the `api` app layer. Moving
it there fixed the MCP bug where `scholar` failed with "No module named 'api'"
over stdio.

This module stays as a thin re-export so every existing caller
(`from api import scholar`) keeps working unchanged: the REST endpoint, the
workspace intake route, tests. It is stdlib-only and adds no dependency.
"""
from __future__ import annotations

from concordance_engine.scholar import (  # noqa: F401  (re-exported API)
    MAILTO,
    by_doi,
    by_title,
    lookup,
    search,
)

__all__ = ["lookup", "search", "by_doi", "by_title", "MAILTO"]
