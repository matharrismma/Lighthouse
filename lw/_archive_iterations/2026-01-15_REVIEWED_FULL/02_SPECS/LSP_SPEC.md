# Lighthouse Standard Pages (LSP) - Spec (Current)

## Purpose
Create deterministic, page-like chunks of Scripture (or other text inputs) that:
- normalize consistently
- chunk deterministically
- hash each chunk for integrity
- allow mapping between translations to the LXX/LSP backbone

## Canonical decisions
- Primary Scripture source is **Septuagint (LXX)**.
- LSP chunks are **immutable** per version.
- Each chunk has:
  - normalization parameters
  - word-count (or token-count) boundary rules
  - SHA-256 integrity hash

## Deterministic normalization rules (v0)
1. Convert to Unicode NFKC.
2. Normalize whitespace to single spaces.
3. Strip leading/trailing whitespace.
4. Preserve original-language diacritics (do not strip accents).

## Chunking rules (v0)
- Default chunk size: **200 words** (configurable).
- Chunk boundary: strict sequential word windows.
- Output record for each chunk:
  - `index` (0-based)
  - `start_word`, `end_word` (inclusive)
  - `text`
  - `sha256`

## Reference mapping (v0)
- A translation can map to LSP by storing:
  - translation identifier
  - range mapping from translation verse markers to LSP word ranges
  - optional alignment confidence

> Note: This spec is implementable without bundling LXX text; LXX text is supplied as input during ingestion.
