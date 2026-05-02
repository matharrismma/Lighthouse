"""Cryptography verifier (information/encoding grid axis — sibling to
genetics and computer_science).

Per Matt 2026-05-02: "they form a grid. Genetics, cryptology, computer
science." All three live on the encoding/transmission/integrity axis;
this verifier wraps Python stdlib hashlib / hmac / base64 / binascii to
expose that axis to the engine.

All checks use stdlib primitives only — no external dependency. NIST /
public-domain hash strength classifications.

Checks performed:

  * cryptography.hash_match
      Claimed message digest matches the recomputed digest for a given
      algorithm (sha256/sha512/sha1/md5/sha3_256, etc.).
  * cryptography.hash_strength
      Algorithm classified per NIST guidance: md5 / sha1 = broken;
      sha224 / sha256 / sha384 / sha512 / sha3_* / blake2 = strong.
      Claim ('strong'/'weak'/'broken') matches.
  * cryptography.hmac_match
      HMAC(key, data, algo) matches the claimed tag.
  * cryptography.encoding_roundtrip
      base64 or hex decoding of the encoded form yields the claimed
      plaintext bytes (or string, when decoded as utf-8).
  * cryptography.key_strength
      Symmetric key length in {128, 192, 256} for AES; or asymmetric
      RSA modulus length >= 2048 bits per NIST current guidance. Claim
      ('strong'/'weak') matches.

CRYPTO_VERIFY packet shape (any subset of fields):
    {
      "hash_algorithm": "sha256",
      "data": "hello world",
      "claimed_hash_hex": "b94d27b9...",

      "hash_strength_algorithm": "md5",
      "claimed_hash_strength": "broken",

      "hmac_algorithm": "sha256",
      "hmac_key": "secret",
      "hmac_data": "hello",
      "claimed_hmac_hex": "...",

      "encoded": "aGVsbG8=",
      "encoded_form": "base64",         # base64 | hex
      "claimed_decoded": "hello",       # accept str (utf-8) or hex bytes

      "cipher": "AES",                  # AES | RSA
      "key_bits": 256,
      "claimed_key_strength": "strong",
    }
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import hmac
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# NIST hash classification (informal — based on current public guidance).
# md5 / sha1 are deprecated for security use; treated as broken.
_HASH_STRENGTH = {
    "md5": "broken",
    "sha1": "broken",
    "sha224": "strong",
    "sha256": "strong",
    "sha384": "strong",
    "sha512": "strong",
    "sha3_224": "strong",
    "sha3_256": "strong",
    "sha3_384": "strong",
    "sha3_512": "strong",
    "blake2b": "strong",
    "blake2s": "strong",
}


_AES_VALID_KEY_BITS = {128, 192, 256}
_RSA_MIN_BITS_NIST = 2048


def _data_to_bytes(data: Any) -> bytes:
    """Coerce str or bytes to bytes (utf-8)."""
    if isinstance(data, bytes):
        return data
    return str(data).encode("utf-8")


def verify_hash_match(spec: Dict[str, Any]) -> VerifierResult:
    """Recompute a digest and compare to the claim."""
    name = "cryptography.hash_match"
    algo = (spec.get("hash_algorithm") or "").lower().strip()
    data = spec.get("data")
    claimed = spec.get("claimed_hash_hex")
    if not algo or data is None or claimed is None:
        return na(name)
    if algo not in hashlib.algorithms_available:
        return error(name, f"unknown hash algorithm {algo!r}")
    try:
        h = hashlib.new(algo)
        h.update(_data_to_bytes(data))
        actual = h.hexdigest().lower()
    except Exception as e:
        return error(name, f"hash failure: {type(e).__name__}: {e}")
    claim_norm = str(claimed).lower().strip().replace(" ", "")
    # Constant-time compare to avoid timing-side-channel even though we're
    # in test mode — habit matters.
    if hmac.compare_digest(actual, claim_norm):
        return confirm(name,
                       f"{algo}({data!r}) = {actual} (matches claim)",
                       {"algorithm": algo, "actual": actual})
    return mismatch(name,
                    f"{algo}({data!r}) = {actual}, claimed {claim_norm}",
                    {"algorithm": algo, "actual": actual, "claimed": claim_norm})


def verify_hash_strength(spec: Dict[str, Any]) -> VerifierResult:
    """Algorithm strength (broken/weak/strong) matches claim."""
    name = "cryptography.hash_strength"
    algo = (spec.get("hash_strength_algorithm") or "").lower().strip()
    claim = (spec.get("claimed_hash_strength") or "").lower().strip()
    if not algo or not claim:
        return na(name)
    if algo not in _HASH_STRENGTH:
        return na(name, f"no NIST classification for {algo!r}")
    actual = _HASH_STRENGTH[algo]
    data = {"algorithm": algo, "actual": actual, "claimed": claim}
    if claim == actual:
        return confirm(name, f"{algo} is {actual} (matches claim)", data)
    return mismatch(name,
                    f"{algo} is {actual} per NIST guidance, claimed {claim}",
                    data)


def verify_hmac_match(spec: Dict[str, Any]) -> VerifierResult:
    """HMAC of (key, data, algo) matches the claimed tag."""
    name = "cryptography.hmac_match"
    algo = (spec.get("hmac_algorithm") or "").lower().strip()
    key = spec.get("hmac_key")
    data = spec.get("hmac_data")
    claimed = spec.get("claimed_hmac_hex")
    if not algo or key is None or data is None or claimed is None:
        return na(name)
    if algo not in hashlib.algorithms_available:
        return error(name, f"unknown hash algorithm {algo!r}")
    try:
        actual = hmac.new(_data_to_bytes(key), _data_to_bytes(data), algo).hexdigest().lower()
    except Exception as e:
        return error(name, f"hmac failure: {type(e).__name__}: {e}")
    claim_norm = str(claimed).lower().strip().replace(" ", "")
    if hmac.compare_digest(actual, claim_norm):
        return confirm(name,
                       f"hmac-{algo} matches claim",
                       {"algorithm": algo, "actual": actual})
    return mismatch(name,
                    f"hmac-{algo} = {actual}, claimed {claim_norm}",
                    {"algorithm": algo, "actual": actual, "claimed": claim_norm})


def verify_encoding_roundtrip(spec: Dict[str, Any]) -> VerifierResult:
    """Decoded(encoded) yields the claimed plaintext."""
    name = "cryptography.encoding_roundtrip"
    encoded = spec.get("encoded")
    form = (spec.get("encoded_form") or "").lower().strip()
    claimed = spec.get("claimed_decoded")
    if encoded is None or not form or claimed is None:
        return na(name)
    try:
        if form == "base64":
            actual_bytes = base64.b64decode(encoded, validate=True)
        elif form == "hex":
            actual_bytes = binascii.unhexlify(str(encoded))
        else:
            return error(name, f"unknown encoded_form {form!r}; expected base64 or hex")
    except (binascii.Error, ValueError) as e:
        return error(name, f"decode failure: {type(e).__name__}: {e}")
    # Allow comparison against str (utf-8 decode) or hex.
    try:
        actual_str = actual_bytes.decode("utf-8")
    except UnicodeDecodeError:
        actual_str = None
    claim_str = str(claimed)
    matched = (actual_str == claim_str) or (actual_bytes.hex() == claim_str.lower())
    data = {"form": form, "encoded": encoded,
            "decoded_bytes_hex": actual_bytes.hex(),
            "decoded_str": actual_str, "claimed": claim_str}
    if matched:
        return confirm(name,
                       f"{form} round-trip yields {actual_str!r} (matches claim)",
                       data)
    return mismatch(name,
                    f"{form} decode = {actual_str!r} (or hex {actual_bytes.hex()}), "
                    f"claimed {claim_str!r}",
                    data)


def verify_key_strength(spec: Dict[str, Any]) -> VerifierResult:
    """Cipher key length within standard ranges."""
    name = "cryptography.key_strength"
    cipher = (spec.get("cipher") or "").upper().strip()
    bits = spec.get("key_bits")
    claim = (spec.get("claimed_key_strength") or "").lower().strip()
    if not cipher or bits is None or not claim:
        return na(name)
    try:
        b = int(bits)
    except (TypeError, ValueError):
        return error(name, f"key_bits must be an integer, got {bits!r}")
    if b <= 0:
        return error(name, f"key_bits must be positive, got {b}")
    if cipher == "AES":
        actual = "strong" if b in _AES_VALID_KEY_BITS else "weak"
    elif cipher == "RSA":
        actual = "strong" if b >= _RSA_MIN_BITS_NIST else "weak"
    else:
        return na(name, f"no strength classification for cipher {cipher!r}")
    data = {"cipher": cipher, "key_bits": b, "actual": actual, "claimed": claim}
    if claim == actual:
        return confirm(name,
                       f"{cipher}-{b} is {actual} (matches claim)",
                       data)
    return mismatch(name,
                    f"{cipher}-{b} is {actual}, claimed {claim}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch every applicable cryptography check."""
    results: List[VerifierResult] = []
    cv = packet.get("CRYPTO_VERIFY") or {}

    if "claimed_hash_hex" in cv:
        results.append(verify_hash_match(cv))
    if "claimed_hash_strength" in cv:
        results.append(verify_hash_strength(cv))
    if "claimed_hmac_hex" in cv:
        results.append(verify_hmac_match(cv))
    if "claimed_decoded" in cv:
        results.append(verify_encoding_roundtrip(cv))
    if "claimed_key_strength" in cv:
        results.append(verify_key_strength(cv))

    if not results:
        results.append(na("cryptography", "no CRYPTO_VERIFY artifacts present"))
    return results
