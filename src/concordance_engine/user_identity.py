"""User identity — persistent personal Ed25519 keypair (the "soul anchor").

Distinct from instance_identity.py, which tracks the *machine*. This
module tracks the *person*. A soulbound receipt binds to the user's
personal public key, not to the device that sealed it.

Key file: ~/.concordance/user_key.json (override: CONCORDANCE_USER_KEY_PATH)

Format (v1):
    {
      "version": 1,
      "user_id": "<first 16 chars of public_key_b64u>",
      "public_key_b64u": "<URL-safe base64 Ed25519 public key>",
      "private_key_b64u": "<URL-safe base64 Ed25519 private key seed>",
      "created_at": <unix epoch int>
    }

The private key never appears in any API response or sealed record.
The public key is embedded in every sealed WitnessRecord as
`subject_pubkey` — the cryptographic soul anchor that makes a receipt
non-transferable: only the holder of the matching private key can
produce new signatures over the same identity.
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
    env = os.environ.get("CONCORDANCE_USER_KEY_PATH")
    if env:
        return Path(env)
    base = Path(os.environ.get("CONCORDANCE_DATA_DIR", "~/.concordance")).expanduser()
    return base / "user_key.json"


def _load_or_generate() -> dict:
    path = _key_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if (data.get("version") == 1
                    and data.get("private_key_b64u")
                    and data.get("public_key_b64u")):
                return data
        except (json.JSONDecodeError, OSError):
            pass

    from .signing import generate_keypair
    priv_b64u, pub_b64u = generate_keypair()
    data = {
        "version": 1,
        "user_id": pub_b64u[:16],
        "public_key_b64u": pub_b64u,
        "private_key_b64u": priv_b64u,
        "created_at": int(time.time()),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def get_user_key() -> dict:
    """Return the user keypair dict (thread-safe, load-or-generate).

    The private key is included — only call this in signing contexts.
    Never serialize the full dict to any response.
    """
    global _CACHED
    if _CACHED is not None:
        return _CACHED
    with _CACHE_LOCK:
        if _CACHED is None:
            _CACHED = _load_or_generate()
    return _CACHED


def get_user_pubkey() -> str:
    """Return the user public key (URL-safe base64). Safe to embed in records."""
    return get_user_key()["public_key_b64u"]


def get_user_id() -> str:
    """Short human-readable user identifier (first 16 chars of pubkey)."""
    return get_user_key()["user_id"]


def sign_dict(data: dict) -> dict:
    """Sign a dict with the user private key. Returns a copy with
    `_user_sig` and `_subject_pubkey` fields added.

    The signature covers the canonical JSON of the dict excluding those
    two fields, so re-signing is idempotent over the payload.
    """
    from .signing import sign_bytes
    from .validate import canonical_json_bytes

    key = get_user_key()
    payload = {k: v for k, v in data.items()
               if k not in ("_user_sig", "_subject_pubkey")}
    sig = sign_bytes(canonical_json_bytes(payload), key["private_key_b64u"])
    out = dict(data)
    out["_user_sig"] = sig
    out["_subject_pubkey"] = key["public_key_b64u"]
    return out


def verify_dict(
    data: dict,
    public_key_b64u: Optional[str] = None,
) -> Tuple[bool, str]:
    """Verify a dict signed by `sign_dict`. Returns (ok, detail).

    public_key_b64u may be supplied explicitly or read from `_subject_pubkey`.
    """
    from .signing import verify_bytes
    from .validate import canonical_json_bytes

    sig = data.get("_user_sig")
    if not sig:
        return False, "no _user_sig field present"

    pubkey = public_key_b64u or data.get("_subject_pubkey")
    if not pubkey:
        return False, "no public key: supply public_key_b64u or include _subject_pubkey"

    payload = {k: v for k, v in data.items()
               if k not in ("_user_sig", "_subject_pubkey")}
    try:
        ok = verify_bytes(canonical_json_bytes(payload), sig, pubkey)
    except Exception as exc:
        return False, f"verification error: {exc}"
    return (True, "signature valid") if ok else (False, "signature invalid")


__all__ = [
    "get_user_key",
    "get_user_pubkey",
    "get_user_id",
    "sign_dict",
    "verify_dict",
]
