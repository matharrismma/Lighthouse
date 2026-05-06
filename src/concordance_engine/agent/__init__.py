"""Agent dispatch layer — NL → domain + spec extraction.

Two-tier architecture:

  Tier 1 — Rule-based dispatch (dispatch.py):
    Fast, deterministic, zero API calls. Regex rules classify the text and
    extract the spec. First match wins. Covers common patterns for all 48 domains.
    Run this first. Return immediately if a rule matches.

  Tier 2 — Oracle (claude_agent.py):
    Claude tool use. Called only when no regex rule matches. Routes the claim
    via Claude to the appropriate verify_* tool, executes the tool, and returns
    the engine's deterministic verdict. Logs every call to data/agent_training/
    so rule_extractor.py can propose new regex rules to promote into Tier 1.

The two tiers together form a self-improving dispatch layer: every oracle call
that succeeds is a training example for a future deterministic rule.

Public API:
    # Tier 1
    from concordance_engine.agent import dispatch, DispatchResult

    # Tier 2
    from concordance_engine.agent import verify_claim

    # Cross-domain axis graph
    from concordance_engine.agent import DOMAIN_AXES, adjacent_domains, axes_for_domain
"""
from .dispatch import dispatch, DispatchResult
from .claude_agent import (
    verify_claim,
    DOMAIN_AXES,
    adjacent_domains,
    axes_for_domain,
)

__all__ = [
    "dispatch",
    "DispatchResult",
    "verify_claim",
    "DOMAIN_AXES",
    "adjacent_domains",
    "axes_for_domain",
]
