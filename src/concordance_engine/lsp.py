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

**Full scope (this iteration):**
  - Deterministic NFKC normalization + whitespace collapse.
  - Strict sequential word-windowed chunking (default 200 words).
  - SHA-256 integrity hash per chunk.
  - Stable index + start_word + end_word per chunk.
  - Corpus ingest: JSONL of {ref, text} → LSP record + ref→word-range
    index, persisted as a single LSPCorpus JSON.
  - Anchor verification: given a ref, find its containing chunk(s),
    recompute the hash, confirm match. Surfaces tampering or drift
    against the canonical hash baseline.
  - Wired into scripture verifier as an optional second-tier integrity
    check (CONCORDANCE_LSP_PATH env var). Falls back to WEB DB lookup
    when no LSP corpus is provisioned.

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

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


# ── Corpus ingest + anchor verification (Full LSP) ──────────────────


# Canonical reference normalization for ref-index keys. The corpus
# stores refs as the caller supplied them (preserves "Jn 3:16" vs
# "John 3:16" provenance); lookup normalizes both sides through this
# function so caller variants resolve to the same key.
_REF_WS_RE = re.compile(r"\s+")


def _canonical_ref(ref: str) -> str:
    """Normalize a reference string for ref-index lookup.

    Lowercases, collapses whitespace, strips trailing punctuation. Does
    not attempt book-name canonicalization — that's the scripture
    verifier's job (it has the canon table). LSP's role is integrity
    over text bytes, not theological/linguistic resolution."""
    if not ref:
        return ""
    out = _REF_WS_RE.sub(" ", str(ref)).strip().lower()
    return out.rstrip(".,;")


@dataclass
class LSPCorpus:
    """An LSP record plus a ref→(start_word, end_word) index.

    The combination is what makes a ref-shaped anchor like "Mt 5:37"
    verifiable: the ref-index maps the human reference to a word range,
    `find_chunk_for_word` maps the word range to chunk(s), and
    `verify_lsp` confirms the chunk hashes haven't drifted.

    Persisted as a single JSON file: {lsp: ..., ref_index: {ref: [start, end]}}.
    Loadable via `LSPCorpus.load(path)`.
    """
    lsp: Dict[str, Any]
    ref_index: Dict[str, List[int]] = field(default_factory=dict)
    source_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lsp_corpus_version": "v0",
            "source_id": self.source_id,
            "lsp": self.lsp,
            "ref_index": {k: list(v) for k, v in self.ref_index.items()},
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LSPCorpus":
        return cls(
            lsp=d.get("lsp", {}),
            ref_index={k: list(v) for k, v in (d.get("ref_index") or {}).items()},
            source_id=d.get("source_id", ""),
        )

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path

    @classmethod
    def load(cls, path: Path) -> "LSPCorpus":
        path = Path(path)
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def lookup(self, ref: str) -> Optional[Tuple[int, int]]:
        """Resolve a reference to its (start_word, end_word) range.
        Returns None if the ref isn't in the index."""
        rng = self.ref_index.get(_canonical_ref(ref))
        if rng is None or len(rng) < 2:
            return None
        return int(rng[0]), int(rng[1])

    def chunks_for_ref(self, ref: str) -> List[Dict[str, Any]]:
        """Return every chunk that overlaps the ref's word range.
        Empty list if the ref isn't indexed or has no overlapping chunks."""
        rng = self.lookup(ref)
        if rng is None:
            return []
        start_word, end_word = rng
        out: List[Dict[str, Any]] = []
        for chunk in self.lsp.get("chunks") or []:
            c_start = chunk.get("start_word", 0)
            c_end = chunk.get("end_word", -1)
            if c_end < c_start:
                continue
            # Overlap: not (c_end < start_word or c_start > end_word)
            if not (c_end < start_word or c_start > end_word):
                out.append(chunk)
        return out

    def verify_anchor(self, ref: str) -> Dict[str, Any]:
        """Verify a single reference resolves AND its chunks haven't drifted.

        Returns:
          {
            "ref": str,
            "canonical_ref": str,
            "status": "ok" | "not_indexed" | "tampered",
            "chunks": [chunk_index, ...],
            "tampered": [{index, expected, recomputed}],  # if any
          }
        """
        canonical = _canonical_ref(ref)
        rng = self.lookup(ref)
        if rng is None:
            return {
                "ref": ref,
                "canonical_ref": canonical,
                "status": "not_indexed",
                "chunks": [],
                "tampered": [],
            }
        chunks = self.chunks_for_ref(ref)
        tampered: List[Dict[str, Any]] = []
        chunk_indices: List[int] = []
        for c in chunks:
            chunk_indices.append(c.get("index", -1))
            stored = c.get("sha256", "")
            recomputed = sha256_bytes(c.get("text", "").encode("utf-8"))
            if stored != recomputed:
                tampered.append({
                    "index": c.get("index"),
                    "expected": stored[:12] + "...",
                    "recomputed": recomputed[:12] + "...",
                })
        return {
            "ref": ref,
            "canonical_ref": canonical,
            "word_range": list(rng),
            "status": "tampered" if tampered else "ok",
            "chunks": chunk_indices,
            "tampered": tampered,
        }


def build_lsp_corpus(
    refs_with_text: Iterable[Tuple[str, str]],
    *,
    source_id: str = "",
    cfg: Optional[LSPConfig] = None,
) -> LSPCorpus:
    """Build an LSPCorpus from an iterable of (ref, text) tuples.

    Texts are concatenated in order with single-space joins. The
    ref-index records the word-range each ref's text occupies in the
    concatenated, normalized stream. Chunks straddle ref boundaries —
    that's intentional: hashing is over the chunk window, not per-ref,
    so chunks preserve canonical word-window invariants regardless of
    how the source was carved into refs.

    Empty texts are skipped. Duplicate refs overwrite earlier entries
    (so callers can call this with a deduped pipeline upstream)."""
    cfg = cfg or LSPConfig()
    pieces: List[str] = []
    ref_index: Dict[str, List[int]] = {}
    word_cursor = 0

    for raw_ref, raw_text in refs_with_text:
        text = normalize_text(raw_text, cfg)
        if not text:
            continue
        words = text.split(" ")
        n = len(words)
        if n == 0:
            continue
        start = word_cursor
        end = word_cursor + n - 1
        ref_index[_canonical_ref(raw_ref)] = [start, end]
        pieces.append(text)
        word_cursor += n

    full_text = " ".join(pieces)
    lsp_record = build_lsp(full_text, source_id=source_id, cfg=cfg)
    return LSPCorpus(
        lsp=lsp_record,
        ref_index=ref_index,
        source_id=source_id,
    )


def load_corpus_from_jsonl(
    path: Path,
    *,
    source_id: str = "",
    cfg: Optional[LSPConfig] = None,
) -> LSPCorpus:
    """Build an LSPCorpus from a JSONL file where each line is a JSON
    object with `ref` and `text` keys.

    Lines that are blank, malformed JSON, or missing ref/text are
    silently skipped — ingest is best-effort over potentially noisy
    public-domain corpora. The line index is preserved in input order
    so the resulting corpus is deterministic per-file."""
    path = Path(path)
    pairs: List[Tuple[str, str]] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict):
                continue
            ref = obj.get("ref")
            text = obj.get("text")
            if not isinstance(ref, str) or not isinstance(text, str):
                continue
            pairs.append((ref, text))
    return build_lsp_corpus(pairs, source_id=source_id, cfg=cfg)


__all__ = [
    "LSPConfig",
    "DEFAULT_WORDS_PER_PAGE",
    "normalize_text",
    "chunk_words",
    "build_lsp",
    "verify_lsp",
    "find_chunk_for_word",
    "LSPCorpus",
    "build_lsp_corpus",
    "load_corpus_from_jsonl",
]
