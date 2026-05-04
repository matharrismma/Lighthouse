"""Tests for Ed25519 witness attestations + federation push.

Distinct from test_witness.py — that's the domain verifier (witness
as one of the 36 axes). This is the cryptographic witness signature
module: a witness signs the canonical bytes of {precedent_id,
entry_hash, signed_at} with their Ed25519 private key, producing a
verifiable proof-of-attestation.

Federation push (/chain/receive) is the inverse of /chain/since:
peers push their sealed precedents to us instead of us pulling.
Tested here because it's the substrate-counterpart to witness
attestations — once a witness signs, the attestation can travel
across instances via push.

These tests skip if `cryptography` isn't installed since signing
requires it.
"""
from __future__ import annotations

import dataclasses
import json
import time

import pytest


# Skip the entire module if cryptography is unavailable.
cryptography = pytest.importorskip("cryptography")


from concordance_engine import signing, witness


# ── Witness sign + verify ──────────────────────────────────────────


def test_sign_then_verify_round_trips():
    priv, _pub = signing.generate_keypair()
    att = witness.sign(
        precedent_id="ledger://test/abc",
        entry_hash="deadbeef",
        private_key_b64u=priv,
        witness_name="Alice",
        witness_role="elder",
    )
    ok, reason = witness.verify(att)
    assert ok, reason


def test_tampered_attestation_fails_verify():
    """Changing any signed field after the fact must invalidate."""
    priv, _pub = signing.generate_keypair()
    att = witness.sign(
        precedent_id="ledger://test/abc",
        entry_hash="original",
        private_key_b64u=priv,
        witness_name="Alice",
        witness_role="elder",
    )

    # Tamper precedent_id.
    bad = dataclasses.replace(att, precedent_id="ledger://test/different")
    ok, reason = witness.verify(bad)
    assert not ok
    assert "signature" in reason.lower() or "verify" in reason.lower()

    # Tamper entry_hash.
    bad = dataclasses.replace(att, entry_hash="modified")
    ok, _ = witness.verify(bad)
    assert not ok

    # Tamper signed_at.
    bad = dataclasses.replace(att, signed_at=att.signed_at + 1)
    ok, _ = witness.verify(bad)
    assert not ok


def test_required_fields_validation():
    priv, _pub = signing.generate_keypair()
    with pytest.raises(ValueError):
        witness.sign(
            precedent_id="",
            entry_hash="h",
            private_key_b64u=priv,
            witness_name="x",
            witness_role="y",
        )
    with pytest.raises(ValueError):
        witness.sign(
            precedent_id="p",
            entry_hash="",
            private_key_b64u=priv,
            witness_name="x",
            witness_role="y",
        )


# ── Verify from dict (typical wire format) ─────────────────────────


def test_verify_dict_from_serialized():
    priv, _pub = signing.generate_keypair()
    att = witness.sign(
        precedent_id="ledger://test/abc",
        entry_hash="hash",
        private_key_b64u=priv,
        witness_name="Alice",
        witness_role="elder",
    )
    raw = json.dumps(att.to_dict())
    d = json.loads(raw)
    ok, reason = witness.verify_dict(d)
    assert ok, reason


def test_verify_dict_malformed_returns_failure():
    ok, reason = witness.verify_dict({"not": "a real attestation"})
    assert not ok
    assert any(k in reason.lower() for k in ("malformed", "missing", "key"))


# ── Append + list ──────────────────────────────────────────────────


def test_append_and_list(tmp_path):
    priv, _pub = signing.generate_keypair()
    pid = "ledger://test/abc"
    att1 = witness.sign(
        precedent_id=pid, entry_hash="h", private_key_b64u=priv,
        witness_name="Alice", witness_role="elder",
    )
    att2 = witness.sign(
        precedent_id=pid, entry_hash="h", private_key_b64u=priv,
        witness_name="Bob", witness_role="brother",
    )
    witness.append(att1, base_dir=tmp_path)
    witness.append(att2, base_dir=tmp_path)
    out = witness.list_for_precedent(pid, base_dir=tmp_path)
    assert len(out) == 2
    names = {a.witness_name for a in out}
    assert names == {"Alice", "Bob"}


def test_list_empty_when_no_file(tmp_path):
    out = witness.list_for_precedent("ledger://nonexistent", base_dir=tmp_path)
    assert out == []


# ── Federation push (/chain/receive) ───────────────────────────────


def test_chain_receive_accepts_valid_entries():
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/chain/receive", json={
        "from": "http://peer.example.test",
        "entries": [
            {"seq": 100, "packet_id": "p/100", "entry_hash": "h100", "overall": "PASS"},
            {"seq": 101, "packet_id": "p/101", "entry_hash": "h101", "overall": "PASS"},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["from"] == "http://peer.example.test"
    assert data["accepted"] == 2
    assert data["rejected"] == []
    assert data["next_seq"] == 101


def test_chain_receive_rejects_malformed():
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/chain/receive", json={
        "from": "http://peer.example.test",
        "entries": [
            {"seq": 1, "packet_id": "p/1", "entry_hash": "h1"},
            {"seq": 2},  # missing packet_id
            "not a dict",  # malformed
            {"packet_id": "p/3", "entry_hash": "h3"},  # missing seq
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert data["accepted"] == 1
    assert len(data["rejected"]) == 3
    reasons = [r.get("reason", "") for r in data["rejected"]]
    assert any("packet_id" in r for r in reasons)
    assert any("dict" in r for r in reasons)
    assert any("seq" in r for r in reasons)


def test_chain_receive_requires_from():
    from fastapi.testclient import TestClient
    from api.app import app
    c = TestClient(app)
    r = c.post("/chain/receive", json={"entries": []})
    assert r.status_code == 400
