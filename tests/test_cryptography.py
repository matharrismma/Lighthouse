"""Tests for the cryptography verifier."""
from __future__ import annotations
import hashlib
import hmac

from concordance_engine.verifiers import cryptography as crypto


# ── hash_match ─────────────────────────────────────────────────────────

def test_hash_match_sha256_hello():
    expected = hashlib.sha256(b"hello").hexdigest()
    r = crypto.verify_hash_match({
        "hash_algorithm": "sha256", "data": "hello", "claimed_hash_hex": expected,
    })
    assert r.status == "CONFIRMED"


def test_hash_match_uppercase_hex_accepted():
    expected = hashlib.sha256(b"abc").hexdigest().upper()
    r = crypto.verify_hash_match({
        "hash_algorithm": "sha256", "data": "abc", "claimed_hash_hex": expected,
    })
    assert r.status == "CONFIRMED"


def test_hash_match_wrong_hash_caught():
    r = crypto.verify_hash_match({
        "hash_algorithm": "sha256", "data": "hello",
        "claimed_hash_hex": "0" * 64,
    })
    assert r.status == "MISMATCH"


def test_hash_match_unknown_algo_is_error():
    r = crypto.verify_hash_match({
        "hash_algorithm": "fake256", "data": "hello",
        "claimed_hash_hex": "0" * 64,
    })
    assert r.status == "ERROR"


# ── hash_strength ──────────────────────────────────────────────────────

def test_hash_strength_md5_broken():
    r = crypto.verify_hash_strength({
        "hash_strength_algorithm": "md5", "claimed_hash_strength": "broken",
    })
    assert r.status == "CONFIRMED"


def test_hash_strength_sha256_strong():
    r = crypto.verify_hash_strength({
        "hash_strength_algorithm": "sha256", "claimed_hash_strength": "strong",
    })
    assert r.status == "CONFIRMED"


def test_hash_strength_sha1_broken():
    r = crypto.verify_hash_strength({
        "hash_strength_algorithm": "sha1", "claimed_hash_strength": "broken",
    })
    assert r.status == "CONFIRMED"


def test_hash_strength_md5_claimed_strong_is_mismatch():
    r = crypto.verify_hash_strength({
        "hash_strength_algorithm": "md5", "claimed_hash_strength": "strong",
    })
    assert r.status == "MISMATCH"


# ── hmac_match ─────────────────────────────────────────────────────────

def test_hmac_match_sha256():
    key = b"secret"
    data = b"hello"
    expected = hmac.new(key, data, "sha256").hexdigest()
    r = crypto.verify_hmac_match({
        "hmac_algorithm": "sha256",
        "hmac_key": "secret", "hmac_data": "hello",
        "claimed_hmac_hex": expected,
    })
    assert r.status == "CONFIRMED"


def test_hmac_match_wrong_key_mismatch():
    expected = hmac.new(b"wrong", b"hello", "sha256").hexdigest()
    r = crypto.verify_hmac_match({
        "hmac_algorithm": "sha256",
        "hmac_key": "secret", "hmac_data": "hello",
        "claimed_hmac_hex": expected,
    })
    assert r.status == "MISMATCH"


# ── encoding_roundtrip ─────────────────────────────────────────────────

def test_encoding_roundtrip_base64():
    # 'hello' base64 = 'aGVsbG8='
    r = crypto.verify_encoding_roundtrip({
        "encoded": "aGVsbG8=", "encoded_form": "base64",
        "claimed_decoded": "hello",
    })
    assert r.status == "CONFIRMED"


def test_encoding_roundtrip_hex():
    # 'hi' hex = '6869'
    r = crypto.verify_encoding_roundtrip({
        "encoded": "6869", "encoded_form": "hex",
        "claimed_decoded": "hi",
    })
    assert r.status == "CONFIRMED"


def test_encoding_roundtrip_wrong_decode_caught():
    r = crypto.verify_encoding_roundtrip({
        "encoded": "aGVsbG8=", "encoded_form": "base64",
        "claimed_decoded": "world",
    })
    assert r.status == "MISMATCH"


def test_encoding_roundtrip_invalid_base64_is_error():
    r = crypto.verify_encoding_roundtrip({
        "encoded": "%%%not-base64%%%", "encoded_form": "base64",
        "claimed_decoded": "anything",
    })
    assert r.status == "ERROR"


def test_encoding_roundtrip_unknown_form_is_error():
    r = crypto.verify_encoding_roundtrip({
        "encoded": "abc", "encoded_form": "rot13",
        "claimed_decoded": "abc",
    })
    assert r.status == "ERROR"


# ── key_strength ───────────────────────────────────────────────────────

def test_key_strength_aes_256_strong():
    r = crypto.verify_key_strength({
        "cipher": "AES", "key_bits": 256, "claimed_key_strength": "strong",
    })
    assert r.status == "CONFIRMED"


def test_key_strength_aes_128_strong():
    r = crypto.verify_key_strength({
        "cipher": "AES", "key_bits": 128, "claimed_key_strength": "strong",
    })
    assert r.status == "CONFIRMED"


def test_key_strength_aes_64_weak():
    r = crypto.verify_key_strength({
        "cipher": "AES", "key_bits": 64, "claimed_key_strength": "weak",
    })
    assert r.status == "CONFIRMED"


def test_key_strength_rsa_2048_strong():
    r = crypto.verify_key_strength({
        "cipher": "RSA", "key_bits": 2048, "claimed_key_strength": "strong",
    })
    assert r.status == "CONFIRMED"


def test_key_strength_rsa_1024_weak():
    r = crypto.verify_key_strength({
        "cipher": "RSA", "key_bits": 1024, "claimed_key_strength": "weak",
    })
    assert r.status == "CONFIRMED"


def test_key_strength_wrong_claim_caught():
    r = crypto.verify_key_strength({
        "cipher": "RSA", "key_bits": 1024, "claimed_key_strength": "strong",
    })
    assert r.status == "MISMATCH"


def test_key_strength_negative_bits_is_error():
    r = crypto.verify_key_strength({
        "cipher": "AES", "key_bits": -1, "claimed_key_strength": "weak",
    })
    assert r.status == "ERROR"


# ── run() dispatch ─────────────────────────────────────────────────────

def test_run_with_no_artifacts_returns_na():
    r = crypto.run({"domain": "cryptography"})
    assert len(r) == 1
    assert r[0].status == "NOT_APPLICABLE"


def test_run_dispatches_all_applicable_checks():
    expected_hash = hashlib.sha256(b"hello").hexdigest()
    expected_hmac = hmac.new(b"k", b"d", "sha256").hexdigest()
    packet = {
        "domain": "cryptography",
        "CRYPTO_VERIFY": {
            "hash_algorithm": "sha256", "data": "hello",
            "claimed_hash_hex": expected_hash,
            "hash_strength_algorithm": "sha256",
            "claimed_hash_strength": "strong",
            "hmac_algorithm": "sha256",
            "hmac_key": "k", "hmac_data": "d",
            "claimed_hmac_hex": expected_hmac,
            "encoded": "aGVsbG8=", "encoded_form": "base64",
            "claimed_decoded": "hello",
            "cipher": "AES", "key_bits": 256,
            "claimed_key_strength": "strong",
        },
    }
    results = crypto.run(packet)
    statuses = [(r.name, r.status) for r in results]
    assert len(results) == 5, statuses
    assert all(s == "CONFIRMED" for (_, s) in statuses), statuses


def test_engine_dispatches_cryptography_domain():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "cryptography",
        "CRYPTO_VERIFY": {
            "hash_strength_algorithm": "md5",
            "claimed_hash_strength": "broken",
        },
    }
    results = run_for_domain("cryptography", packet)
    crypto_results = [r for r in results if r.name.startswith("cryptography.")]
    assert len(crypto_results) == 1
    assert crypto_results[0].status == "CONFIRMED"


def test_cryptology_alias_dispatches_cryptography():
    from concordance_engine.verifiers import run_for_domain
    packet = {
        "domain": "cryptology",
        "CRYPTO_VERIFY": {
            "hash_strength_algorithm": "sha256",
            "claimed_hash_strength": "strong",
        },
    }
    results = run_for_domain("cryptology", packet)
    crypto_results = [r for r in results if r.name.startswith("cryptography.")]
    assert len(crypto_results) == 1
