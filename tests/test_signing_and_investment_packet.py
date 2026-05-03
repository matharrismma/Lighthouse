"""Tests for Ed25519 signing + Investment Packet v1.1.

Per canonical 02_SPECS/INVESTMENT_PACKET_SPEC_v1_1.md:
  > A cryptographically signed, time-bound, revocable, privacy-
  > preserving eligibility credential.
"""
from __future__ import annotations

import datetime as dt

import pytest

from concordance_engine.signing import (
    generate_keypair, public_from_private, sign_bytes, verify_bytes,
    sign_packet, verify_packet,
)
from concordance_engine.investment_packet import (
    PACKET_VERSION, hash_subject_pii, make_packet, make_and_sign,
    verify_investment_packet,
)


# ── Signing primitives ────────────────────────────────────────────────

def test_generate_keypair_produces_distinct_keys():
    priv1, pub1 = generate_keypair()
    priv2, pub2 = generate_keypair()
    assert priv1 != priv2
    assert pub1 != pub2


def test_public_derives_from_private():
    priv, pub = generate_keypair()
    assert public_from_private(priv) == pub


def test_sign_and_verify_bytes_roundtrip():
    priv, pub = generate_keypair()
    msg = b"hello, audit chain"
    sig = sign_bytes(msg, priv)
    assert verify_bytes(msg, sig, pub) is True


def test_verify_bytes_rejects_tampered_message():
    priv, pub = generate_keypair()
    sig = sign_bytes(b"original", priv)
    assert verify_bytes(b"tampered", sig, pub) is False


def test_verify_bytes_rejects_wrong_key():
    priv1, _ = generate_keypair()
    _, pub2 = generate_keypair()
    sig = sign_bytes(b"x", priv1)
    assert verify_bytes(b"x", sig, pub2) is False


# ── Packet sign / verify ──────────────────────────────────────────────

def test_sign_packet_adds_signature_field():
    priv, pub = generate_keypair()
    packet = {"domain": "test", "claim": "x", "issuer_public_key": pub}
    signed = sign_packet(packet, priv)
    assert "signature" in signed
    assert isinstance(signed["signature"], str) and len(signed["signature"]) > 0


def test_sign_packet_does_not_mutate_input():
    priv, pub = generate_keypair()
    packet = {"domain": "test", "claim": "x", "issuer_public_key": pub}
    signed = sign_packet(packet, priv)
    assert "signature" not in packet  # input unchanged
    assert signed is not packet


def test_verify_packet_passes_for_clean_signed():
    priv, pub = generate_keypair()
    packet = {"domain": "test", "claim": "x", "issuer_public_key": pub}
    signed = sign_packet(packet, priv)
    ok, detail = verify_packet(signed)
    assert ok, detail


def test_verify_packet_rejects_tampered():
    priv, pub = generate_keypair()
    signed = sign_packet({"domain": "test", "claim": "x",
                          "issuer_public_key": pub}, priv)
    tampered = dict(signed)
    tampered["claim"] = "y"
    ok, detail = verify_packet(tampered)
    assert not ok


def test_verify_packet_no_signature_returns_error():
    priv, pub = generate_keypair()
    ok, detail = verify_packet({"domain": "test", "issuer_public_key": pub})
    assert not ok
    assert "signature" in detail.lower()


def test_sign_packet_idempotent():
    """Re-signing replaces the prior signature with a fresh one over
    the current canonical content. The original signature is not part
    of the new payload, so the result is stable."""
    priv, pub = generate_keypair()
    packet = {"domain": "test", "claim": "x", "issuer_public_key": pub}
    signed1 = sign_packet(packet, priv)
    signed2 = sign_packet(signed1, priv)
    # Both verify; the signatures are equal (Ed25519 is deterministic).
    ok1, _ = verify_packet(signed1)
    ok2, _ = verify_packet(signed2)
    assert ok1 and ok2
    assert signed1["signature"] == signed2["signature"]


# ── Investment Packet ─────────────────────────────────────────────────

def _sample_packet_args():
    priv, pub = generate_keypair()
    return {
        "private_key": priv,
        "issuer": "node://test/2026-05-03",
        "issuer_public_key": pub,
        "subject_id": hash_subject_pii("test@example.com"),
        "derived_bands": {
            "income_band": "B3",
            "liquidity_band": "B2",
            "debt_band": "B1",
            "stability_band": "B4",
        },
        "proof_hashes": ["a" * 64, "b" * 64],
        "constraints": {
            "income_band_definition": "B1=<25k, B2=25-50k, B3=50-100k, B4=100k+",
        },
        "valid_for_days": 365,
    }


def test_hash_subject_pii_stable():
    """Same input always produces the same hash; hash never reveals
    raw input."""
    h1 = hash_subject_pii("alice@example.com")
    h2 = hash_subject_pii("alice@example.com")
    assert h1 == h2
    assert "alice@example.com" not in h1
    assert len(h1) == 64  # SHA-256 hex


def test_hash_subject_pii_normalizes_whitespace_and_case():
    assert hash_subject_pii("Alice@Example.com") == hash_subject_pii("alice@example.com")
    assert hash_subject_pii("  alice@example.com  ") == hash_subject_pii("alice@example.com")


def test_hash_subject_pii_rejects_empty():
    with pytest.raises(ValueError):
        hash_subject_pii()


def test_make_packet_canonical_shape():
    args = _sample_packet_args()
    args.pop("private_key")  # make_packet doesn't sign
    packet = make_packet(**args)
    assert packet["packet_version"] == PACKET_VERSION
    assert packet["issuer"] == args["issuer"]
    assert packet["subject_id"] == args["subject_id"]
    assert "issued_at" in packet
    assert "expires_at" in packet
    assert "signature" not in packet  # unsigned at this stage


def test_make_packet_rejects_missing_band_family():
    args = _sample_packet_args()
    args.pop("private_key")
    args["derived_bands"] = {"income_band": "B3"}  # missing 3 families
    with pytest.raises(ValueError, match="band families"):
        make_packet(**args)


def test_make_packet_rejects_empty_proof_hashes():
    args = _sample_packet_args()
    args.pop("private_key")
    args["proof_hashes"] = []
    with pytest.raises(ValueError, match="proof_hashes"):
        make_packet(**args)


def test_make_packet_rejects_invalid_proof_hash_format():
    args = _sample_packet_args()
    args.pop("private_key")
    args["proof_hashes"] = ["not-a-sha256"]
    with pytest.raises(ValueError, match="SHA-256"):
        make_packet(**args)


def test_make_and_sign_produces_verifiable_packet():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    assert "signature" in signed
    ok, detail, report = verify_investment_packet(signed)
    assert ok, f"{detail}\n{report}"


def test_verify_investment_packet_rejects_tampered_band():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    signed["derived_bands"]["income_band"] = "B9"  # tamper after signing
    ok, detail, _ = verify_investment_packet(signed)
    assert not ok
    assert "signature" in detail.lower()


def test_verify_investment_packet_rejects_expired():
    """A packet whose expires_at is in the past should fail verification."""
    args = _sample_packet_args()
    args["valid_for_days"] = 1
    args["issued_at"] = "2020-01-01T00:00:00+00:00"  # long ago
    signed = make_and_sign(**args)
    ok, detail, _ = verify_investment_packet(signed)
    assert not ok
    assert "expired" in detail.lower()


def test_verify_investment_packet_rejects_revoked():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    revoked = [signed["revocation_key_id"]]
    ok, detail, _ = verify_investment_packet(signed, revoked_keys=revoked)
    assert not ok
    assert "revocation" in detail.lower()


def test_verify_investment_packet_rejects_wrong_version():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    signed["packet_version"] = "0.9"
    # Re-sign so signature would be valid except for version mismatch
    from concordance_engine.signing import sign_packet as _sp
    signed = _sp(
        {k: v for k, v in signed.items() if k != "signature"},
        args["private_key"],
    )
    ok, detail, _ = verify_investment_packet(signed)
    assert not ok
    assert "version" in detail.lower()


def test_verify_investment_packet_rejects_missing_required_field():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    del signed["issuer"]
    ok, detail, _ = verify_investment_packet(signed)
    assert not ok
    assert "missing" in detail.lower()


def test_verify_investment_packet_report_contains_each_check():
    args = _sample_packet_args()
    signed = make_and_sign(**args)
    ok, detail, report = verify_investment_packet(signed)
    assert ok
    checks = report.get("checks", {})
    for k in ("required_fields", "version", "signature", "expiry", "revocation"):
        assert k in checks, f"check {k!r} missing from report"
