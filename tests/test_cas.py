"""Tests for the in-house content-addressable store (CAS).

Covers: store, fetch, exists, verify, list_hashes, delete, stats,
content_hash_of stability, idempotency, and 2-char prefix layout.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from concordance_engine.cas import (
    content_hash_of,
    store,
    fetch,
    exists,
    verify,
    list_hashes,
    delete,
    stats,
)


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def cas_dir(tmp_path):
    """Isolated CAS directory per test."""
    return tmp_path / "cas"


def _store(rec, cas_dir):
    return store(rec, base_dir=cas_dir)

def _fetch(h, cas_dir):
    return fetch(h, base_dir=cas_dir)


# ── content_hash_of ───────────────────────────────────────────────────────

def test_content_hash_of_is_stable():
    rec = {"domain": "chemistry", "claims": ["H2O is water"]}
    h1 = content_hash_of(rec)
    h2 = content_hash_of(rec)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_content_hash_of_excludes_content_hash_field():
    rec = {"domain": "chemistry", "claims": ["H2O is water"]}
    h_base = content_hash_of(rec)
    rec_with_hash = dict(rec, content_hash=h_base)
    assert content_hash_of(rec_with_hash) == h_base


def test_content_hash_of_excludes_permanent_ref_field():
    rec = {"domain": "chemistry", "claims": ["H2O is water"]}
    h_base = content_hash_of(rec)
    rec_with_ref = dict(rec, permanent_ref=h_base)
    assert content_hash_of(rec_with_ref) == h_base


def test_content_hash_of_sensitive_to_content():
    rec1 = {"domain": "chemistry", "claims": ["H2O is water"]}
    rec2 = {"domain": "chemistry", "claims": ["H2O is ice"]}
    assert content_hash_of(rec1) != content_hash_of(rec2)


def test_content_hash_of_key_order_independent():
    rec_a = {"b": 2, "a": 1}
    rec_b = {"a": 1, "b": 2}
    assert content_hash_of(rec_a) == content_hash_of(rec_b)


# ── store ─────────────────────────────────────────────────────────────────

def test_store_returns_content_hash(cas_dir):
    rec = {"domain": "mathematics", "value": 42}
    h = _store(rec, cas_dir)
    assert isinstance(h, str) and len(h) == 64


def test_store_creates_2char_prefix_layout(cas_dir):
    rec = {"domain": "mathematics", "value": 99}
    h = _store(rec, cas_dir)
    expected_path = cas_dir / h[:2] / f"{h[2:]}.json"
    assert expected_path.exists()


def test_store_embeds_content_hash_in_file(cas_dir):
    rec = {"domain": "mathematics", "value": 99}
    h = _store(rec, cas_dir)
    path = cas_dir / h[:2] / f"{h[2:]}.json"
    stored = json.loads(path.read_text())
    assert stored["content_hash"] == h


def test_store_is_idempotent(cas_dir):
    rec = {"domain": "mathematics", "value": 77}
    h1 = _store(rec, cas_dir)
    h2 = _store(rec, cas_dir)
    assert h1 == h2
    assert len(list_hashes(base_dir=cas_dir)) == 1


def test_store_overwrite_replaces_file(cas_dir):
    rec = {"domain": "mathematics", "value": 1}
    h = _store(rec, cas_dir)
    path = cas_dir / h[:2] / f"{h[2:]}.json"
    original_size = path.stat().st_size
    store(rec, base_dir=cas_dir, overwrite=True)
    assert path.exists()


# ── fetch ─────────────────────────────────────────────────────────────────

def test_fetch_returns_record(cas_dir):
    rec = {"domain": "physics", "claim": "F=ma"}
    h = _store(rec, cas_dir)
    result = _fetch(h, cas_dir)
    assert result is not None
    assert result["domain"] == "physics"
    assert result["content_hash"] == h


def test_fetch_missing_returns_none(cas_dir):
    assert _fetch("a" * 64, cas_dir) is None


# ── exists ────────────────────────────────────────────────────────────────

def test_exists_true_after_store(cas_dir):
    rec = {"x": 1}
    h = _store(rec, cas_dir)
    assert exists(h, base_dir=cas_dir)


def test_exists_false_for_unknown(cas_dir):
    assert not exists("b" * 64, base_dir=cas_dir)


# ── verify ────────────────────────────────────────────────────────────────

def test_verify_passes_for_intact_record(cas_dir):
    rec = {"domain": "biology", "claim": "DNA is double-helix"}
    h = _store(rec, cas_dir)
    ok, detail = verify(h, base_dir=cas_dir)
    assert ok, detail


def test_verify_fails_for_missing_hash(cas_dir):
    ok, detail = verify("c" * 64, base_dir=cas_dir)
    assert not ok
    assert "not found" in detail


def test_verify_fails_for_tampered_file(cas_dir):
    rec = {"domain": "biology", "claim": "DNA is double-helix"}
    h = _store(rec, cas_dir)
    path = cas_dir / h[:2] / f"{h[2:]}.json"
    tampered = json.loads(path.read_text())
    tampered["claim"] = "TAMPERED"
    path.write_text(json.dumps(tampered))
    ok, detail = verify(h, base_dir=cas_dir)
    assert not ok
    assert "mismatch" in detail


# ── list_hashes ───────────────────────────────────────────────────────────

def test_list_hashes_empty_when_no_records(cas_dir):
    assert list_hashes(base_dir=cas_dir) == []


def test_list_hashes_returns_all_stored(cas_dir):
    recs = [{"i": i} for i in range(5)]
    hashes = {_store(r, cas_dir) for r in recs}
    listed = set(list_hashes(base_dir=cas_dir))
    assert hashes == listed


def test_list_hashes_is_sorted(cas_dir):
    for i in range(10):
        _store({"i": i}, cas_dir)
    hashes = list_hashes(base_dir=cas_dir)
    assert hashes == sorted(hashes)


# ── delete ────────────────────────────────────────────────────────────────

def test_delete_removes_record(cas_dir):
    rec = {"x": "to-be-deleted"}
    h = _store(rec, cas_dir)
    assert delete(h, base_dir=cas_dir)
    assert not exists(h, base_dir=cas_dir)


def test_delete_returns_false_for_missing(cas_dir):
    assert not delete("d" * 64, base_dir=cas_dir)


# ── stats ─────────────────────────────────────────────────────────────────

def test_stats_reflects_stored_records(cas_dir):
    for i in range(3):
        _store({"i": i, "data": "x" * 100}, cas_dir)
    s = stats(base_dir=cas_dir)
    assert s["count"] == 3
    assert s["total_bytes"] > 0
    assert "base_dir" in s


def test_stats_empty_cas(cas_dir):
    s = stats(base_dir=cas_dir)
    assert s["count"] == 0
    assert s["total_bytes"] == 0
