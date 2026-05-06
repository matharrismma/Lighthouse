"""Instance identity — persistent Ed25519 keypair for this engine node.

On first call to `get_instance_key()` the engine generates a fresh keypair
and writes it to ~/.concordance/instance_key.json (overridable via
CONCORDANCE_KEY_PATH env var). Every subsequent call returns the same keys.

This is the identity token that makes verified packets trustworthy across
instances. A packet signed by this key can be verified by any recipient
who has the public key — without calling home, without network access,
on a USB drive, on a LoRa mesh node.

Key file format:
    {
      "version": 1,
      "instance_id": "<first 16 chars of public_key_b64u>",
      "public_key_b64u": "<URL-safe base64 Ed25519 public key>",
      "private_key_b64u": "<URL-safe base64 Ed25519 private key seed>",
      "created_at": <unix epoch int>
    }

The private key never leaves this file and never appears in any API
response. The public key is served freely at GET /identity/pubkey.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Optional, Tuple


_CACHE_LOCK = threading.Lock()
_CACHED: Optional[dict] = None


def _key_path() -> Path:
    env = os.environ.get("CONCORDANCE_KEY_PATH")
    if env:
        return Path(env)
    base = Path(os.environ.get("CONCORDANCE_DATA_DIR", "~/.concordance")).expanduser()
    return base / "instance_key.json"


def _load_or_generate() -> dict:
    path = _key_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") == 1 and data.get("private_key_b64u") and data.get("public_key_b64u"):
                return data
        except (json.JSONDecodeError, OSError):
            pass

    # Generate fresh keypair using the existing signing module.
    from .signing import generate_keypair
    priv_b64u, pub_b64u = generate_keypair()
    instance_id = pub_b64u[:16]
    data = {
        "version": 1,
        "instance_id": instance_id,
        "public_key_b64u": pub_b64u,
        "private_key_b64u": priv_b64u,
        "created_at": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def get_instance_key() -> dict:
    """Return the instance keypair dict, loading or generating on first call.

    Thread-safe. The private key is included — only call this in signing
    contexts, never serialize the full dict to a response.
    """
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    with _CACHE_LOCK:
        if _CACHED is None:
            _CACHED = _load_or_generate()
    return _CACHED


def get_public_key() -> str:
    """Return the instance public key (URL-safe base64). Safe to expose."""
    return get_instance_key()["public_key_b64u"]


def get_instance_id() -> str:
    """Return a short human-readable instance identifier (first 16 chars
    of the public key). Not secret. Used in packet metadata."""
    return get_instance_key()["instance_id"]


def sign_dict(data: dict) -> dict:
    """Sign a dict and return a copy with `_sig` and `_instance_pubkey`
    fields added. The signature covers the canonical JSON of the dict
    excluding those two fields, so the payload is stable across re-signs.

    Uses the instance private key. Safe to store the result publicly —
    the private key is never included.
    """
    from .signing import sign_bytes
    from .validate import canonical_json_bytes

    key = get_instance_key()
    payload = {k: v for k, v in data.items() if k not in ("_sig", "_instance_pubkey")}
    sig = sign_bytes(canonical_json_bytes(payload), key["private_key_b64u"])
    out = dict(data)
    out["_sig"] = sig
    out["_instance_pubkey"] = key["public_key_b64u"]
    out["_instance_id"] = key["instance_id"]
    return out


def verify_dict(data: dict, public_key_b64u: Optional[str] = None) -> Tuple[bool, str]:
    """Verify a dict signed by `sign_dict`. Returns (ok, detail).

    public_key_b64u may be supplied explicitly or read from the dict's
    `_instance_pubkey` field. If neither is present → (False, reason).
    """
    from .signing import verify_bytes
    from .validate import canonical_json_bytes

    sig = data.get("_sig")
    if not sig:
        return False, "no _sig field present"

    pubkey = public_key_b64u or data.get("_instance_pubkey")
    if not pubkey:
        return False, "no public key: supply public_key_b64u or include _instance_pubkey in data"

    payload = {k: v for k, v in data.items() if k not in ("_sig", "_instance_pubkey", "_instance_id")}
    try:
        ok = verify_bytes(canonical_json_bytes(payload), sig, pubkey)
    except Exception as exc:
        return False, f"verification error: {exc}"
    return (True, "signature valid") if ok else (False, "signature invalid")


__all__ = [
    "get_instance_key",
    "get_public_key",
    "get_instance_id",
    "sign_dict",
    "verify_dict",
]
