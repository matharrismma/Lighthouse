"""Quarantine Airlock — canonical default-quarantine workflow.

Per 03_ARCH/QUARANTINE_AIRLOCK.md:

  > Default rule: Ideas are quarantined by default.
  >
  > Zones:
  >   * Core: canonical, installable truth + specs.
  >   * Holding chamber: candidate inputs awaiting processing.
  >   * Decontamination pipeline: dedupe, denoise, classify, test,
  >     and output structured packets.
  >
  > Roles:
  >   * Q: manages flow and hygiene.
  >   * Scribe: captures and structures.
  >   * Guide: evaluates, decides, and converts (post-admission only).
  >
  > Admission format: No idea enters Core except as a structured
  > packet — hypothesis, backlog item(s), decision (accept/reject/defer).

This module implements the state machine. Every captured idea starts
in HOLDING. Q + Scribe move it through DECONTAMINATION. Only when a
Guide-issued ACCEPT decision is recorded does it enter CORE. REJECT
keeps it in HOLDING with the rejection note attached. DEFER puts it
back into DECONTAMINATION pending more work.

Persistence is file-backed (one JSON per packet under `lw/quarantine/`)
parallel to the Audit Chain's `lw/ledger/` directory, so the
quarantine record is auditable from outside the running process.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# ── Canonical enums ──────────────────────────────────────────────────


class Zone(str, Enum):
    """Three zones from QUARANTINE_AIRLOCK.md."""
    HOLDING = "holding"
    DECONTAMINATION = "decontamination"
    CORE = "core"


class Role(str, Enum):
    """Three roles from QUARANTINE_AIRLOCK.md.

    Q: flow and hygiene — moves packets between zones, dedupes, denoises.
    Scribe: capture-first — intakes, structures, hands off.
    Guide: evaluates, decides, converts (post-admission only).
    """
    Q = "Q"
    SCRIBE = "scribe"
    GUIDE = "guide"


class Decision(str, Enum):
    """Per canon: structured packet admission carries a decision."""
    ACCEPT = "accept"   # → moves to CORE
    REJECT = "reject"   # → stays in HOLDING with rejection note
    DEFER = "defer"     # → stays in DECONTAMINATION pending more work


# ── Errors ───────────────────────────────────────────────────────────


class QuarantineError(Exception):
    """Raised when a state transition violates canonical rules."""


# ── Packet ───────────────────────────────────────────────────────────


@dataclass
class RoleAction:
    """One action by one role on a quarantine packet — appended to the
    packet's history. Provides the audit trail for why a packet sits
    where it does."""
    role: str        # one of Role values
    action: str      # short verb: "captured", "denoised", "accepted", etc.
    note: str = ""   # optional human-readable note
    timestamp: float = 0.0  # set on append

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "action": self.action,
            "note": self.note,
            "timestamp": self.timestamp,
        }


@dataclass
class QuarantinePacket:
    """A candidate idea moving through the airlock.

    Per canon's admission format, a packet that enters CORE must
    declare:
      * hypothesis: the claim or proposition being tested
      * backlog_items: concrete next-actions or unresolved questions
      * decision: accept / reject / defer (set at admission)

    Before that, it carries raw + normalized text and accumulates
    role actions through the workflow.
    """
    id: str
    raw: str
    normalized: str = ""
    tags: List[str] = field(default_factory=list)
    zone: str = Zone.HOLDING.value
    hypothesis: str = ""
    backlog_items: List[str] = field(default_factory=list)
    decision: Optional[str] = None
    rejection_reason: str = ""
    history: List[RoleAction] = field(default_factory=list)
    created_at: float = 0.0
    modified_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["history"] = [
            (a.to_dict() if isinstance(a, RoleAction) else a)
            for a in self.history
        ]
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QuarantinePacket":
        history = []
        for a in d.get("history", []):
            if isinstance(a, dict):
                history.append(RoleAction(**a))
            else:
                history.append(a)
        return cls(
            id=d["id"],
            raw=d.get("raw", ""),
            normalized=d.get("normalized", ""),
            tags=list(d.get("tags", [])),
            zone=d.get("zone", Zone.HOLDING.value),
            hypothesis=d.get("hypothesis", ""),
            backlog_items=list(d.get("backlog_items", [])),
            decision=d.get("decision"),
            rejection_reason=d.get("rejection_reason", ""),
            history=history,
            created_at=d.get("created_at", 0.0),
            modified_at=d.get("modified_at", 0.0),
        )


# ── Helpers ──────────────────────────────────────────────────────────


def _now() -> float:
    return time.time()


def _new_id() -> str:
    return f"q-{uuid.uuid4().hex[:12]}"


def _normalize_text(raw: str) -> str:
    """Light normalization parallel to LSP's first stage. Removes
    non-breaking spaces and collapses whitespace; preserves diacritics
    and case."""
    import re
    if not raw:
        return ""
    text = raw.replace(" ", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── State transitions ───────────────────────────────────────────────


def capture(
    raw: str,
    *,
    tags: Optional[List[str]] = None,
    note: str = "",
) -> QuarantinePacket:
    """Scribe captures a raw input. Lands in HOLDING."""
    if not raw or not raw.strip():
        raise QuarantineError("cannot capture empty input")
    now = _now()
    packet = QuarantinePacket(
        id=_new_id(),
        raw=raw,
        normalized=_normalize_text(raw),
        tags=list(tags or []),
        zone=Zone.HOLDING.value,
        created_at=now,
        modified_at=now,
    )
    packet.history.append(RoleAction(
        role=Role.SCRIBE.value,
        action="captured",
        note=note or f"raw input ({len(raw)} chars)",
        timestamp=now,
    ))
    return packet


def decontaminate(
    packet: QuarantinePacket,
    *,
    hypothesis: str,
    backlog_items: Optional[List[str]] = None,
    note: str = "",
) -> QuarantinePacket:
    """Q moves a packet from HOLDING → DECONTAMINATION. Requires the
    Scribe to have framed a hypothesis (the structured form of what
    the input is being tested against)."""
    if packet.zone != Zone.HOLDING.value:
        raise QuarantineError(
            f"can only decontaminate packets in HOLDING; "
            f"this packet is in {packet.zone}"
        )
    if not hypothesis or not hypothesis.strip():
        raise QuarantineError(
            "decontamination requires a non-empty hypothesis "
            "(the structured form of the captured idea)"
        )
    now = _now()
    packet.zone = Zone.DECONTAMINATION.value
    packet.hypothesis = hypothesis.strip()
    if backlog_items is not None:
        packet.backlog_items = list(backlog_items)
    packet.modified_at = now
    packet.history.append(RoleAction(
        role=Role.Q.value,
        action="moved_to_decontamination",
        note=note or f"hypothesis set: {hypothesis[:60]}",
        timestamp=now,
    ))
    return packet


def admit(
    packet: QuarantinePacket,
    *,
    decision: Decision,
    rationale: str = "",
    note: str = "",
) -> QuarantinePacket:
    """Guide issues a decision on a packet. ACCEPT moves it to CORE;
    REJECT keeps it in HOLDING with a rejection_reason; DEFER puts it
    back in DECONTAMINATION pending more work.

    Per canon: Guide evaluates ONLY post-admission. The packet must be
    in DECONTAMINATION (Q + Scribe have already framed it) before a
    Guide can issue a decision. Capture → Decontamination → Decision
    is the canonical flow.
    """
    if packet.zone != Zone.DECONTAMINATION.value:
        raise QuarantineError(
            f"Guide decisions only valid for packets in DECONTAMINATION; "
            f"this packet is in {packet.zone}. Move it through "
            f"decontaminate() first."
        )
    if not isinstance(decision, Decision):
        raise QuarantineError(
            f"decision must be a Decision enum value, got {type(decision).__name__}"
        )
    if decision == Decision.REJECT and not rationale.strip():
        raise QuarantineError(
            "REJECT requires a rationale — capturing why the idea didn't "
            "make it into Core is the value of the rejection record"
        )

    now = _now()
    packet.decision = decision.value
    packet.modified_at = now

    if decision == Decision.ACCEPT:
        packet.zone = Zone.CORE.value
        packet.history.append(RoleAction(
            role=Role.GUIDE.value,
            action="accepted",
            note=note or rationale or "admitted to Core",
            timestamp=now,
        ))
    elif decision == Decision.REJECT:
        packet.zone = Zone.HOLDING.value
        packet.rejection_reason = rationale.strip()
        packet.history.append(RoleAction(
            role=Role.GUIDE.value,
            action="rejected",
            note=note or rationale,
            timestamp=now,
        ))
    elif decision == Decision.DEFER:
        # Stays in DECONTAMINATION; needs more work.
        packet.history.append(RoleAction(
            role=Role.GUIDE.value,
            action="deferred",
            note=note or rationale or "needs more work before decision",
            timestamp=now,
        ))
    return packet


# ── Persistence (file-backed store) ──────────────────────────────────


def _default_store_dir() -> Path:
    override = os.environ.get("CONCORDANCE_QUARANTINE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "lw" / "quarantine"


class QuarantineStore:
    """File-backed quarantine packet store. One JSON per packet."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or _default_store_dir()

    def _ensure_dir(self) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        return self.base_dir

    def save(self, packet: QuarantinePacket) -> Path:
        d = self._ensure_dir()
        target = d / f"{packet.id}.json"
        target.write_text(
            json.dumps(packet.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return target

    def load(self, packet_id: str) -> Optional[QuarantinePacket]:
        f = self.base_dir / f"{packet_id}.json"
        if not f.exists():
            return None
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return QuarantinePacket.from_dict(data)
        except (OSError, json.JSONDecodeError):
            return None

    def list_all(self, *, zone: Optional[Zone] = None) -> List[QuarantinePacket]:
        if not self.base_dir.exists():
            return []
        out: List[QuarantinePacket] = []
        for f in sorted(self.base_dir.glob("q-*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                packet = QuarantinePacket.from_dict(data)
                if zone is None or packet.zone == zone.value:
                    out.append(packet)
            except (OSError, json.JSONDecodeError):
                continue
        return out

    def delete(self, packet_id: str) -> bool:
        f = self.base_dir / f"{packet_id}.json"
        if f.exists():
            f.unlink()
            return True
        return False


__all__ = [
    "Zone",
    "Role",
    "Decision",
    "QuarantineError",
    "QuarantinePacket",
    "RoleAction",
    "capture",
    "decontaminate",
    "admit",
    "QuarantineStore",
]
