"""Tests for the personal identity module (user Ed25519 keypair).

Covers: keypair generation + persistence, sign/verify, subject_pubkey
binding in sealed WitnessRecords.

Key path is redirected via CONCORDANCE_USER_KEY_PATH env var so tests
never touch the real ~/.concordance/user_key.json.
"""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_key(tmp_path, monkeypatch):
    """Redirect key storage to a temp path and clear the in-memory cache."""
    key_path = tmp_path / "user_key.json"
    monkeypatch.setenv("CONCORDANCE_USER_KEY_PATH", str(key_path))
    # Clear the module-level cache so each test gets a fresh state.
    import concordance_engine.user_identity as ui
    ui._CACHED = None
    yield key_path
    ui._CACHED = None


# ── Keypair generation ─────────────────────────────────────────────────────

def test_get_user_key_generates_file(isolated_key):
    from concordance_engine.user_identity import get_user_key
    key = get_user_key()
    assert isolated_key.exists()
    assert key["version"] == 1
    assert "public_key_b64u" in key
    assert "private_key_b64u" in key
    assert "user_id" in key


def test_get_user_key_is_persistent(isolated_key):
    from concordance_engine.user_identity import get_user_key
    key1 = get_user_key()
    key2 = get_user_key()
    assert key1["public_key_b64u"] == key2["public_key_b64u"]
    assert key1["user_id"] == key2["user_id"]


def test_get_user_pubkey_returns_string(isolated_key):
    from concordance_engine.user_identity import get_user_pubkey
    pub = get_user_pubkey()
    assert isinstance(pub, str)
    assert len(pub) > 0


def test_get_user_id_returns_string(isolated_key):
    from concordance_engine.user_identity import get_user_id
    uid = get_user_id()
    assert isinstance(uid, str)
    assert len(uid) > 0


def test_user_key_has_ed25519_algorithm_field(isolated_key):
    from concordance_engine.user_identity import get_user_key
    key = get_user_key()
    assert key.get("algorithm", "Ed25519") == "Ed25519"


# ── sign_dict / verify_dict ───────────────────────────────────────────────

def test_sign_dict_adds_signature_fields(isolated_key):
    from concordance_engine.user_identity import sign_dict
    data = {"domain": "mathematics", "value": 42}
    signed = sign_dict(data)
    assert "_user_sig" in signed
    assert "_subject_pubkey" in signed
    assert signed["domain"] == "mathematics"


def test_verify_dict_passes_for_valid_sig(isolated_key):
    from concordance_engine.user_identity import sign_dict, verify_dict
    data = {"domain": "mathematics", "value": 42}
    signed = sign_dict(data)
    ok, detail = verify_dict(signed)
    assert ok, detail


def test_verify_dict_fails_for_tampered_data(isolated_key):
    from concordance_engine.user_identity import sign_dict, verify_dict
    data = {"domain": "mathematics", "value": 42}
    signed = sign_dict(data)
    signed["value"] = 99  # tamper
    ok, detail = verify_dict(signed)
    assert not ok


def test_verify_dict_fails_without_sig_fields(isolated_key):
    from concordance_engine.user_identity import verify_dict
    ok, detail = verify_dict({"domain": "math", "value": 1})
    assert not ok


# ── subject_pubkey binding in WitnessRecord ───────────────────────────────

def test_bind_subject_sets_pubkey():
    from concordance_engine.witness_record import WitnessRecord, bind_subject
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    bound = bind_subject(rec, "test_pubkey_abc")
    assert bound.subject_pubkey == "test_pubkey_abc"


def test_bind_subject_preserves_other_fields():
    from concordance_engine.witness_record import WitnessRecord, bind_subject
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(),
        verifier_results=(),
        packet_id="pkt://test",
        schema_version="1.1",
    )
    bound = bind_subject(rec, "pk")
    assert bound.packet_id == "pkt://test"
    assert bound.schema_version == "1.1"
    assert bound.overall == "PASS"


def test_subject_pubkey_appears_in_to_dict():
    from concordance_engine.witness_record import WitnessRecord, bind_subject
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    bound = bind_subject(rec, "pubkey_xyz")
    d = bound.to_dict()
    assert d["subject_pubkey"] == "pubkey_xyz"


def test_subject_pubkey_absent_when_not_set():
    from concordance_engine.witness_record import WitnessRecord
    rec = WitnessRecord(overall="PASS", gate_results=(), verifier_results=())
    d = rec.to_dict()
    assert "subject_pubkey" not in d
