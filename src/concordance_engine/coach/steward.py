"""coach.steward — the sovereign-gate plane.

Ported from `coach_fractal_os/steward.py` (iCloud_archive). The
Steward defines the corridor (the path), admits or denies wedge
requests via short-lived tokens, and emits append-only audit
packets for every decision. The Steward is the spirit-plane: it
clears and defines the path; the Coach plane (Main) operates
inside the corridor it sets.

Per the canonical spec (`COACH_FRACTAL_ARCH_SPEC_v1.md`):

  > Steward Plane (Steward) — Spirit
  > * Sovereign gate + corridor/policy engine
  > * "Clears and defines the path"
  > * Admits/denies boundary actions via short-lived tokens
  > * Logs all decisions append-only

The deterministic gate order on a wedge request (per
`COACH_STEWARD_PATH_CORRIDOR_POLICY_SPEC_v1.md`):

    1) Corridor binding + expiry
    2) Allowed wedge list
    3) Flow protect (don't break in-flow with high-level wedges)
    4) Dose limit (max per minute / min gap between)
    5) Escalation cap
    6) Mode lock
    7) Egress lock
    8) Admit → token mint + audit
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .protocol import (
    ActionToken,
    Decision,
    PacketStore,
    ReasonCode,
    WedgeRequest,
    new_id,
    now_ms,
)


# ── Policy + Corridor ───────────────────────────────────────────────


@dataclass(frozen=True)
class Corridor:
    """A session-scoped path the Coach operates inside.

    Fields:
      * `target` — what the corridor is for (success criteria)
      * `allowed_wedges` — only these wedge_ids may run
      * `constraints` — dose limits, escalation caps, mode/egress
        locks (canonical keys per the spec)
      * `expires_at_ms` — corridor TTL; expired corridors deny all
    """
    corridor_id: str
    target: Dict[str, Any]
    allowed_wedges: List[str]
    constraints: Dict[str, Any]
    expires_at_ms: int


@dataclass(frozen=True)
class StewardPolicy:
    """Tunables for the Steward. Defaults match the canonical spec."""
    # Token issuance
    token_ttl_ms: int = 15_000
    token_rate_limit_per_1m: int = 60
    wip_limit_active_sessions: int = 1000

    # Default corridor constraints (used when get_corridor falls back)
    default_max_interventions_per_min: int = 12
    default_min_ms_between_interventions: int = 2500
    default_max_escalations_per_min: int = 4
    default_mode_locked: bool = True
    default_egress_locked: bool = True

    # Flow protection: if user/child is "in flow", deny most wedges
    # above this level.
    flow_protect_enabled: bool = True
    flow_protect_max_level: int = 2


# ── Steward ─────────────────────────────────────────────────────────


class Steward:
    """The sovereign gate.

    Holds per-session corridor state, enforces the deterministic
    gate order, mints tokens on admission, validates+consumes them
    at execution time, and audits every decision via the PacketStore.
    """

    def __init__(self, policy: StewardPolicy, store: PacketStore):
        self.policy = policy
        self.store = store
        self._counter = 0

        self._token_issued_timestamps: List[int] = []
        self._used_tokens: Set[str] = set()

        # Per-session corridor + event window (both kept in memory;
        # the canonical record is the audit packets).
        self._corridors: Dict[str, Corridor] = {}
        self._session_events: Dict[str, List[Dict[str, Any]]] = {}

    # ── Corridor management ─────────────────────────────────────

    def set_corridor(self, session_id: str, corridor: Corridor) -> None:
        """Define (or replace) the corridor for a session."""
        self._corridors[session_id] = corridor
        self.store.append("coach_steward_directive_v1", {
            "session_id": session_id,
            "corridor_id": corridor.corridor_id,
            "target": corridor.target,
            "allowed_wedges": list(corridor.allowed_wedges),
            "constraints": dict(corridor.constraints),
            "expires_at_ms": corridor.expires_at_ms,
        })

    def get_corridor(self, session_id: str) -> Corridor:
        """Return the active corridor for a session, creating a
        default one if none exists. The default is conservative —
        designed for a one-hour reading session — and can be
        overridden by calling `set_corridor` with a custom one."""
        c = self._corridors.get(session_id)
        if c is None:
            c = Corridor(
                corridor_id=new_id(),
                target={"name": "default_session",
                        "success_criteria": {"minutes": 60}},
                allowed_wedges=["WAIT", "PROMPT", "REPEAT", "SEGMENT", "MODEL"],
                constraints={
                    "max_interventions_per_min": self.policy.default_max_interventions_per_min,
                    "min_ms_between_interventions": self.policy.default_min_ms_between_interventions,
                    "max_escalations_per_min": self.policy.default_max_escalations_per_min,
                    "mode_locked": self.policy.default_mode_locked,
                    "egress_locked": self.policy.default_egress_locked,
                },
                expires_at_ms=now_ms() + 60 * 60 * 1000,
            )
            self.set_corridor(session_id, c)
        return c

    # ── Internal: rate / dose / escalation tracking ──────────────

    def _rate_limit_ok(self, now: int) -> bool:
        window_ms = 60 * 1000
        self._token_issued_timestamps = [
            t for t in self._token_issued_timestamps if (now - t) <= window_ms
        ]
        return len(self._token_issued_timestamps) < self.policy.token_rate_limit_per_1m

    def _record_session_event(
        self, session_id: str, kind: str, level: int,
    ) -> None:
        self._session_events.setdefault(session_id, []).append({
            "t": now_ms(), "kind": kind, "level": level,
        })

    def _count_last_minute(self, session_id: str, predicate) -> int:
        now = now_ms()
        events = self._session_events.get(session_id, [])
        return sum(
            1 for e in events
            if (now - e["t"]) <= 60 * 1000 and predicate(e)
        )

    def _time_since_last_intervention_ms(
        self, session_id: str,
    ) -> Optional[int]:
        now = now_ms()
        events = self._session_events.get(session_id, [])
        last = None
        for e in reversed(events):
            if e["kind"] == "intervention":
                last = e
                break
        if last is None:
            return None
        return now - last["t"]

    # ── Admit / deny — the deterministic gate sequence ───────────

    def admit_or_deny(
        self,
        request: WedgeRequest,
        *,
        active_sessions_count: int,
        child_state: Dict[str, Any],
    ) -> Tuple[Decision, Optional[ActionToken], ReasonCode]:
        """Run the Steward's gate sequence. Returns the decision, an
        ActionToken (when admitted), and the canonical reason code.

        `child_state` carries the human/agent's current state — at
        minimum `in_flow: bool`, optionally `frustration: int`. The
        Steward uses this to decide flow-protection.
        """
        now = now_ms()

        # Gate 0a: WIP limit
        if active_sessions_count > self.policy.wip_limit_active_sessions:
            self._audit(request, Decision.DENY, ReasonCode.DENY_WIP_LIMIT,
                        notes="WIP_LIMIT")
            return Decision.DENY, None, ReasonCode.DENY_WIP_LIMIT

        # Gate 0b: rate limit on token issuance
        if not self._rate_limit_ok(now):
            self._audit(request, Decision.DENY, ReasonCode.DENY_RATE_LIMIT,
                        notes="TOKEN_RATE_LIMIT")
            return Decision.DENY, None, ReasonCode.DENY_RATE_LIMIT

        corridor = self.get_corridor(request.session_id)

        # Gate 1: corridor binding + expiry
        if request.corridor_id != corridor.corridor_id:
            self._audit(request, Decision.DENY, ReasonCode.DENY_CORRIDOR,
                        notes="CORRIDOR_MISMATCH")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR
        if now > corridor.expires_at_ms:
            self._audit(request, Decision.DENY, ReasonCode.DENY_CORRIDOR,
                        notes="CORRIDOR_EXPIRED")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR

        # Gate 2: allowed wedge list
        if request.wedge_id not in corridor.allowed_wedges:
            self._audit(request, Decision.DENY, ReasonCode.DENY_CORRIDOR,
                        notes="WEDGE_NOT_ALLOWED")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR

        # Gate 3: flow protect
        in_flow = bool(child_state.get("in_flow", False))
        if (self.policy.flow_protect_enabled and in_flow
                and request.wedge_level > self.policy.flow_protect_max_level):
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_FLOW_PROTECTED, notes="FLOW_PROTECT")
            return Decision.DENY, None, ReasonCode.DENY_FLOW_PROTECTED

        # Gate 4: dose limits
        max_per_min = int(corridor.constraints.get(
            "max_interventions_per_min", 999))
        per_min = self._count_last_minute(
            request.session_id, lambda e: e["kind"] == "intervention")
        if per_min >= max_per_min:
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_DOSE_LIMIT, notes="MAX_PER_MIN")
            return Decision.DENY, None, ReasonCode.DENY_DOSE_LIMIT

        min_gap = int(corridor.constraints.get(
            "min_ms_between_interventions", 0))
        since = self._time_since_last_intervention_ms(request.session_id)
        if since is not None and since < min_gap:
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_DOSE_LIMIT, notes="MIN_GAP")
            return Decision.DENY, None, ReasonCode.DENY_DOSE_LIMIT

        # Gate 5: escalation cap
        max_escalations = int(corridor.constraints.get(
            "max_escalations_per_min", 999))
        esc_per_min = self._count_last_minute(
            request.session_id, lambda e: e["kind"] == "escalation")
        if request.wedge_level >= 4 and esc_per_min >= max_escalations:
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_ESCALATION_CAP,
                        notes="ESCALATION_CAP")
            return Decision.DENY, None, ReasonCode.DENY_ESCALATION_CAP

        # Gate 6: mode lock
        if (corridor.constraints.get("mode_locked", False)
                and "mode_change" in request.risk_flags):
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_MODE_LOCK, notes="MODE_LOCK")
            return Decision.DENY, None, ReasonCode.DENY_MODE_LOCK

        # Gate 7: egress lock
        if (corridor.constraints.get("egress_locked", False)
                and "egress" in request.risk_flags):
            self._audit(request, Decision.DENY,
                        ReasonCode.DENY_EGRESS_LOCK, notes="EGRESS_LOCK")
            return Decision.DENY, None, ReasonCode.DENY_EGRESS_LOCK

        # Gate 8: admit → mint token
        self._counter += 1
        req_hash = request.hash()
        token = ActionToken(
            token_id=new_id(),
            request_hash=req_hash,
            issued_at_ms=now,
            expires_at_ms=now + self.policy.token_ttl_ms,
            steward_counter=self._counter,
            constraints=dict(corridor.constraints),
        )
        self._token_issued_timestamps.append(now)
        self._audit(request, Decision.ADMIT, ReasonCode.ALLOW_OK, token=token)
        return Decision.ADMIT, token, ReasonCode.ALLOW_OK

    # ── Validate + consume ──────────────────────────────────────

    def validate_and_consume(
        self, *, token: ActionToken, request: WedgeRequest,
    ) -> Tuple[bool, ReasonCode]:
        """Confirm a token is valid for THIS request and consume it.
        Tokens are single-use. Returns (ok, reason_code)."""
        now = now_ms()

        if token.token_id in self._used_tokens:
            return False, ReasonCode.DENY_TOKEN_ALREADY_USED

        if now > token.expires_at_ms:
            return False, ReasonCode.DENY_EXPIRED_TOKEN

        if token.request_hash != request.hash():
            return False, ReasonCode.DENY_TOKEN_MISMATCH

        self._used_tokens.add(token.token_id)
        self.store.append("coach_token_consumed_v1", {
            "session_id": request.session_id,
            "request_id": request.request_id,
            "token_id": token.token_id,
            "steward_counter": token.steward_counter,
        })

        # Update event windows for dose / escalation tracking.
        self._record_session_event(
            request.session_id, "intervention", request.wedge_level)
        if request.wedge_level >= 4:
            self._record_session_event(
                request.session_id, "escalation", request.wedge_level)

        return True, ReasonCode.ALLOW_OK

    # ── Audit (append-only) ─────────────────────────────────────

    def _audit(
        self,
        request: WedgeRequest,
        decision: Decision,
        reason: ReasonCode,
        *,
        notes: Optional[str] = None,
        token: Optional[ActionToken] = None,
    ) -> None:
        self.store.append("coach_wedge_admission_v1", {
            "request_id": request.request_id,
            "session_id": request.session_id,
            "corridor_id": request.corridor_id,
            "wedge_id": request.wedge_id,
            "wedge_level": request.wedge_level,
            "decision": decision.value,
            "reason_code": reason.value,
            "notes": notes,
            "token": token.to_dict() if token else None,
        })


__all__ = [
    "Corridor",
    "Steward",
    "StewardPolicy",
]
