"""Agent dispatch layer — NL → domain + spec extraction.

This layer sits between raw natural language and the deterministic
verifier layer. It does two things only:
  1. Classify which domain the text is about
  2. Extract the numeric/string fields the verifier needs

It does NOT answer. It does NOT generate. It routes.

Public API:
    dispatch(text) -> DispatchResult | None
"""
from .dispatch import dispatch, DispatchResult

__all__ = ["dispatch", "DispatchResult"]
