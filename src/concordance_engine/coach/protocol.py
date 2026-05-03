"""coach.protocol — shared types and the append-only packet log.

Ported from `coach_fractal_os/protocol.py` (iCloud_archive). The
canonical spec lives at `coach_fractal_os/specs/COACH_FRACTAL_ARCH_SPEC_v1.md`
and `coach_fractal_os/specs/COACH_ACTION_TOKEN_CONTRACT_v1.md` (also
in iCloud_archive). Engine-side adjustments:

  * `PacketStore` writes optionally to disk under `lw/coach/` so the
    audit log persists across sessions, parallel to the engine's
    other file-backed stores (lw/ledger/, lw/quarantine/, lw/keeping/,
    lw/journal/). In-memory-only mode is also supported (default for
    short-lived tests).

  * Type aliases line up with the engine's existing vocabulary —
    `Decision` is namespaced inside this package so it doesn't
    collide with `quarantine.Decision`.

The protocol's invariants (per the canonical spec):

  * **Append-only.** Packets are never mutated or deleted.
  * **Token binding.** Each ActionToken hashes the full request
    (session, corridor, wedge, level, context_digest, risk_flags) so
    the token is invalid for any other request.
  * **TTL + single use.** Tokens expire and can be consumed once.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# ── Core enums ──────────────────────────────────────────────────────


class Plane(Enum):
    """The two planes of the Coach OS architecture."""
    MAIN = "main"          # Coach + Scribe (mind/body)
    STEWARD = "steward"    # Steward (spirit)


class Decision(Enum):
    """Steward's verdict on a wedge request."""
    ADMIT = "admit"
    DENY = "deny"


class ReasonCode(Enum):
    """Why the Steward admitted or denied. Canonical set per
    COACH_ACTION_TOKEN_CONTRACT_v1."""
    ALLOW_OK = "ALLOW_OK"

    # Corridor / path protection
    DENY_CORRIDOR = "DENY_CORRIDOR"
    DENY_FLOW_PROTECTED = "DENY_FLOW_PROTECTED"
    DENY_DOSE_LIMIT = "DENY_DOSE_LIMIT"
    DENY_ESCALATION_CAP = "DENY_ESCALATION_CAP"
    DENY_MODE_LOCK = "DENY_MODE_LOCK"
    DENY_EGRESS_LOCK = "DENY_EGRESS_LOCK"

    # Safety / policy / integrity
    DENY_SAFETY = "DENY_SAFETY"
    DENY_POLICY = "DENY_POLICY"
    DENY_WIP_LIMIT = "DENY_WIP_LIMIT"
    DENY_RATE_LIMIT = "DENY_RATE_LIMIT"

    # Token failures
    DENY_EXPIRED_TOKEN = "DENY_EXPIRED_TOKEN"
    DENY_TOKEN_MISMATCH = "DENY_TOKEN_MISMATCH"
    DENY_TOKEN_ALREADY_USED = "DENY_TOKEN_ALREADY_USED"


# ── Helpers ─────────────────────────────────────────────────────────


def now_ms() -> int:
    return int(time.time() * 1000)


def new_id() -> str:
    return str(uuid.uuid4())


def stable_hash(obj: Dict[str, Any]) -> str:
    """Deterministic SHA-256 over a dict with sorted keys. The hash is
    over the dict's repr-ordered key/value pairs — sufficient for
    request-binding in this protocol; not a general-purpose canonical
    JSON hash (the engine uses `validate.canonical_json_bytes` for
    that)."""
    h = hashlib.sha256()
    for k in sorted(obj.keys()):
        h.update(str(k).encode("utf-8"))
        h.update(str(obj[k]).encode("utf-8"))
    return h.hexdigest()


def _default_coach_dir() -> Path:
    """Repo-root `lw/coach/` by default; overridable via env var."""
    override = os.environ.get("CONCORDANCE_COACH_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / "lw" / "coach"


# ── Packets (append-only events) ────────────────────────────────────


@dataclass(frozen=True)
class Packet:
    packet_type: str
    packet_id: str
    created_at_ms: int
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "packet_type": self.packet_type,
            "packet_id": self.packet_id,
            "created_at_ms": self.created_at_ms,
            "payload": dict(self.payload),
        }


class PacketStore:
    """Append-only packet log. Never mutated or deleted.

    Two modes:
      * in-memory only (default): packets live for the process; useful
        for tests and short-lived sessions.
      * file-backed: pass `base_dir=Path(...)` and packets append to
        `<base_dir>/coach_log.jsonl`.

    The engine's other stores (ledger, quarantine, keeping, journal)
    each have their own pattern; this one is JSONL because Coach OS
    packets are typed event records, not addressable entities."""

    def __init__(self, base_dir: Optional[Path] = None):
        self._log: List[Packet] = []
        self.base_dir: Optional[Path] = base_dir

    def _path(self) -> Optional[Path]:
        if self.base_dir is None:
            return None
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir / "coach_log.jsonl"

    def append(self, packet_type: str, payload: Dict[str, Any]) -> str:
        pid = new_id()
        packet = Packet(packet_type, pid, now_ms(), dict(payload))
        self._log.append(packet)
        path = self._path()
        if path is not None:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(packet.to_dict(), default=str) + "\n")
        return pid

    def all(self) -> List[Packet]:
        return list(self._log)

    def by_type(self, packet_type: str) -> List[Packet]:
        return [p for p in self._log if p.packet_type == packet_type]

    def by_session(self, session_id: str) -> List[Packet]:
        return [
            p for p in self._log
            if p.payload.get("session_id") == session_id
        ]


# ── Requests / Tokens ───────────────────────────────────────────────


@dataclass(frozen=True)
class WedgeRequest:
    """Main-plane request for an action ("wedge") that crosses the
    corridor boundary.

    Per the canonical spec: the request hashes (session, corridor,
    wedge, level, requested_effect, context_digest, risk_flags) into
    the ActionToken so the token is invalid for any other request.
    """
    request_id: str
    created_at_ms: int

    session_id: str
    wedge_id: str
    wedge_level: int  # 1=soft prompt ... 5=strong escalation
    requested_effect: str

    # Corridor context (Steward stays content-light; only the digest)
    context_digest: str
    corridor_id: str

    # Risk flags surfaced to the Steward for mode/egress decisions
    risk_flags: List[str]

    def hash(self) -> str:
        """Deterministic hash binding this request to a token."""
        return stable_hash({
            "request_id": self.request_id,
            "session_id": self.session_id,
            "wedge_id": self.wedge_id,
            "wedge_level": self.wedge_level,
            "requested_effect": self.requested_effect,
            "context_digest": self.context_digest,
            "corridor_id": self.corridor_id,
            "risk_flags": tuple(self.risk_flags),
        })


@dataclass(frozen=True)
class ActionToken:
    """Short-lived, single-use admission token issued by the Steward."""
    token_id: str
    request_hash: str
    issued_at_ms: int
    expires_at_ms: int
    steward_counter: int
    constraints: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "request_hash": self.request_hash,
            "issued_at_ms": self.issued_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "steward_counter": self.steward_counter,
            "constraints": dict(self.constraints),
        }


__all__ = [
    "ActionToken",
    "Decision",
    "Packet",
    "PacketStore",
    "Plane",
    "ReasonCode",
    "WedgeRequest",
    "new_id",
    "now_ms",
    "stable_hash",
]
