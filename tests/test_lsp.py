"""Tests for LSP — Lighthouse Standard Pages.

Per canonical 02_SPECS/LSP_SPEC.md: deterministic chunking + per-chunk
SHA-256 hashing of input text. MVP scope (this commit) is the chunker
itself; Scripture-verifier integration is a future iteration.
"""
from __future__ import annotations

import json

import pytest

from concordance_engine.lsp import (
    DEFAULT_WORDS_PER_PAGE,
    LSPConfig,
    LSPCorpus,
    build_lsp,
    build_lsp_corpus,
    chunk_words,
    find_chunk_for_word,
    load_corpus_from_jsonl,
    normalize_text,
    verify_lsp,
)


# ── normalize_text ────────────────────────────────────────────────────

def test_normalize_collapses_whitespace():
    assert normalize_text("hello   world") == "hello world"
    assert normalize_text("hello\nworld\t!") == "hello world !"


def test_normalize_strips_leading_trailing():
    assert normalize_text("  hello world  ") == "hello world"


def test_normalize_applies_nfkc():
    """NFKC composes some Unicode forms (e.g., compatibility chars)."""
    # Halfwidth katakana → fullwidth via NFKC
    halfwidth = "ｶﾀｶﾅ"
    out = normalize_text(halfwidth)
    fullwidth = "カタカナ"
    assert out == fullwidth


def test_normalize_can_skip_nfkc():
    halfwidth = "ｶﾀｶﾅ"
    cfg = LSPConfig(nfkc=False)
    assert normalize_text(halfwidth, cfg) == halfwidth


def test_normalize_preserves_diacritics():
    """Canon §5 requires preserving original-language diacritics."""
    # Greek with accents — these must survive normalization
    greek = "λόγος ἐν ἀρχῇ"
    out = normalize_text(greek)
    # All accented characters should still be present
    for char in "όἐἀῇ":
        assert char in out


def test_normalize_empty_returns_empty():
    assert normalize_text("") == ""
    assert normalize_text(None) == ""


# ── chunk_words ───────────────────────────────────────────────────────

def test_chunk_words_basic():
    words = list("abcdefghij")
    chunks = chunk_words(words, 3)
    assert chunks == [list("abc"), list("def"), list("ghi"), list("j")]


def test_chunk_words_exact_multiple():
    words = list("abcdef")
    chunks = chunk_words(words, 3)
    assert chunks == [list("abc"), list("def")]
    assert all(len(c) == 3 for c in chunks)


def test_chunk_words_empty_input():
    assert chunk_words([], 200) == []


def test_chunk_words_rejects_zero_size():
    with pytest.raises(ValueError):
        chunk_words(["a"], 0)


# ── build_lsp ─────────────────────────────────────────────────────────

def test_build_lsp_basic_shape():
    text = "the quick brown fox jumped over the lazy dog"
    record = build_lsp(text, cfg=LSPConfig(words_per_page=3))
    assert record["lsp_version"] == "v0"
    assert record["words_per_page"] == 3
    assert record["nfkc"] is True
    assert record["total_words"] == 9
    assert record["chunk_count"] == 3
    assert len(record["chunks"]) == 3


def test_build_lsp_chunk_indices_are_correct():
    text = "the quick brown fox jumped over the lazy dog"
    record = build_lsp(text, cfg=LSPConfig(words_per_page=3))
    chunks = record["chunks"]
    assert chunks[0]["index"] == 0
    assert chunks[0]["start_word"] == 0
    assert chunks[0]["end_word"] == 2
    assert chunks[1]["index"] == 1
    assert chunks[1]["start_word"] == 3
    assert chunks[1]["end_word"] == 5
    assert chunks[2]["index"] == 2
    assert chunks[2]["start_word"] == 6
    assert chunks[2]["end_word"] == 8


def test_build_lsp_each_chunk_has_sha256():
    record = build_lsp("alpha beta gamma delta", cfg=LSPConfig(words_per_page=2))
    for chunk in record["chunks"]:
        sha = chunk["sha256"]
        assert isinstance(sha, str)
        assert len(sha) == 64  # SHA-256 hex


def test_build_lsp_is_deterministic():
    """Same input always produces same hashes."""
    text = "one fish two fish red fish blue fish"
    r1 = build_lsp(text)
    r2 = build_lsp(text)
    assert r1 == r2


def test_build_lsp_chunk_text_joinable():
    """chunk text + spaces should reconstruct the normalized whole."""
    text = "the quick brown fox jumped over the lazy dog"
    record = build_lsp(text, cfg=LSPConfig(words_per_page=3))
    rejoined = " ".join(c["text"] for c in record["chunks"])
    assert rejoined == "the quick brown fox jumped over the lazy dog"


def test_build_lsp_default_chunk_size_is_200():
    short_text = "alpha beta"
    record = build_lsp(short_text)
    assert record["words_per_page"] == DEFAULT_WORDS_PER_PAGE


def test_build_lsp_empty_text_zero_chunks():
    record = build_lsp("")
    assert record["chunk_count"] == 0
    assert record["chunks"] == []
    assert record["total_words"] == 0


def test_build_lsp_carries_source_id():
    record = build_lsp("text", source_id="LXX-Mt")
    assert record["source_id"] == "LXX-Mt"


def test_build_lsp_works_on_greek():
    """Original-language priority requires LSP to handle Greek without
    mangling diacritics or producing empty chunks."""
    # John 1:1 in Greek
    greek = "Ἐν ἀρχῇ ἦν ὁ λόγος καὶ ὁ λόγος ἦν πρὸς τὸν θεόν"
    record = build_lsp(greek, source_id="LXX-Jn1", cfg=LSPConfig(words_per_page=5))
    assert record["chunk_count"] == 3
    # First chunk should preserve diacritics
    first = record["chunks"][0]["text"]
    for char in "Ἐἀῇ":
        assert char in first


# ── verify_lsp ────────────────────────────────────────────────────────

def test_verify_lsp_clean_record():
    record = build_lsp("alpha beta gamma delta", cfg=LSPConfig(words_per_page=2))
    report = verify_lsp(record)
    assert report["ok"]
    assert report["verified"] == 2
    assert report["tampered"] == []


def test_verify_lsp_detects_tampered_chunk():
    record = build_lsp("alpha beta gamma delta", cfg=LSPConfig(words_per_page=2))
    # Tamper with chunk text WITHOUT recomputing the hash
    record["chunks"][0]["text"] = "tampered text here"
    report = verify_lsp(record)
    assert not report["ok"]
    assert len(report["tampered"]) == 1
    assert report["tampered"][0]["index"] == 0


def test_verify_lsp_empty_record():
    report = verify_lsp({"chunks": []})
    assert report["ok"]
    assert report["total"] == 0


# ── find_chunk_for_word ───────────────────────────────────────────────

def test_find_chunk_for_word_locates_correct_chunk():
    record = build_lsp(
        "a b c d e f g h i j",
        cfg=LSPConfig(words_per_page=3),
    )
    # word 0 → chunk 0
    assert find_chunk_for_word(record, 0)["index"] == 0
    # word 3 → chunk 1 (start of second chunk)
    assert find_chunk_for_word(record, 3)["index"] == 1
    # word 9 → chunk 3 (last chunk: word 9 only)
    assert find_chunk_for_word(record, 9)["index"] == 3


def test_find_chunk_for_word_out_of_range_returns_none():
    record = build_lsp("a b c", cfg=LSPConfig(words_per_page=2))
    assert find_chunk_for_word(record, 999) is None
    assert find_chunk_for_word(record, -1) is None


# ── LSPConfig validation ──────────────────────────────────────────────

def test_lsp_config_rejects_zero_size():
    with pytest.raises(ValueError):
        LSPConfig(words_per_page=0)


def test_lsp_config_rejects_negative_size():
    with pytest.raises(ValueError):
        LSPConfig(words_per_page=-1)


# ── LSPCorpus + ingest (Full LSP) ─────────────────────────────────────


def test_build_lsp_corpus_records_ref_ranges():
    """Each ref in the input maps to a contiguous word range in the
    concatenated, normalized stream."""
    pairs = [
        ("Jn 3:16", "for God so loved the world"),       # 6 words: 0-5
        ("Jn 3:17", "that he gave his only Son"),        # 6 words: 6-11
        ("Mt 5:37", "let your yes be yes"),              # 5 words: 12-16
    ]
    corpus = build_lsp_corpus(pairs, source_id="WEB-NT", cfg=LSPConfig(words_per_page=5))
    assert corpus.lookup("Jn 3:16") == (0, 5)
    assert corpus.lookup("Jn 3:17") == (6, 11)
    assert corpus.lookup("Mt 5:37") == (12, 16)
    assert corpus.lsp["total_words"] == 17
    assert corpus.source_id == "WEB-NT"


def test_build_lsp_corpus_skips_empty_text():
    pairs = [
        ("Jn 3:16", "real text here"),
        ("Jn 3:17", ""),
        ("Jn 3:18", "more text"),
    ]
    corpus = build_lsp_corpus(pairs)
    assert corpus.lookup("Jn 3:16") is not None
    assert corpus.lookup("Jn 3:17") is None
    assert corpus.lookup("Jn 3:18") is not None


def test_lsp_corpus_lookup_normalizes_ref():
    """Caller variants of the same ref resolve to the same key."""
    pairs = [("John 3:16", "the verse")]
    corpus = build_lsp_corpus(pairs)
    # Same canonical form, just different whitespace.
    assert corpus.lookup("John   3:16") == corpus.lookup("john 3:16")
    assert corpus.lookup("John 3:16.") == corpus.lookup("John 3:16")


def test_lsp_corpus_chunks_for_ref():
    """A ref straddling a chunk boundary should return both chunks."""
    pairs = [
        ("a", "one two three"),     # words 0-2
        ("b", "four five six"),     # words 3-5
        ("c", "seven eight nine"),  # words 6-8 (straddles chunk boundary)
    ]
    corpus = build_lsp_corpus(pairs, cfg=LSPConfig(words_per_page=4))
    # 9 words / 4 = chunks: [0-3], [4-7], [8-8]
    chunks_a = corpus.chunks_for_ref("a")
    assert [c["index"] for c in chunks_a] == [0]
    chunks_b = corpus.chunks_for_ref("b")
    # b is words 3-5: overlaps chunk 0 (0-3) AND chunk 1 (4-7)
    assert [c["index"] for c in chunks_b] == [0, 1]
    chunks_c = corpus.chunks_for_ref("c")
    # c is words 6-8: chunk 1 (4-7) AND chunk 2 (8-8)
    assert [c["index"] for c in chunks_c] == [1, 2]


def test_lsp_corpus_verify_anchor_ok():
    pairs = [("Jn 3:16", "for God so loved the world")]
    corpus = build_lsp_corpus(pairs)
    result = corpus.verify_anchor("Jn 3:16")
    assert result["status"] == "ok"
    assert result["chunks"] == [0]
    assert result["tampered"] == []


def test_lsp_corpus_verify_anchor_not_indexed():
    pairs = [("Jn 3:16", "for God so loved")]
    corpus = build_lsp_corpus(pairs)
    result = corpus.verify_anchor("Mt 5:37")
    assert result["status"] == "not_indexed"
    assert result["chunks"] == []


def test_lsp_corpus_verify_anchor_detects_tamper():
    pairs = [("Jn 3:16", "for God so loved the world")]
    corpus = build_lsp_corpus(pairs)
    # Tamper with the text without recomputing the hash.
    corpus.lsp["chunks"][0]["text"] = "tampered"
    result = corpus.verify_anchor("Jn 3:16")
    assert result["status"] == "tampered"
    assert len(result["tampered"]) == 1


def test_lsp_corpus_save_load_roundtrip(tmp_path):
    pairs = [
        ("Jn 3:16", "for God so loved the world"),
        ("Mt 5:37", "let your yes be yes"),
    ]
    corpus = build_lsp_corpus(pairs, source_id="test")
    target = tmp_path / "corpus.json"
    corpus.save(target)
    loaded = LSPCorpus.load(target)
    assert loaded.source_id == corpus.source_id
    assert loaded.ref_index == corpus.ref_index
    assert loaded.lsp == corpus.lsp
    # Verification still works after roundtrip.
    assert loaded.verify_anchor("Jn 3:16")["status"] == "ok"


def test_load_corpus_from_jsonl(tmp_path):
    jsonl_path = tmp_path / "corpus.jsonl"
    jsonl_path.write_text(
        '\n'.join([
            json.dumps({"ref": "Jn 3:16", "text": "for God so loved"}),
            json.dumps({"ref": "Mt 5:37", "text": "let your yes be yes"}),
        ]) + '\n',
        encoding="utf-8",
    )
    corpus = load_corpus_from_jsonl(jsonl_path, source_id="test")
    assert corpus.lookup("Jn 3:16") is not None
    assert corpus.lookup("Mt 5:37") is not None
    assert corpus.source_id == "test"


def test_load_corpus_from_jsonl_skips_malformed(tmp_path):
    jsonl_path = tmp_path / "corpus.jsonl"
    jsonl_path.write_text(
        '\n'.join([
            json.dumps({"ref": "Jn 3:16", "text": "valid"}),
            "not json at all",
            json.dumps({"ref": "no_text"}),       # missing text
            json.dumps({"text": "no_ref"}),       # missing ref
            "",
            json.dumps({"ref": "Mt 5:37", "text": "also valid"}),
        ]) + '\n',
        encoding="utf-8",
    )
    corpus = load_corpus_from_jsonl(jsonl_path)
    assert len(corpus.ref_index) == 2
    assert corpus.lookup("Jn 3:16") is not None
    assert corpus.lookup("Mt 5:37") is not None
