"""witness — Ed25519 witness signatures for sealed precedents.

A witness signature is a small JSON record that asserts: *I, holding
this public key, attest that this precedent existed at this moment.*
The BROTHERS gate already requires N witnesses by name; this module
adds cryptographic proof — a witness signature can be verified
without trusting the sealing engine, only by trusting the public key.

Per the deployment-modes doctrine: witnesses signing across
distributed instances is what makes Lockdown-mode federation real.
Two communities running their own engines can exchange precedents
that carry verifiable proof-of-witness; neither has to trust the
other's chain.

Per "free use, alignment to execute": witnessing is part of
executing (sealing requires witnesses; pulling/reading does not).

## What gets signed

A canonical JSON document with these fields, in this order:

```
{
  "precedent_id": "ledger://decision/2024-11-08/admit-member-007",
  "entry_hash":   "abc123...",
  "signed_at":    1730000000
}
```

The witness's Ed25519 signature covers the canonical (sorted-keys,
no-whitespace) bytes of that document.

## The witness-attestation record

The full attestation a witness produces:

```
{
  "precedent_id": "...",
  "entry_hash":   "...",
  "signed_at":    1730000000,
  "witness_name": "Alice",
  "witness_role": "elder",
  "witness_pubkey": "<b64u>",
  "signature":    "<b64u>"
}
```

The first three fields are the signed payload. The last four are
the witness identity and the signature itself. Anyone with this
record can verify it without the engine's involvement: extract the
payload, recompute canonical bytes, verify against `signature` +
`witness_pubkey`.

## Stored separately from the audit chain

Witness attestations live in their own JSONL files alongside the
audit chain — `<base_dir>/witness/<precedent_slug>.jsonl`, append-
only, one attestation per line. The audit chain stays unchanged;
witness attestations are an additional layer of evidence that can
be added retroactively.

## Dependencies

This module uses `concordance_engine.signing` which lazily imports
`cryptography`. If `cryptography` isn't installed, witness operations
raise ImportError with a setup message. Install with:

    pip install 'concordance-engine[signing]'
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import signing as _signing


# ── Storage ────────────────────────────────────────────────────────


def _default_witness_dir() -> Path:
    """Where witness attestations live. Override via
    CONCORDANCE_DATA_DIR/witness or CONCORDANCE_WITNESS_DIR directly."""
    if "CONCORDANCE_WITNESS_DIR" in os.environ:
        return Path(os.environ["CONCORDANCE_WITNESS_DIR"])
    if "CONCORDANCE_DATA_DIR" in os.environ:
        return Path(os.environ["CONCORDANCE_DATA_DIR"]) / "witness"
    return Path.home() / ".concordance" / "witness"


def _slug_for(precedent_id: str) -> str:
    """Filesystem-safe slug from a precedent_id. 16 hex chars is
    collision-resistant for any reasonable scale of precedents."""
    return hashlib.sha256(precedent_id.encode("utf-8")).hexdigest()[:16]


# ── Data shapes ────────────────────────────────────────────────────


@dataclass
class WitnessAttestation:
    """A single signed witness record. Ordering of fields matters
    for the canonical-JSON-of-payload step; do not reorder."""
    precedent_id: str
    entry_hash: str
    signed_at: int
    witness_name: str
    witness_role: str
    witness_pubkey: str
    signature: str

    def to_dict(self) -> Dict[str, Any]:
        # Ordered explicitly so on-the-wire ordering is stable.
        return {
            "precedent_id":   self.precedent_id,
            "entry_hash":     self.entry_hash,
            "signed_at":      self.signed_at,
            "witness_name":   self.witness_name,
            "witness_role":   self.witness_role,
            "witness_pubkey": self.witness_pubkey,
            "signature":      self.signature,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WitnessAttestation":
        return cls(
            precedent_id=str(d["precedent_id"]),
            entry_hash=str(d["entry_hash"]),
            signed_at=int(d["signed_at"]),
            witness_name=str(d["witness_name"]),
            witness_role=str(d["witness_role"]),
            witness_pubkey=str(d["witness_pubkey"]),
            signature=str(d["signature"]),
        )


# ── Sign ───────────────────────────────────────────────────────────


def _payload_bytes(precedent_id: str, entry_hash: str, signed_at: int) -> bytes:
    """Canonical bytes the witness signature covers. The three
    fields, in fixed order, as canonical JSON (sorted keys, no
    whitespace, UTF-8). Same convention as `signing._payload_for_signature`."""
    payload = {
        "entry_hash":   entry_hash,
        "precedent_id": precedent_id,
        "signed_at":    int(signed_at),
    }
    # canonical_json_bytes sorts keys; this matches the engine-wide
    # convention so any other implementation of this protocol can
    # produce byte-identical input.
    from .validate import canonical_json_bytes
    return canonical_json_bytes(payload)


def sign(
    *,
    precedent_id: str,
    entry_hash: str,
    private_key_b64u: str,
    witness_name: str,
    witness_role: str,
    signed_at: Optional[int] = None,
) -> WitnessAttestation:
    """Produce a signed witness attestation.

    The private_key never leaves the caller; we only use it to
    compute the signature and discard. The returned record contains
    only the public key, name, role, and signature."""
    if not precedent_id:
        raise ValueError("precedent_id is required")
    if not entry_hash:
        raise ValueError("entry_hash is required")
    if not witness_name:
        raise ValueError("witness_name is required")
    if not witness_role:
        raise ValueError("witness_role is required")

    when = int(signed_at if signed_at is not None else time.time())
    pub = _signing.public_from_private(private_key_b64u)
    payload = _payload_bytes(precedent_id, entry_hash, when)
    sig = _signing.sign_bytes(payload, private_key_b64u)
    return WitnessAttestation(
        precedent_id=precedent_id,
        entry_hash=entry_hash,
        signed_at=when,
        witness_name=witness_name,
        witness_role=witness_role,
        witness_pubkey=pub,
        signature=sig,
    )


# ── Verify ─────────────────────────────────────────────────────────


def verify(att: WitnessAttestation) -> Tuple[bool, str]:
    """Verify a witness attestation. Returns (ok, reason)."""
    try:
        payload = _payload_bytes(
            att.precedent_id, att.entry_hash, att.signed_at,
        )
    except (TypeError, ValueError) as exc:
        return False, f"malformed payload: {exc}"
    try:
        ok = _signing.verify_bytes(
            payload, att.signature, att.witness_pubkey,
        )
    except (ValueError, TypeError) as exc:
        return False, f"signature decode failed: {exc}"
    except ImportError as exc:
        return False, f"cryptography not installed: {exc}"
    if not ok:
        return False, "signature does not verify against witness_pubkey"
    return True, "ok"


def verify_dict(d: Dict[str, Any]) -> Tuple[bool, str]:
    """Verify a witness attestation given as a dict (e.g. parsed
    from JSON). Convenience wrapper that constructs the dataclass."""
    try:
        att = WitnessAttestation.from_dict(d)
    except (KeyError, TypeError, ValueError) as exc:
        return False, f"malformed attestation: {exc}"
    return verify(att)


# ── Append + read ──────────────────────────────────────────────────


def append(
    att: WitnessAttestation,
    *,
    base_dir: Optional[Path] = None,
) -> Path:
    """Append an attestation to the per-precedent JSONL log. The
    file is created if it doesn't exist. Multiple attestations per
    precedent are expected (BROTHERS = N witnesses)."""
    base = base_dir or _default_witness_dir()
    base.mkdir(parents=True, exist_ok=True)
    slug = _slug_for(att.precedent_id)
    p = base / f"{slug}.jsonl"
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(att.to_dict(), separators=(",", ":")) + "\n")
    return p


def list_for_precedent(
    precedent_id: str,
    *,
    base_dir: Optional[Path] = None,
) -> List[WitnessAttestation]:
    """Return all attestations on file for a given precedent_id."""
    base = base_dir or _default_witness_dir()
    slug = _slug_for(precedent_id)
    p = base / f"{slug}.jsonl"
    if not p.exists():
        return []
    out: List[WitnessAttestation] = []
    try:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    out.append(WitnessAttestation.from_dict(d))
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
    except OSError:
        return []
    return out


__all__ = [
    "WitnessAttestation",
    "sign",
    "verify",
    "verify_dict",
    "append",
    "list_for_precedent",
]
