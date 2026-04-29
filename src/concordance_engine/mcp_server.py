"""Deprecated shadow file.

This module file is shadowed at import time by the ``mcp_server`` package
directory of the same name (Python prefers the package). The historical
contents have been removed to avoid maintenance drift and confusion.

The active MCP server lives at ``concordance_engine.mcp_server`` (the
package). Use ``concordance-mcp`` or ``python -m concordance_engine.mcp_server``.

This file can be deleted; it is kept only because the build environment
does not permit deletion. It is unreachable from any import path.
"""
