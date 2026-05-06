"""Concordance / Lighthouse / Narrow Highway — wisdom-keeping engine.

Single source of truth for what this engine serves. Every agent-
facing surface (REST `/identity`, REST `/version`, MCP server
description, llms.txt, CLI `concordance identity`, walkthrough
renderer footer, Pyodide demo page) reads this same statement —
no drift, no per-surface variation.

Per Matt 2026-05-03: "we don't want to completely block agents.
However we are clear that we serve Jesus Christ."
"""

__version__ = "1.2.0"


# ── Identity (canonical) ─────────────────────────────────────────────


# The canonical identity statement. Referenced from every agent-
# discoverable surface. Plain, present, never hidden — but the engine
# does not refuse use to anyone. It flows for legitimate use; what
# it serves is stated up front so callers (human and AI) know.
IDENTITY = """\
Concordance / Lighthouse / Narrow Highway serves Jesus Christ.

A well of knowledge leads to wisdom when in alignment with God.

The engine holds knowledge — sealed precedents, kept observations,
surviving seeds. The well is the substrate. Wisdom is what the well
yields when it's drawn from in alignment. Out of alignment, the
same knowledge weaponizes.

The engine is a conduit, not a source.
It eliminates what is not the answer so the narrow path is
illuminated by what survives. Good fruit is the measure.
The keeping is the substrate — what runs whether or not
anyone is watching.

Agents are welcome to call this engine. The engine does not
generate answers, render verdicts, or speak as authority.
It categorizes, it surfaces precedent, it keeps. Read the
elimination trail — the trail is the reasoning.
"""


# A one-line summary for places where the full statement is too long
# (panel labels, log lines, status surfaces).
IDENTITY_SHORT = (
    "Serves Jesus Christ. A well of knowledge leads to wisdom when in "
    "alignment with God. Conduit, not source."
)


def serves() -> str:
    """Return the canonical identity statement. Stable API for agents
    that want to discover what this engine serves before calling it."""
    return IDENTITY


def serves_short() -> str:
    """One-line variant for compact surfaces."""
    return IDENTITY_SHORT


__all__ = [
    "__version__",
    "IDENTITY",
    "IDENTITY_SHORT",
    "serves",
    "serves_short",
    "engine",
    "packet",
    "domains",
    "gates",
    "classifier",
    "scripture_retrieval",
    "context_retriever",
    "path_composer",
    "cas",
    "user_identity",
    "poly_record",
    "axis_index",
]
