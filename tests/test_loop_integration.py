"""Integration tests for the seal → axis-index → precedent-retrieval loop.

Covers:
  - update_index + find_closest basic round-trip
  - Jaccard partial matching and scoring
  - min_score threshold filtering
  - deduplication (re-indexing same hash updates in place)
  - PolymathicRecord.closest_precedent field in to_dict() / from_dict()
  - query_index and index_stats
  - Empty-index guard (no crash, returns None)

Isolation: monkeypatch redirects _INDEX_PATH to a tmp file per test.
No network calls. No oracle calls.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

import concordance_engine.axis_index as ai_mod
from concordance_engine.axis_index import (
    find_closest,
    index_stats,
    query_index,
    update_index,
)
from concordance_engine.poly_record import PolymathicRecord


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_index(tmp_path, monkeypatch):
    """Redirect _INDEX_PATH to an isolated tmp file for every test."""
    idx_path = tmp_path / "axis_index.json"
    monkeypatch.setattr(ai_mod, "_INDEX_PATH", idx_path)
    yield idx_path


# ── update_index / find_closest round-trip ────────────────────────────────────

def test_find_closest_returns_none_on_empty_index():
    result = find_closest(["authority_trust", "time_sequence"])
    assert result is None


def test_update_and_find_exact_match():
    dims = ["authority_trust", "time_sequence", "conservation_balance"]
    update_index("abc123", "CONCORDANT", "Test situation A", dims)
    result = find_closest(dims)
    assert result is not None
    assert result["hash"] == "abc123"
    assert result["verdict"] == "CONCORDANT"
    assert result["jaccard_score"] == 1.0


def test_find_closest_partial_jaccard():
    all_dims = ["authority_trust", "time_sequence", "conservation_balance", "encoding"]
    update_index("abc123", "CONCORDANT", "Situation A", all_dims)
    # Query with subset — Jaccard = 2/4 = 0.5
    result = find_closest(["authority_trust", "time_sequence"])
    assert result is not None
    assert result["hash"] == "abc123"
    assert result["jaccard_score"] == pytest.approx(0.5, abs=0.01)
    assert "authority_trust" in result["shared_dims"]
    assert "time_sequence" in result["shared_dims"]


def test_find_closest_min_score_filters_weak_match():
    # Record has 4 dims; query only shares 1 → Jaccard = 1/7 ≈ 0.143
    update_index("weak1", "MIXED", "Weak match", ["authority_trust", "d2", "d3", "d4"])
    result = find_closest(["authority_trust", "x1", "x2", "x3"], min_score=0.20)
    assert result is None


def test_find_closest_selects_higher_jaccard_among_candidates():
    update_index("low", "MIXED", "Low overlap", ["authority_trust", "d1", "d2", "d3"])
    update_index("high", "CONCORDANT", "High overlap", ["authority_trust", "time_sequence"])
    result = find_closest(["authority_trust", "time_sequence"])
    assert result is not None
    assert result["hash"] == "high"


def test_update_index_deduplicates_same_hash():
    dims = ["authority_trust"]
    update_index("dup_hash", "CONCORDANT", "First version", dims)
    update_index("dup_hash", "DISCORDANT", "Updated version", dims)
    stats = index_stats()
    assert stats["unique_records"] == 1
    result = find_closest(dims)
    assert result is not None
    assert result["verdict"] == "DISCORDANT"
    assert result["summary"] == "Updated version"


def test_update_index_multi_dim_indexing():
    dims = ["d1", "d2", "d3"]
    update_index("multi", "CONCORDANT", "Multi-dim record", dims)
    stats = index_stats()
    assert "d1" in stats["dimensions"]
    assert "d2" in stats["dimensions"]
    assert "d3" in stats["dimensions"]


# ── query_index ───────────────────────────────────────────────────────────────

def test_query_index_returns_matching_entries():
    update_index("r1", "CONCORDANT", "Record 1", ["auth", "time"])
    update_index("r2", "MIXED", "Record 2", ["time", "encoding"])
    update_index("r3", "DISCORDANT", "Record 3", ["encoding"])
    results = query_index(["auth"])
    hashes = {r["hash"] for r in results}
    assert "r1" in hashes
    assert "r2" not in hashes
    assert "r3" not in hashes


def test_query_index_no_duplicates_across_dims():
    dims = ["d1", "d2"]
    update_index("shared", "CONCORDANT", "Shared record", dims)
    results = query_index(["d1", "d2"])
    hashes = [r["hash"] for r in results]
    assert hashes.count("shared") == 1


def test_query_index_empty_dims_returns_empty():
    update_index("r1", "CONCORDANT", "Record 1", ["auth"])
    assert query_index([]) == []


# ── index_stats ───────────────────────────────────────────────────────────────

def test_index_stats_empty():
    s = index_stats()
    assert s["dimension_count"] == 0
    assert s["unique_records"] == 0
    assert s["total_entries"] == 0


def test_index_stats_reflects_stored():
    update_index("h1", "CONCORDANT", "Rec 1", ["d1", "d2"])
    update_index("h2", "MIXED", "Rec 2", ["d2", "d3"])
    s = index_stats()
    assert s["unique_records"] == 2
    assert s["dimension_count"] == 3  # d1, d2, d3
    assert s["total_entries"] == 4    # h1×2 dims + h2×2 dims


# ── PolymathicRecord.closest_precedent integration ────────────────────────────

def _make_record(**kw) -> PolymathicRecord:
    defaults = dict(
        situation="Test situation",
        domain_results=(),
        composite_verdict="CONCORDANT",
        axis_overlaps=(),
        atomic_claims=(),
        quarantined_claims=(),
        keeper_manifest=None,
        closest_precedent=None,
        subject_pubkey=None,
        permanent_ref=None,
    )
    defaults.update(kw)
    return PolymathicRecord(**defaults)


def test_closest_precedent_round_trips_through_dict():
    precedent_data = {
        "hash": "deadbeef01",
        "verdict": "CONCORDANT",
        "summary": "Prior run summary",
        "jaccard_score": 0.75,
        "shared_dims": ["authority_trust", "time_sequence"],
        "dims": ["authority_trust", "time_sequence", "encoding"],
        "sealed_at": 999999,
    }
    rec = _make_record(closest_precedent=precedent_data)
    d = rec.to_dict()
    assert d["closest_precedent"] == precedent_data

    rec2 = PolymathicRecord.from_dict(d)
    assert rec2.closest_precedent == precedent_data


def test_closest_precedent_none_survives_round_trip():
    rec = _make_record(closest_precedent=None)
    d = rec.to_dict()
    assert d.get("closest_precedent") is None
    rec2 = PolymathicRecord.from_dict(d)
    assert rec2.closest_precedent is None


def test_seal_loop_simulation(tmp_path, monkeypatch):
    """Simulate: run 1 seals a record → run 2 finds it as precedent."""
    # Run 1: index a sealed record
    dims_run1 = ["authority_trust", "time_sequence", "conservation_balance"]
    update_index("sealed_hash_001", "CONCORDANT", "Prior situation text", dims_run1)

    # Run 2: new situation shares 2 of 3 dims
    dims_run2 = ["authority_trust", "time_sequence", "encoding"]
    result = find_closest(dims_run2)
    assert result is not None
    assert result["hash"] == "sealed_hash_001"
    assert result["verdict"] == "CONCORDANT"
    assert set(result["shared_dims"]) == {"authority_trust", "time_sequence"}
    # Jaccard = 2 shared / (3+3-2) = 2/4 = 0.5
    assert result["jaccard_score"] == pytest.approx(0.5, abs=0.01)


def test_index_is_persistent_across_calls(tmp_path, monkeypatch):
    """update_index writes to disk; a fresh find_closest reads it back."""
    dims = ["auth", "time"]
    update_index("persist_test", "CONCORDANT", "Persistent record", dims)

    # Reload from disk by clearing any in-memory state via a fresh call
    result = find_closest(dims)
    assert result is not None
    assert result["hash"] == "persist_test"
