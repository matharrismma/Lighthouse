"""Auto-rule extraction — mine oracle training logs for regex candidates.

When the rule-based dispatcher misses and the oracle picks up the call,
the interaction is logged to data/agent_training/{domain}.jsonl.  Every
confirmed oracle hit (oracle resolved domain + spec, verifier returned
CONFIRMED) is a positive training example.

This module reads those logs and produces regex pattern candidates that
could be promoted into dispatch.py.  Promotion is always manual — we
surface proposals for review, never auto-edit dispatch.py.

Public API:
    extract_proposals(training_dir) -> List[RuleProposal]
    load_training_examples(training_dir) -> Dict[domain, List[Example]]
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class TrainingExample:
    domain: str
    text: str
    spec: Dict[str, Any]
    summary: str
    source: str


@dataclass
class RuleProposal:
    domain: str
    pattern: str
    example_texts: List[str]
    support: int          # number of training examples matched by this pattern
    confidence: float     # fraction of texts where this domain was confirmed
    spec_keys: List[str]  # spec fields this pattern would need to extract
    note: str = ""


def load_training_examples(
    training_dir: str | Path = "data/agent_training",
) -> Dict[str, List[TrainingExample]]:
    """Load all training examples from JSONL files, keyed by domain."""
    base = Path(training_dir)
    by_domain: Dict[str, List[TrainingExample]] = {}
    if not base.exists():
        return by_domain
    for path in sorted(base.glob("*.jsonl")):
        domain = path.stem
        examples: List[TrainingExample] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                e = json.loads(stripped)
                if e.get("source", "rule") == "oracle" and e.get("text"):
                    examples.append(TrainingExample(
                        domain=domain,
                        text=e["text"],
                        spec=e.get("spec") or {},
                        summary=e.get("summary", "UNKNOWN"),
                        source=e.get("source", "oracle"),
                    ))
            except json.JSONDecodeError:
                continue
        if examples:
            by_domain[domain] = examples
    return by_domain


def _common_tokens(texts: List[str]) -> List[str]:
    """Return tokens that appear in >= 50% of texts (case-insensitive)."""
    if not texts:
        return []
    counts: Dict[str, int] = {}
    for text in texts:
        seen: set = set()
        for tok in re.findall(r"[a-zA-Z_]{3,}", text.lower()):
            if tok not in seen:
                counts[tok] = counts.get(tok, 0) + 1
                seen.add(tok)
    threshold = max(1, len(texts) // 2)
    return sorted(t for t, c in counts.items() if c >= threshold)


def _spec_keys_for(examples: List[TrainingExample]) -> List[str]:
    """Return spec keys that appear in >= half the examples."""
    if not examples:
        return []
    counts: Dict[str, int] = {}
    for ex in examples:
        for k in ex.spec:
            counts[k] = counts.get(k, 0) + 1
    threshold = max(1, len(examples) // 2)
    return sorted(k for k, c in counts.items() if c >= threshold)


def _build_pattern_for_domain(
    domain: str,
    examples: List[TrainingExample],
) -> Optional[RuleProposal]:
    """Generate a single candidate pattern for a domain from its training texts."""
    confirmed = [e for e in examples if e.summary == "CONFIRMED"]
    if not confirmed:
        return None

    texts = [e.text for e in confirmed]
    tokens = _common_tokens(texts)
    if not tokens:
        tokens = [domain.replace("_", " ")]

    # Build an alternation pattern from the top 5 most discriminating tokens.
    top = tokens[:5]
    alt = "|".join(re.escape(t) for t in top)
    pattern = rf"(?:{alt})"

    # Verify the pattern actually matches most of the training texts.
    try:
        rx = re.compile(pattern, re.IGNORECASE)
        matched = [t for t in texts if rx.search(t)]
        support = len(matched)
        confidence = support / len(texts) if texts else 0.0
    except re.error:
        return None

    if support == 0:
        return None

    spec_keys = _spec_keys_for(confirmed)

    return RuleProposal(
        domain=domain,
        pattern=pattern,
        example_texts=texts[:5],
        support=support,
        confidence=confidence,
        spec_keys=spec_keys,
        note=(
            f"Derived from {len(confirmed)} oracle-confirmed examples. "
            f"To promote: add a @_rule decorator in dispatch.py with this pattern "
            f"and a spec-extraction function for keys: {spec_keys}."
        ),
    )


def extract_proposals(
    training_dir: str | Path = "data/agent_training",
    min_examples: int = 2,
    min_confidence: float = 0.5,
) -> List[RuleProposal]:
    """Extract rule proposals from oracle training logs.

    Only domains with >= min_examples confirmed oracle hits and a pattern
    confidence >= min_confidence are returned.  Proposals are sorted by
    confidence descending (highest-value rules first).

    Args:
        training_dir: Path to the agent_training directory.
        min_examples: Minimum oracle-confirmed examples required per domain.
        min_confidence: Minimum fraction of training texts that must match.

    Returns:
        List of RuleProposal dataclass instances, best first.
    """
    by_domain = load_training_examples(training_dir)
    proposals: List[RuleProposal] = []
    for domain, examples in by_domain.items():
        confirmed = [e for e in examples if e.summary == "CONFIRMED"]
        if len(confirmed) < min_examples:
            continue
        proposal = _build_pattern_for_domain(domain, examples)
        if proposal is None:
            continue
        if proposal.confidence < min_confidence:
            continue
        proposals.append(proposal)
    proposals.sort(key=lambda p: p.confidence, reverse=True)
    return proposals
