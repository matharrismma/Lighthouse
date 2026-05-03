"""Ed25519 packet signing — canonical asymmetric crypto layer.

Per canonical 02_SPECS/INVESTMENT_PACKET_SPEC_v1_1.md and the
reference implementation in 04_CODE/lighthouse_all.py, every signed
packet uses Ed25519 with a base64url-encoded 32-byte private key
seed and 32-byte public key. The signature covers the canonical JSON
serialization of the packet *excluding* its `signature` field.

Three operations:
  * `generate_keypair()` — fresh (private, public) pair, both b64u.
  * `sign(packet, private_key)` — returns a copy of the packet with
    a `signature` field added. Idempotent: signing an already-signed
    packet replaces the signature.
  * `verify(signed_packet)` — returns (ok: bool, detail: str). Reads
    `issuer_public_key` from the packet to know which key to verify
    against (or accepts an explicit `public_key` arg).

The `cryptography` package is an OPTIONAL dep — it's heavyweight
(~5MB compiled binary) and most engine callers don't sign packets.
Install via `pip install -e ".[signing]"`. Imports are lazy: the
ImportError message tells the caller exactly what to install.

Design principles (canonical):
  * Signature covers canonical JSON (sorted keys, no whitespace) so
    the same logical packet always signs to the same bytes.
  * Private keys never leave the caller; all functions take pre-
    encoded b64u strings, never file paths.
  * No side effects — pure functions returning new dicts.
"""
from __future__ import annotations

import base64
from typing import Any, Dict, Tuple, Optional

from .validate import canonical_json_bytes


def _require_cryptography():
    """Lazy-import the cryptography package, with a friendly error
    pointing the caller at the right install command."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey, Ed25519PublicKey,
        )
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey, Ed25519PublicKey, serialization
    except ImportError as e:
        raise ImportError(
            "Ed25519 signing requires the `cryptography` package. "
            "Install with: pip install 'concordance-engine[signing]' "
            "(or pip install cryptography)"
        ) from e


def _b64u_encode(data: bytes) -> str:
    """URL-safe base64 without padding — canonical encoding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode(s + pad)


# ── Key management ───────────────────────────────────────────────────

def generate_keypair() -> Tuple[str, str]:
    """Generate a fresh Ed25519 keypair.

    Returns (private_key_b64u, public_key_b64u). Both are URL-safe
    base64-encoded raw bytes (32 bytes each).
    """
    Ed25519PrivateKey, _, serialization = _require_cryptography()
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64u_encode(priv_bytes), _b64u_encode(pub_bytes)


def public_from_private(private_key_b64u: str) -> str:
    """Derive the public key from a private key. Useful when the
    caller has only the private key and needs to publish/verify with
    the corresponding public key."""
    Ed25519PrivateKey, _, serialization = _require_cryptography()
    priv = Ed25519PrivateKey.from_private_bytes(_b64u_decode(private_key_b64u))
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64u_encode(pub_bytes)


# ── Sign / verify primitives ─────────────────────────────────────────

def sign_bytes(message: bytes, private_key_b64u: str) -> str:
    """Sign raw bytes with a private key. Returns the b64u signature."""
    Ed25519PrivateKey, _, _ = _require_cryptography()
    priv = Ed25519PrivateKey.from_private_bytes(_b64u_decode(private_key_b64u))
    return _b64u_encode(priv.sign(message))


def verify_bytes(
    message: bytes, signature_b64u: str, public_key_b64u: str,
) -> bool:
    """Verify a signature against a public key. Returns True/False."""
    _, Ed25519PublicKey, _ = _require_cryptography()
    try:
        pub = Ed25519PublicKey.from_public_bytes(_b64u_decode(public_key_b64u))
        pub.verify(_b64u_decode(signature_b64u), message)
        return True
    except Exception:
        return False


# ── Packet sign / verify ─────────────────────────────────────────────

def _payload_for_signature(packet: Dict[str, Any]) -> bytes:
    """The canonical-JSON bytes that get signed. Excludes `signature`
    so signing/verification are stable regardless of whether the
    packet has a prior signature."""
    payload = {k: v for k, v in packet.items() if k != "signature"}
    return canonical_json_bytes(payload)


def sign_packet(
    packet: Dict[str, Any], private_key_b64u: str,
) -> Dict[str, Any]:
    """Sign a packet and return a copy with the `signature` field added.

    Idempotent: re-signing an already-signed packet replaces the
    signature with a fresh one over the current canonical content.
    """
    if not isinstance(packet, dict):
        raise TypeError(f"packet must be a dict, got {type(packet).__name__}")
    payload = _payload_for_signature(packet)
    signature = sign_bytes(payload, private_key_b64u)
    out = dict(packet)
    out["signature"] = signature
    return out


def verify_packet(
    signed_packet: Dict[str, Any],
    public_key_b64u: Optional[str] = None,
) -> Tuple[bool, str]:
    """Verify a signed packet. Returns (ok, detail).

    The public key can be supplied as an argument or read from the
    packet's `issuer_public_key` field (per canonical Investment
    Packet v1.1 convention). At least one must be present.
    """
    if not isinstance(signed_packet, dict):
        return False, f"packet must be a dict, got {type(signed_packet).__name__}"
    if "signature" not in signed_packet:
        return False, "packet has no `signature` field"
    sig = signed_packet["signature"]
    if not isinstance(sig, str) or not sig:
        return False, "signature must be a non-empty string"

    if public_key_b64u is None:
        public_key_b64u = signed_packet.get("issuer_public_key")
    if not public_key_b64u:
        return False, (
            "no public key supplied and packet has no "
            "`issuer_public_key` field"
        )

    payload = _payload_for_signature(signed_packet)
    if verify_bytes(payload, sig, public_key_b64u):
        return True, "signature valid"
    return False, "signature invalid (wrong key, tampered packet, or both)"


__all__ = [
    "generate_keypair",
    "public_from_private",
    "sign_bytes",
    "verify_bytes",
    "sign_packet",
    "verify_packet",
]
