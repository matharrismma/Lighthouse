"""Witness attestations on a walk's BROTHERS gate.

The four gates require a witness — "in the mouth of two or three witnesses
every word shall be established" (Mt 18:16). v1 is social: the walker
invites a witness via a shareable URL, and the witness submits a named
attestation. v2 will add Ed25519 signatures for cryptographic binding;
the schema already reserves `signature` + `witness_pubkey` so the upgrade
is non-breaking.

Storage: append-only JSONL per walker at
data/witnesses/walks/<walker_visitor_id>.jsonl. The walk_id ties the
attestation to a specific situation.

A witness does NOT need a visitor_id of their own — they identify
themselves by name. Anyone with the shareable link can attest.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "witnesses" / "walks"

_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_WALK_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_NAME_RE    = re.compile(r"^[A-Za-z0-9 _\-\.']{1,80}$")

MAX_WITNESSES_PER_WALK = 12
MAX_ATTESTATION_LEN = 4000


def _valid_visitor_id(vid: str) -> bool:
    return bool(_VISITOR_RE.match((vid or "").strip().lower()))


def _valid_walk_id(wid: str) -> bool:
    return bool(_WALK_ID_RE.match((wid or "").strip()))


def _valid_name(name: str) -> bool:
    return bool(_NAME_RE.match((name or "").strip()))


def _walker_file(visitor_id: str) -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"{visitor_id.strip().lower()}.jsonl"


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def add_attestation(
    *,
    walker_visitor_id: str,
    walk_id: str,
    witness_name: str,
    witness_role: str = "",
    attestation: str = "",
    witness_pubkey: str = "",
    signature: str = "",
    lang: str = "en",
    attestation_original: Optional[str] = None,
    mt_provider: Optional[str] = None,
) -> Dict[str, Any]:
    """A named witness attests to the walker's BROTHERS gate.

    witness_pubkey + signature are reserved for crypto v2. Today the
    attestation is socially binding: the walker chose to share the link,
    the witness chose to put their name to it.

    `lang` plus `attestation_original` + `mt_provider` capture the bilingual
    audit trail when the witness wrote in a non-English language. The
    canonical `attestation` is English; UI can render `attestation_original`
    in the witness's language when present.
    """
    if not _valid_visitor_id(walker_visitor_id):
        raise ValueError("invalid walker_visitor_id")
    if not _valid_walk_id(walk_id):
        raise ValueError("invalid walk_id")
    if not _valid_name(witness_name):
        raise ValueError("witness name must be 1-80 chars, letters/digits/space/-_.'")
    attestation = (attestation or "").strip()[:MAX_ATTESTATION_LEN]

    now = int(time.time())
    record = {
        "id": "wit-" + _short_hash(f"{walker_visitor_id}|{walk_id}|{witness_name}|{now}"),
        "logged_at": now,
        "logged_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "walker_visitor_id": walker_visitor_id.strip().lower(),
        "walk_id": walk_id.strip(),
        "witness_name": witness_name.strip(),
        "witness_role": (witness_role or "").strip()[:80],
        "attestation": attestation,
        # crypto fields reserved for v2
        "witness_pubkey": (witness_pubkey or "").strip()[:200],
        "signature": (signature or "").strip()[:200],
        "verified": False,  # flipped to True once signature verification lands
        "lang": (lang or "en").strip().lower() or "en",
    }
    if attestation_original:
        record["attestation_original"] = attestation_original[:MAX_ATTESTATION_LEN]
    if mt_provider:
        record["mt_provider"] = mt_provider

    # Enforce per-walk cap server-side
    existing = list_for_walk(walker_visitor_id, walk_id)
    if len(existing) >= MAX_WITNESSES_PER_WALK:
        raise ValueError(f"walk already has {MAX_WITNESSES_PER_WALK} witnesses (cap reached)")

    path = _walker_file(walker_visitor_id)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _read_all(walker_visitor_id: str) -> List[Dict[str, Any]]:
    if not _valid_visitor_id(walker_visitor_id):
        return []
    path = _walker_file(walker_visitor_id)
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return out
    return out


def list_for_walk(walker_visitor_id: str, walk_id: str) -> List[Dict[str, Any]]:
    """All attestations for a specific walk, oldest first."""
    if not _valid_walk_id(walk_id):
        return []
    return [r for r in _read_all(walker_visitor_id) if r.get("walk_id") == walk_id and not r.get("deleted")]


def list_for_walker(walker_visitor_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """All attestations the walker has ever received, newest first."""
    out = [r for r in _read_all(walker_visitor_id) if not r.get("deleted")]
    out.sort(key=lambda r: r.get("logged_at", 0), reverse=True)
    return out[:limit]


def public_view(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Render an attestation for surfacing on the walk. visitor_id stays opaque."""
    return {
        "id": rec.get("id"),
        "logged_at_iso": rec.get("logged_at_iso", ""),
        "walk_id": rec.get("walk_id"),
        "witness_name": rec.get("witness_name", ""),
        "witness_role": rec.get("witness_role", ""),
        "attestation": rec.get("attestation", ""),
        "verified": bool(rec.get("verified", False)),
    }
