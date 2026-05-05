"""Personal context retriever — Layer 3 of the standalone model.

Reads the individual user's kept data from the Concordance Engine ledger
and applies it as a RAG overlay on top of the Scripture retrieval.

What the overlay produces: specificity. The Scripture anchor is universal.
The path is personal. The intersection of the two is the output.

A user asking a timing question who has kept six packets over the past year
about the same unresolved decision receives a different path than a user
asking the same question for the first time. The model sees the pattern.
The path reflects it.

Phase 1: reads journal entries and sealed precedents. Surfaces:
  - Entry count on the current theme
  - Dominant Scripture anchors in prior entries
  - Detected pattern (recurring theme, unresolved thread)
  - Most recent relevant precedent

The caller is responsible for user authentication; this module receives
a pre-authorized `base_dir` or journal/ledger stores directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ── Data types ─────────────────────────────────────────────────────────

@dataclass
class PersonalContext:
    """Personal context overlay for the current submission.

    relevant_count  — number of prior entries on the same theme
    pattern         — human-readable pattern description (populated after ≥3)
    recurring_anchors — Scripture refs that appear repeatedly in prior entries
    most_recent_precedent — the closest sealed precedent, if any
    first_seen_at   — epoch of earliest entry on this theme (0 if none)
    unresolved      — True when the theme has been kept without a sealed outcome
    """
    relevant_count: int = 0
    pattern: Optional[str] = None
    recurring_anchors: list[str] = field(default_factory=list)
    most_recent_precedent: Optional[dict] = None
    first_seen_at: float = 0.0
    unresolved: bool = False

    @property
    def has_history(self) -> bool:
        return self.relevant_count > 0

    def to_dict(self) -> dict:
        return {
            "relevant_packets": self.relevant_count,
            "pattern": self.pattern,
            "recurring_anchors": self.recurring_anchors,
            "precedent": self.most_recent_precedent,
            "first_seen_at": self.first_seen_at,
            "unresolved": self.unresolved,
        }


# ── Theme extraction ───────────────────────────────────────────────────
# Simple keyword extraction from the submission. Used to search prior
# entries for thematic similarity. Phase 2 replaces this with vector
# similarity over packet embeddings.

_STOPWORDS = frozenset(
    "i a an the is are was were be been being have has had do does did "
    "will would could should may might shall must can not no nor and or "
    "but for so yet of in on at to from with by about into through "
    "this that these those my me my we us our you your he she it they "
    "his her its their just also how what when where why who which "
    "want feel think know see need help understand god lord jesus christ".split()
)


def _keywords(text: str, top_n: int = 8) -> list[str]:
    """Extract meaningful keywords from text for theme matching."""
    words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
    counts: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS:
            counts[w] = counts.get(w, 0) + 1
    return [w for w, _ in sorted(counts.items(), key=lambda x: -x[1])][:top_n]


def _theme_overlap(keywords: list[str], text: str) -> int:
    """Return count of keyword matches in text."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if re.search(r"\b" + re.escape(kw) + r"\b", text_lower))


# ── Anchor extraction from journal entries ─────────────────────────────

def _anchors_from_entry(entry: dict) -> list[str]:
    """Extract Scripture references from a journal entry dict."""
    refs: list[str] = []
    # Annotations and detected anchors
    for ann in entry.get("annotations", []):
        ref = ann.get("ref") or ann.get("text", "")
        if ref and re.search(r"\d", ref):    # has a chapter:verse
            refs.append(ref)
    # scripture_anchors field
    for a in entry.get("scripture_anchors", []):
        if isinstance(a, str):
            refs.append(a)
        elif isinstance(a, dict) and "ref" in a:
            refs.append(a["ref"])
    return refs


# ── Core retrieval ─────────────────────────────────────────────────────

def retrieve_context(
    text: str,
    question_type: str,
    base_dir: Optional[Path] = None,
    min_overlap: int = 2,
) -> PersonalContext:
    """Retrieve personal context for the current submission.

    Args:
        text:          The raw user submission.
        question_type: Classified question type (used to boost relevance
                       of same-type prior entries).
        base_dir:      Data directory root. Defaults to ~/.concordance.
                       Reads journal/ and the ledger chain from here.
        min_overlap:   Minimum keyword overlap to count as thematically
                       related.

    Returns:
        PersonalContext with pattern summary and relevant prior entries.
    """
    keywords = _keywords(text)
    if not keywords:
        return PersonalContext()

    # Locate journal store.
    if base_dir is None:
        from pathlib import Path as _P
        import os
        base_dir = _P(os.environ.get("CONCORDANCE_DATA_DIR", "~/.concordance")).expanduser()

    journal_dir = base_dir / "journal"
    if not journal_dir.exists():
        return PersonalContext()

    # Load journal entries (lightweight: only scan text + metadata).
    import json
    relevant_entries: list[dict] = []

    for fp in sorted(journal_dir.glob("*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True):
        try:
            with fp.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    entry_text = entry.get("text", "") + " " + entry.get("summary", "")
                    if _theme_overlap(keywords, entry_text) >= min_overlap:
                        relevant_entries.append(entry)
        except OSError:
            continue

    if not relevant_entries:
        return PersonalContext()

    # Sort by creation time.
    relevant_entries.sort(key=lambda e: e.get("created_at", 0.0))
    first_seen = relevant_entries[0].get("created_at", 0.0)
    count = len(relevant_entries)

    # Collect recurring Scripture anchors.
    anchor_freq: dict[str, int] = {}
    for entry in relevant_entries:
        for ref in _anchors_from_entry(entry):
            anchor_freq[ref] = anchor_freq.get(ref, 0) + 1
    # Return refs that appear in ≥2 entries, sorted by frequency.
    recurring = [ref for ref, n in sorted(anchor_freq.items(), key=lambda x: -x[1]) if n >= 2]

    # Look for a sealed precedent that matches (via ledger chain).
    precedent = _find_matching_precedent(keywords, base_dir)

    # Build pattern description (only when ≥3 entries).
    pattern: Optional[str] = None
    if count >= 3:
        import datetime
        first_dt = datetime.datetime.fromtimestamp(first_seen).strftime("%B %Y")
        pattern = (
            f"This is submission {count} on this theme. "
            f"The thread has been present since {first_dt}. "
            f"The pattern shows the question has been carried longer than the urgency suggests."
        )
    elif count == 2:
        pattern = "This is the second submission on this theme. A pattern is beginning to form."

    # Unresolved: theme exists in journal but no sealed precedent yet.
    unresolved = count > 0 and precedent is None

    return PersonalContext(
        relevant_count=count,
        pattern=pattern,
        recurring_anchors=recurring[:5],
        most_recent_precedent=precedent,
        first_seen_at=first_seen,
        unresolved=unresolved,
    )


def _find_matching_precedent(keywords: list[str], base_dir: Path) -> Optional[dict]:
    """Find a sealed precedent that matches the current theme keywords."""
    import json

    # Check fetched_precedents/ and the main ledger for a match.
    search_dirs = [
        base_dir / "fetched_precedents",
    ]
    # Also check the repo ledger if available.
    try:
        from .ledger import _default_ledger_dir
        search_dirs.append(_default_ledger_dir())
    except Exception:
        pass

    best: Optional[dict] = None
    best_overlap = 0

    for d in search_dirs:
        if not d.exists():
            continue
        for fp in d.glob("*.json"):
            try:
                with fp.open(encoding="utf-8") as fh:
                    prec = json.load(fh)
            except (json.JSONDecodeError, OSError):
                continue
            prec_text = (
                prec.get("summary", "") + " "
                + prec.get("description", "") + " "
                + prec.get("title", "")
            )
            ov = _theme_overlap(keywords, prec_text)
            if ov > best_overlap:
                best_overlap = ov
                best = prec

    return best if best_overlap >= 2 else None
