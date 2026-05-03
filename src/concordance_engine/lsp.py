"""LSP — Lighthouse Standard Pages.

Per canonical 02_SPECS/LSP_SPEC.md:

  > Create deterministic, page-like chunks of Scripture (or other text
  > inputs) that:
  >   - normalize consistently
  >   - chunk deterministically
  >   - hash each chunk for integrity
  >   - allow mapping between translations to the LXX/LSP backbone

The engine's anchor system means much more when the anchor target is
a hashed canonical chunk, not a regex-matched verse string. LSP is
the substrate that gives "Mt 5:37 (jesus_words)" a verifiable address
that can't drift between editions, translations, or transcription
accidents.

**MVP scope (this commit):**
  - Deterministic NFKC normalization + whitespace collapse.
  - Strict sequential word-windowed chunking (default 200 words).
  - SHA-256 integrity hash per chunk.
  - Stable index + start_word + end_word per chunk.
  - Caller provides text; no LXX/MorphGNT corpus is bundled.
  - Scripture verifier integration is NOT in MVP — stays a future
    "Integrated" iteration.

Canonical normalization rules (LSP_SPEC.md v0):
  1. Convert to Unicode NFKC.
  2. Normalize whitespace to single spaces.
  3. Strip leading/trailing whitespace.
  4. Preserve original-language diacritics (do not strip accents).

Per canon §5 (PRIMARY_RULESET.md): "For cryptography, numeric/pattern
analysis, and Scripture tooling — original source languages first
(Greek/Hebrew etc.). English is explanatory only." The chunker
preserves diacritics by design so it works on Greek/Hebrew without
mangling original-language tokens.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .validate import sha256_bytes


# Default chunk size from LSP_SPEC.md v0.
DEFAULT_WORDS_PER_PAGE = 200

# LSP_SPEC.md v0 — preserve diacritics; do not strip accents.
# The whitespace regex collapses runs of any Unicode whitespace
# (including non-breaking spaces, zero-width spaces in Hebrew/Greek
# inputs) without touching combining marks.
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


@dataclass(frozen=True)
class LSPConfig:
    """Configuration for an LSP build. Frozen so a build's params are
    captured immutably alongside its output."""
    words_per_page: int = DEFAULT_WORDS_PER_PAGE
    nfkc: bool = True

    def __post_init__(self):
        if self.words_per_page < 1:
            raise ValueError(
                f"words_per_page must be >= 1, got {self.words_per_page}"
            )


def normalize_text(text: str, cfg: Optional[LSPConfig] = None) -> str:
    """Apply LSP-canonical normalization to a raw text string.

    Steps (per LSP_SPEC.md v0):
      1. NFKC normalize (compose canonical Unicode forms).
      2. Collapse all whitespace runs to single spaces.
      3. Strip leading/trailing whitespace.
      4. Preserve diacritics (no accent stripping).

    Returns the normalized string. Empty input returns empty.
    """
    cfg = cfg or LSPConfig()
    if not text:
        return ""
    if cfg.nfkc:
        text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def chunk_words(words: List[str], words_per_page: int) -> List[List[str]]:
    """Strict sequential word-window chunking. The final chunk may be
    smaller than `words_per_page` if `len(words)` isn't a clean multiple."""
    if words_per_page < 1:
        raise ValueError(f"words_per_page must be >= 1, got {words_per_page}")
    return [
        words[i: i + words_per_page]
        for i in range(0, len(words), words_per_page)
    ]


def build_lsp(
    text: str,
    *,
    source_id: str = "",
    cfg: Optional[LSPConfig] = None,
) -> Dict[str, Any]:
    """Build an LSP record from a raw text string.

    Returns a dict with:
      - source_id: opaque caller-supplied identifier (e.g. "LXX-Mt")
      - words_per_page: chunk size used
      - nfkc: whether NFKC was applied
      - total_words: count of words after normalization
      - chunks: list of per-chunk records with:
          * index (0-based)
          * start_word (inclusive)
          * end_word (inclusive; -1 if chunk is empty)
          * text (the chunk's text, single-spaced)
          * sha256 (hex string of UTF-8-encoded chunk text)

    The chunks are immutable per (text, cfg, source_id) — same input
    always produces the same hashes. Recipients can verify a single
    chunk by recomputing its sha256 over its text bytes.

    Empty text returns an LSP record with zero chunks.
    """
    cfg = cfg or LSPConfig()
    normalized = normalize_text(text, cfg)
    words = normalized.split(" ") if normalized else []
    chunked = chunk_words(words, cfg.words_per_page)

    out_chunks: List[Dict[str, Any]] = []
    for i, group in enumerate(chunked):
        start = i * cfg.words_per_page
        end = start + len(group) - 1 if group else start - 1
        chunk_text = " ".join(group)
        out_chunks.append({
            "index": i,
            "start_word": start,
            "end_word": end,
            "text": chunk_text,
            "sha256": sha256_bytes(chunk_text.encode("utf-8")),
        })

    return {
        "lsp_version": "v0",
        "source_id": source_id,
        "words_per_page": cfg.words_per_page,
        "nfkc": cfg.nfkc,
        "total_words": len(words),
        "chunk_count": len(out_chunks),
        "chunks": out_chunks,
    }


def verify_lsp(lsp: Dict[str, Any]) -> Dict[str, Any]:
    """Recompute hashes for every chunk in an LSP record and confirm
    they match. Catches tampering or transcription drift on a stored
    LSP. Returns a structured report:
      {
        "ok": bool,
        "total": int,
        "verified": int,
        "tampered": [{index, expected, recomputed}],
      }
    """
    report: Dict[str, Any] = {
        "ok": True,
        "total": 0,
        "verified": 0,
        "tampered": [],
    }
    chunks = lsp.get("chunks") or []
    report["total"] = len(chunks)
    for c in chunks:
        text = c.get("text", "")
        stored = c.get("sha256", "")
        recomputed = sha256_bytes(text.encode("utf-8"))
        if stored == recomputed:
            report["verified"] += 1
        else:
            report["tampered"].append({
                "index": c.get("index"),
                "expected": stored[:12] + "...",
                "recomputed": recomputed[:12] + "...",
            })
            report["ok"] = False
    return report


def find_chunk_for_word(
    lsp: Dict[str, Any], word_index: int,
) -> Optional[Dict[str, Any]]:
    """Locate the chunk that contains a given word index. Useful when a
    translation maps a verse range into LSP word ranges and we want to
    find which chunks cover that range."""
    if word_index < 0:
        return None
    for chunk in lsp.get("chunks") or []:
        start = chunk.get("start_word", 0)
        end = chunk.get("end_word", -1)
        if start <= word_index <= end:
            return chunk
    return None


__all__ = [
    "LSPConfig",
    "DEFAULT_WORDS_PER_PAGE",
    "normalize_text",
    "chunk_words",
    "build_lsp",
    "verify_lsp",
    "find_chunk_for_word",
]
