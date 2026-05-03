"""LSP ↔ scripture verifier integration tests.

Exercises the optional LSPCorpus integrity check that runs when
CONCORDANCE_LSP_PATH points at a corpus JSON. Without the env var, the
scripture verifier falls back to the WEB DB lookup; with it, anchor
verification additionally confirms each ref's chunk hash hasn't drifted.
"""
from __future__ import annotations

import importlib

import pytest

from concordance_engine.lsp import LSPConfig, build_lsp_corpus
from concordance_engine.verifiers import scripture as scr


@pytest.fixture
def reset_lsp_cache():
    """The corpus loader is lru_cached; clear it before & after each
    test that mutates CONCORDANCE_LSP_PATH so the env change takes."""
    scr._get_lsp_corpus.cache_clear()
    yield
    scr._get_lsp_corpus.cache_clear()


def _build_corpus_at(path, pairs):
    corpus = build_lsp_corpus(pairs, source_id="test")
    corpus.save(path)
    return corpus


def test_lsp_check_passes_for_clean_corpus(tmp_path, monkeypatch, reset_lsp_cache):
    """Anchors that resolve and hash-match should land in lsp_checks
    with status='ok' and not flip the verifier to MISMATCH."""
    corpus_path = tmp_path / "corpus.json"
    _build_corpus_at(corpus_path, [
        ("Jn 3:16", "for God so loved the world"),
        ("Mt 5:37", "let your yes be yes"),
    ])
    monkeypatch.setenv("CONCORDANCE_LSP_PATH", str(corpus_path))
    scr._get_lsp_corpus.cache_clear()

    result = scr.verify_scripture_anchors(["Jn 3:16", "Mt 5:37"])
    # WEB DB may or may not be provisioned; either way LSP checks ran.
    data = result.data or {}
    assert "lsp_checks" in data
    assert len(data["lsp_checks"]) == 2
    assert all(c["status"] == "ok" for c in data["lsp_checks"])
    assert data.get("lsp_tampered", []) == []


def test_lsp_check_detects_tampered_corpus(tmp_path, monkeypatch, reset_lsp_cache):
    """A corpus whose chunk text was altered without recomputing the
    hash must trigger MISMATCH on the scripture verifier."""
    corpus_path = tmp_path / "corpus.json"
    _build_corpus_at(corpus_path, [
        ("Jn 3:16", "for God so loved the world"),
    ])
    # Tamper the saved corpus.
    import json
    saved = json.loads(corpus_path.read_text(encoding="utf-8"))
    saved["lsp"]["chunks"][0]["text"] = "for caesar so loved the world"  # changed
    corpus_path.write_text(json.dumps(saved), encoding="utf-8")

    monkeypatch.setenv("CONCORDANCE_LSP_PATH", str(corpus_path))
    scr._get_lsp_corpus.cache_clear()

    result = scr.verify_scripture_anchors(["Jn 3:16"])
    assert result.status == "MISMATCH"
    assert "LSP integrity" in result.detail or "drift" in result.detail.lower()
    assert len((result.data or {}).get("lsp_tampered", [])) == 1


def test_no_lsp_env_means_no_lsp_data(monkeypatch, reset_lsp_cache):
    """Without CONCORDANCE_LSP_PATH, the verifier never touches LSP and
    its result data carries no lsp_checks key."""
    monkeypatch.delenv("CONCORDANCE_LSP_PATH", raising=False)
    scr._get_lsp_corpus.cache_clear()

    result = scr.verify_scripture_anchors(["Jn 3:16"])
    data = result.data or {}
    assert "lsp_checks" not in data
    assert "lsp_tampered" not in data


def test_lsp_check_skips_unindexed_ref(tmp_path, monkeypatch, reset_lsp_cache):
    """A ref not in the corpus's ref-index returns 'not_indexed' on the
    LSP side without triggering a tamper failure — the engine should
    fall back to the WEB DB result for that anchor."""
    corpus_path = tmp_path / "corpus.json"
    _build_corpus_at(corpus_path, [
        ("Jn 3:16", "for God so loved"),
    ])
    monkeypatch.setenv("CONCORDANCE_LSP_PATH", str(corpus_path))
    scr._get_lsp_corpus.cache_clear()

    result = scr.verify_scripture_anchors(["Mt 5:37"])
    data = result.data or {}
    assert any(c["status"] == "not_indexed" for c in data.get("lsp_checks", []))
    assert data.get("lsp_tampered", []) == []
