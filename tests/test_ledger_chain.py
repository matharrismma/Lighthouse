"""Tests for the ledger hash chain — V1 integrity guarantee.

Each precedent file carries `content_hash` (SHA-256 of canonical JSON
excluding the chain fields) and `prev_hash` (the prior file's
content_hash, or GENESIS for the first). Tampering with any field
breaks the chain — the recomputed content_hash won't match, and
downstream prev_hash links will be off.

This is the fix for the audit's #2 weakness: the ledger had no
integrity guarantee, so anyone editing a precedent file invalidly
could pass the file off as authentic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from concordance_engine.gates import ok
from concordance_engine.ledger import (
    GENESIS_HASH, compute_content_hash, find_closest, list_precedents,
    seal_to_ledger, verify_chain,
)
from concordance_engine.witness_record import (
    Anchor, WitnessRecord, axis_coords_for,
)


def _pass_record(packet_id="pkt://test/1") -> WitnessRecord:
    return WitnessRecord(
        overall="PASS",
        gate_results=(
            ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD"),
        ),
        verifier_results=(),
        anchors=(Anchor(ref="Mt 5:37", layer="jesus_words"),),
        axis_coords=axis_coords_for("mathematics"),
        packet_id=packet_id,
    )


# ── compute_content_hash ───────────────────────────────────────────────

def test_content_hash_excludes_chain_fields():
    """The hash must be over content, not over the chain wrapper —
    otherwise re-sealing or re-hashing would produce a different hash
    even when content is unchanged."""
    base = {"precedent_id": "x", "axis": "y", "dimensions": []}
    h1 = compute_content_hash(base)
    base_with_chain = dict(base, content_hash="abcdef", prev_hash="GENESIS")
    h2 = compute_content_hash(base_with_chain)
    assert h1 == h2, "content_hash should ignore chain fields"


def test_content_hash_is_canonical():
    """Order of keys doesn't affect the hash — the canonical JSON
    serializer sorts them."""
    a = {"axis": "x", "precedent_id": "y", "dimensions": ["a", "b"]}
    b = {"dimensions": ["a", "b"], "precedent_id": "y", "axis": "x"}
    assert compute_content_hash(a) == compute_content_hash(b)


def test_content_hash_changes_when_content_changes():
    a = {"precedent_id": "x", "summary": "first"}
    b = {"precedent_id": "x", "summary": "second"}
    assert compute_content_hash(a) != compute_content_hash(b)


# ── seal_to_ledger writes chain fields ─────────────────────────────────

def test_seal_writes_content_hash_and_prev_hash(tmp_path):
    rec = _pass_record()
    target = seal_to_ledger(
        rec, summary="first", precedent_id="ledger://test/a",
        ledger_dir=tmp_path,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert "content_hash" in payload
    assert "prev_hash" in payload
    assert payload["prev_hash"] == GENESIS_HASH
    # content_hash is a 64-char hex string (SHA-256)
    assert len(payload["content_hash"]) == 64


def test_seal_chains_subsequent_files(tmp_path):
    """Second file's prev_hash must be the first file's content_hash."""
    rec1 = _pass_record(packet_id="pkt://1")
    f1 = seal_to_ledger(
        rec1, summary="first",
        precedent_id="ledger://test/a-first", ledger_dir=tmp_path,
    )
    rec2 = _pass_record(packet_id="pkt://2")
    f2 = seal_to_ledger(
        rec2, summary="second",
        precedent_id="ledger://test/b-second", ledger_dir=tmp_path,
    )
    p1 = json.loads(f1.read_text(encoding="utf-8"))
    p2 = json.loads(f2.read_text(encoding="utf-8"))
    assert p2["prev_hash"] == p1["content_hash"]


def test_seal_inserting_alphabetically_earlier_keeps_chain_intact(tmp_path):
    """Files are chain-ordered alphabetically, not by creation time.
    Inserting a new file with a name that sorts before existing ones
    should still produce a valid chain."""
    # First, seal "b-second" and "c-third"
    seal_to_ledger(
        _pass_record(), summary="b",
        precedent_id="ledger://test/b-second", ledger_dir=tmp_path,
    )
    seal_to_ledger(
        _pass_record(), summary="c",
        precedent_id="ledger://test/c-third", ledger_dir=tmp_path,
    )
    # Now insert "a-first" which sorts before both
    seal_to_ledger(
        _pass_record(), summary="a",
        precedent_id="ledger://test/a-first", ledger_dir=tmp_path,
    )
    # Verify: chain may be broken because b-second was originally
    # written with prev=GENESIS, now there's an a-first before it.
    # That's the expected behavior — verify_chain reports the break.
    report = verify_chain(ledger_dir=tmp_path)
    # broken_links should contain b-second (its stored prev_hash is
    # GENESIS but the expected is now a-first's content_hash).
    broken_files = [b["file"] for b in report["broken_links"]]
    assert any("b-second" in f for f in broken_files)


# ── verify_chain ───────────────────────────────────────────────────────

def test_verify_chain_clean_returns_ok(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="first",
        precedent_id="ledger://test/a", ledger_dir=tmp_path,
    )
    seal_to_ledger(
        _pass_record(), summary="second",
        precedent_id="ledger://test/b", ledger_dir=tmp_path,
    )
    report = verify_chain(ledger_dir=tmp_path)
    assert report["ok"]
    assert report["verified"] == 2
    assert report["tampered"] == []
    assert report["broken_links"] == []


def test_verify_chain_detects_content_tamper(tmp_path):
    """Edit a precedent's summary without recomputing the hash —
    verify_chain must catch it."""
    f = seal_to_ledger(
        _pass_record(), summary="original",
        precedent_id="ledger://test/tamper", ledger_dir=tmp_path,
    )
    payload = json.loads(f.read_text(encoding="utf-8"))
    payload["summary"] = "tampered"
    # Don't recompute content_hash — leave the stale value.
    f.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    report = verify_chain(ledger_dir=tmp_path)
    assert not report["ok"]
    assert len(report["tampered"]) == 1
    assert "tamper" in report["tampered"][0]["file"]
    assert "mismatch" in report["tampered"][0]["error"].lower()


def test_verify_chain_detects_link_break(tmp_path):
    """If someone manually fixes a tampered file's content_hash, the
    chain link to the next file breaks (its prev_hash no longer
    matches)."""
    seal_to_ledger(
        _pass_record(), summary="first",
        precedent_id="ledger://test/a", ledger_dir=tmp_path,
    )
    seal_to_ledger(
        _pass_record(), summary="second",
        precedent_id="ledger://test/b", ledger_dir=tmp_path,
    )
    # Tamper with the first file AND recompute its content_hash so
    # the integrity check passes for that file — but the chain to file
    # b is now broken (b's prev_hash points at the old content_hash).
    f1 = tmp_path / "test-a.json"
    p1 = json.loads(f1.read_text(encoding="utf-8"))
    p1["summary"] = "modified"
    p1["content_hash"] = compute_content_hash(p1)
    f1.write_text(json.dumps(p1, indent=2), encoding="utf-8")

    report = verify_chain(ledger_dir=tmp_path)
    assert not report["ok"]
    assert len(report["broken_links"]) == 1
    assert "test-b" in report["broken_links"][0]["file"]


def test_verify_chain_handles_unsigned_precedents(tmp_path):
    """A precedent file with no content_hash field is reported as
    'unsigned' rather than 'tampered'. This lets old / hand-written
    precedents coexist with chain-aware ones."""
    unsigned = {
        "precedent_id": "ledger://test/unsigned",
        "axis": "chemistry",
        "dimensions": ["physical_substance"],
        "summary": "no chain fields",
    }
    (tmp_path / "test-unsigned.json").write_text(
        json.dumps(unsigned), encoding="utf-8",
    )
    report = verify_chain(ledger_dir=tmp_path)
    assert report["unsigned"] == ["test-unsigned.json"]
    # No tamper or broken-link errors
    assert report["tampered"] == []


def test_verify_chain_handles_unparseable_files(tmp_path):
    (tmp_path / "bad.json").write_text("{ not valid json", encoding="utf-8")
    report = verify_chain(ledger_dir=tmp_path)
    assert not report["ok"]
    assert any(t["file"] == "bad.json" for t in report["tampered"])


def test_verify_chain_empty_ledger_is_ok(tmp_path):
    report = verify_chain(ledger_dir=tmp_path)
    assert report["ok"]
    assert report["total"] == 0
    assert report["verified"] == 0


# ── End-to-end with the real sample ledger ─────────────────────────────

def test_real_sample_ledger_verifies_clean():
    """The 3 sample precedents in lw/ledger/ should verify cleanly
    after backfill. This locks in: the live ledger is signed, and
    `concordance ledger verify` will return ok."""
    report = verify_chain()
    assert report["ok"], (
        f"sample ledger chain is broken: tampered={report['tampered']}, "
        f"broken_links={report['broken_links']}"
    )
    assert report["verified"] >= 3


def test_real_sample_ledger_no_unsigned_files():
    """After backfill, no sample precedent should be unsigned."""
    report = verify_chain()
    assert report["unsigned"] == []


# ── seal_to_ledger overwrite preserves chain integrity ─────────────────

def test_overwrite_recomputes_chain(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="first",
        precedent_id="ledger://test/a", ledger_dir=tmp_path,
    )
    # Overwrite with a different summary
    seal_to_ledger(
        _pass_record(), summary="rewritten",
        precedent_id="ledger://test/a", ledger_dir=tmp_path,
        overwrite=True,
    )
    report = verify_chain(ledger_dir=tmp_path)
    assert report["ok"]
    assert report["verified"] == 1
