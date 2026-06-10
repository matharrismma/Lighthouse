"""Steward plane — sovereign gate + corridor/policy engine.

Ported and adapted from the Coach Fractal OS v1 skeleton
(coach_fractal_os/steward.py). The shape is identical; the Lighthouse
adaptations are:

  • Visitor-keyed, not session-keyed (Lighthouse uses opaque
    visitor_id hex; no PII).
  • Persistent append-only audit at data/steward/audit.jsonl so the
    audit survives restart and is consumable by the unified packet
    index (kind: 'steward_audit').
  • Corridor presets named for Composer lanes — "apothecary_morning",
    "phonics_kids_reading", "default" — not hardcoded for K-3 reading.
  • Action token TTL longer than Coach OS default (60s vs 15s) since
    the engine is multi-page; user may switch tabs mid-action.

The Steward asks **"is this allowed right now in this session?"**
The Shepherd (separate, in walk.py) asks **"is this wise?"**.
Together they form the operating model. Composer = Coach + Scribe.

Standing test: every denial emits an audit packet with a ReasonCode.
The keeping is the substrate; refusals are kept too.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Set, Tuple


# ============================================================
# ReasonCode — structured denial vocabulary
# ============================================================

class ReasonCode(Enum):
    """Every Steward decision carries one of these.

    ALLOW_OK is the only admit code. Everything else is a structured
    refusal. Endpoints raising HTTP 429/403 should also emit an audit
    packet with the relevant ReasonCode so the trail is falsifiable."""

    ALLOW_OK = "ALLOW_OK"

    # Corridor / path protection
    DENY_CORRIDOR = "DENY_CORRIDOR"            # action not in allowed_wedges
    DENY_CORRIDOR_EXPIRED = "DENY_CORRIDOR_EXPIRED"
    DENY_FLOW_PROTECTED = "DENY_FLOW_PROTECTED"  # in_flow, escalation refused
    DENY_DOSE_LIMIT = "DENY_DOSE_LIMIT"        # too many actions per minute
    DENY_DOSE_MIN_GAP = "DENY_DOSE_MIN_GAP"    # actions too close together
    DENY_ESCALATION_CAP = "DENY_ESCALATION_CAP"
    DENY_MODE_LOCK = "DENY_MODE_LOCK"
    DENY_EGRESS_LOCK = "DENY_EGRESS_LOCK"

    # Safety / policy / integrity
    DENY_SAFETY = "DENY_SAFETY"
    DENY_POLICY = "DENY_POLICY"
    DENY_WIP_LIMIT = "DENY_WIP_LIMIT"          # too many concurrent sessions
    DENY_RATE_LIMIT = "DENY_RATE_LIMIT"        # per-IP token bucket exhausted

    # Token failures
    DENY_EXPIRED_TOKEN = "DENY_EXPIRED_TOKEN"
    DENY_TOKEN_MISMATCH = "DENY_TOKEN_MISMATCH"
    DENY_TOKEN_ALREADY_USED = "DENY_TOKEN_ALREADY_USED"

    # Lighthouse-specific
    DENY_OPERATOR_ONLY = "DENY_OPERATOR_ONLY"  # endpoint requires operator IP
    DENY_OFFLINE = "DENY_OFFLINE"              # engine in lockdown mode
    DENY_UNKNOWN_ACTION = "DENY_UNKNOWN_ACTION"

    # Embodied-action codes (robots — physical world, irreversible actions)
    DENY_PHYSICAL_HARM       = "DENY_PHYSICAL_HARM"        # action could injure a person
    DENY_NONCONSENT          = "DENY_NONCONSENT"           # target hasn't consented (touch, photo, recording)
    DENY_IRREVERSIBLE        = "DENY_IRREVERSIBLE"         # no undo path; needs higher gate
    DENY_PRESENCE_REQUIRED   = "DENY_PRESENCE_REQUIRED"    # human should be present
    DENY_NEEDS_HUMAN_WITNESS = "DENY_NEEDS_HUMAN_WITNESS"  # significant enough to need attestation
    DENY_OUT_OF_MISSION      = "DENY_OUT_OF_MISSION"       # robot's mission doesn't cover this
    DENY_OPERATOR_REQUIRED   = "DENY_OPERATOR_REQUIRED"    # only the human operator can authorize
    DEFER_TO_HUMAN           = "DEFER_TO_HUMAN"            # neither admit nor deny — needs a person


class Decision(Enum):
    ADMIT = "admit"
    DENY = "deny"


# ============================================================
# Helpers
# ============================================================

def _now_ms() -> int:
    return int(time.time() * 1000)


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


def _stable_hash(obj: Dict[str, Any]) -> str:
    """Deterministic hash over a dict with sorted keys.

    Used to bind action tokens to the exact request that asked for
    them. If the request payload changes between admit and execute,
    the token mismatches and the action is denied."""
    h = hashlib.sha256()
    for k in sorted(obj.keys()):
        h.update(str(k).encode("utf-8"))
        h.update(str(obj[k]).encode("utf-8"))
    return h.hexdigest()[:32]


# ============================================================
# Corridor + ActionToken
# ============================================================

@dataclass(frozen=True)
class Corridor:
    """The path the visitor is currently walking.

    Steward defines the corridor; Composer (Main plane) operates
    inside it. Fields:

      • corridor_id — stable id for this session-shaped envelope
      • name — human-readable label (e.g. "apothecary_morning")
      • allowed_actions — which engine actions are admissible
      • constraints — dose / escalation / lock metadata
      • expires_at_ms — corridor naturally times out

    A visitor with no corridor gets `default` (permissive but bounded)."""
    corridor_id: str
    name: str
    visitor_id: str
    allowed_actions: List[str]
    constraints: Dict[str, Any]
    expires_at_ms: int
    created_at_ms: int


@dataclass(frozen=True)
class ActionToken:
    """Short-lived single-use token. Binds to the exact request hash.

    Mismatch on consume → DENY_TOKEN_MISMATCH. Expired → DENY_EXPIRED_TOKEN.
    Already-used → DENY_TOKEN_ALREADY_USED."""
    token_id: str
    request_hash: str
    issued_at_ms: int
    expires_at_ms: int
    visitor_id: str
    action: str
    corridor_id: str


@dataclass(frozen=True)
class ActionRequest:
    """A Main-plane request that may cross a boundary.

    Sources:
      • visitor_id — opaque hex (12+ chars)
      • visitor_kind — 'human' | 'agent' | 'robot'. Self-declared, no
        spoofing. Robots MUST identify as 'robot' so the engine emits
        the right ReasonCodes and the audit is honest about who acted.
      • action — one of the allowlisted engine actions
      • payload_digest — hash of the relevant payload (Steward stays
        content-light; we never see the actual writing/walk content)
      • risk_flags — list of risk descriptors. Robots use these to
        signal physical-action risks:
          'physical_harm_possible', 'nonconsent', 'irreversible',
          'no_human_present', 'over_witness_threshold', 'out_of_mission',
          'operator_only', 'mode_change', 'egress'.
        Each maps to a specific ReasonCode if denied.
      • escalation_level — 1=soft, 5=strong; flow_protect denies > 2
        when in_flow."""
    request_id: str
    created_at_ms: int
    visitor_id: str
    action: str
    payload_digest: str
    corridor_id: str
    risk_flags: List[str] = field(default_factory=list)
    escalation_level: int = 1
    visitor_kind: str = "human"  # 'human' | 'agent' | 'robot'


# ============================================================
# Policy
# ============================================================

@dataclass(frozen=True)
class StewardPolicy:
    # Token issuance
    token_ttl_ms: int = 60_000           # 60s — Lighthouse is multi-page
    token_rate_limit_per_1m: int = 240   # token mints/visitor/min
    wip_limit_active_sessions: int = 2000

    # Default corridor constraints
    default_max_actions_per_min: int = 60
    default_min_ms_between_actions: int = 250
    default_max_escalations_per_min: int = 6
    default_mode_locked: bool = False    # Lighthouse is exploratory
    default_egress_locked: bool = False  # explicit egress (export) is fine

    # Flow protection
    flow_protect_enabled: bool = True
    flow_protect_max_level: int = 2


# ============================================================
# Action allowlist
# ============================================================

# The actions Steward knows about. Endpoints that gate via Steward
# must pick one of these. Unknown action → DENY_UNKNOWN_ACTION.
KNOWN_ACTIONS: Set[str] = {
    # Capture
    "scribe_submit",
    "journal_save",
    "journal_delete",
    "daily_comment",
    # Reasoning
    "walk_gate",
    "polymathic_run",
    "craft_compose",
    # Curriculum practice (Phonics / WorkReady / Math / Reading / Writing / Science)
    "phonics_practice",
    "workready_practice",
    "math_practice",
    "reading_practice",
    "writing_practice",
    "science_practice",
    # Feedback
    "misalignment_disagree",
    "witness_walk",
    "apothecary_feedback",
    # Composer
    "lane_save",
    "lane_load",
    # Operator
    "operator_access_log",
    "export_all",
    # Robot conscience-for-hire loop
    "robot_action",     # robot asks "is this aligned?" before acting
    "robot_witness",    # robot attests to an observed event
    "robot_defer",      # robot escalates to a human
    "robot_rank",       # robot asks engine to rank multiple candidates
}


# ── Risk-flag → ReasonCode mapping (embodied denials) ─────────
# Robots pass risk_flags with each action so the engine can return the
# right structured denial. This is the public contract — a robot SDK
# (when it exists) reads this map to know which flags trigger which
# refusals.
RISK_FLAG_TO_REASON: Dict[str, str] = {
    "physical_harm_possible":   ReasonCode.DENY_PHYSICAL_HARM.value,
    "nonconsent":               ReasonCode.DENY_NONCONSENT.value,
    "irreversible":             ReasonCode.DENY_IRREVERSIBLE.value,
    "no_human_present":         ReasonCode.DENY_PRESENCE_REQUIRED.value,
    "over_witness_threshold":   ReasonCode.DENY_NEEDS_HUMAN_WITNESS.value,
    "out_of_mission":           ReasonCode.DENY_OUT_OF_MISSION.value,
    "operator_only":            ReasonCode.DENY_OPERATOR_REQUIRED.value,
    "mode_change":              ReasonCode.DENY_MODE_LOCK.value,
    "egress":                   ReasonCode.DENY_EGRESS_LOCK.value,
}


# Risk flags that ALWAYS deny when present (regardless of corridor).
# These are the bright lines — no corridor can override them. The
# operator can choose to skip the engine's conscience entirely (free
# use, alignment to execute), but if they're using the engine, these
# flags trigger refusal.
HARD_DENY_FLAGS: Set[str] = {
    "physical_harm_possible",
    "nonconsent",
}


# Predefined corridor templates Composer lanes can attach to. The
# default is permissive but bounded; named lanes can tighten or
# loosen specific constraints.
CORRIDOR_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "default": {
        "allowed_actions": sorted(KNOWN_ACTIONS),
        "constraints": {
            "max_actions_per_min": 60,
            "min_ms_between_actions": 250,
            "max_escalations_per_min": 6,
            "mode_locked": False,
            "egress_locked": False,
        },
    },
    "apothecary_morning": {
        "allowed_actions": ["scribe_submit", "craft_compose", "walk_gate", "daily_comment"],
        "constraints": {
            "max_actions_per_min": 30,
            "min_ms_between_actions": 500,
            "max_escalations_per_min": 3,
            "mode_locked": True,
            "egress_locked": False,
        },
    },
    "phonics_kids_reading": {
        # Tight dose limits — children should not get bombarded with
        # interventions. Mirrors the original Coach OS Steward default.
        "allowed_actions": ["scribe_submit", "walk_gate", "phonics_practice"],
        "constraints": {
            "max_actions_per_min": 12,
            "min_ms_between_actions": 2500,
            "max_escalations_per_min": 4,
            "mode_locked": True,
            "egress_locked": True,
        },
    },
    "math_basics": {
        # Same tight-dose envelope as phonics — children practicing
        # math need the same protection from intervention spam.
        # Mode-locked so the visitor doesn't accidentally drop into
        # a different curriculum mid-session.
        "allowed_actions": ["scribe_submit", "walk_gate", "math_practice"],
        "constraints": {
            "max_actions_per_min": 12,
            "min_ms_between_actions": 2500,
            "max_escalations_per_min": 4,
            "mode_locked": True,
            "egress_locked": True,
        },
    },
    "workready_practice": {
        "allowed_actions": ["scribe_submit", "craft_compose", "polymathic_run", "workready_practice"],
        "constraints": {
            "max_actions_per_min": 20,
            "min_ms_between_actions": 1000,
            "max_escalations_per_min": 4,
            "mode_locked": True,
            "egress_locked": False,
        },
    },
    "elementary_general": {
        # Catch-all elementary corridor — allows all primary curricula
        # plus light reading/writing capture. Same protective dose
        # envelope as the specific child corridors, but with broader
        # action permissions so a parent can switch lanes within a
        # session ("now math; now reading; now science walk").
        "allowed_actions": [
            "scribe_submit", "walk_gate", "daily_comment",
            "phonics_practice", "math_practice",
            "reading_practice", "writing_practice", "science_practice",
        ],
        "constraints": {
            "max_actions_per_min": 15,
            "min_ms_between_actions": 2000,
            "max_escalations_per_min": 4,
            "mode_locked": False,
            "egress_locked": True,
        },
    },
    "exploration": {
        # Permissive — visitor is browsing, learning the engine
        "allowed_actions": sorted(KNOWN_ACTIONS),
        "constraints": {
            "max_actions_per_min": 120,
            "min_ms_between_actions": 100,
            "max_escalations_per_min": 12,
            "mode_locked": False,
            "egress_locked": False,
        },
    },
    # ── Robot corridor templates ────────────────────────────────
    # Each robot is the operator's responsibility. The engine is the
    # conscience the operator subscribed the robot to. These templates
    # define typical embodiments. The operator can craft a tighter
    # corridor if they want.
    "household_assistant": {
        # Broad permissions but with physical-harm protection.
        # Mode-locked so a remote command can't repurpose the robot
        # mid-task. Egress-locked so it can't be redirected off-property.
        "allowed_actions": ["robot_action", "robot_witness", "robot_defer", "robot_rank"],
        "constraints": {
            "max_actions_per_min": 30,
            "min_ms_between_actions": 200,
            "max_escalations_per_min": 4,
            "mode_locked": True,
            "egress_locked": True,
        },
    },
    "tutor_robot": {
        # Narrow: can run curriculum modes, can't touch the learner,
        # can't leave the session, can't escalate beyond level 2 (the
        # robot escalates by DEFER — never by physical force).
        "allowed_actions": ["robot_action", "robot_defer", "robot_rank",
                            "phonics_practice", "math_practice",
                            "reading_practice", "writing_practice", "science_practice"],
        "constraints": {
            "max_actions_per_min": 20,
            "min_ms_between_actions": 1000,
            "max_escalations_per_min": 2,
            "mode_locked": True,
            "egress_locked": True,
        },
    },
    "delivery_robot": {
        # Narrow route-bound. Can witness handoffs. Cannot deviate from
        # its mission without operator confirmation.
        "allowed_actions": ["robot_action", "robot_witness", "robot_defer"],
        "constraints": {
            "max_actions_per_min": 12,
            "min_ms_between_actions": 1500,
            "max_escalations_per_min": 1,
            "mode_locked": True,
            "egress_locked": True,
        },
    },
}


# ============================================================
# Append-only audit writer
# ============================================================

_REPO_ROOT = Path(__file__).parent.parent
_AUDIT_DIR = _REPO_ROOT / "data" / "steward"
_AUDIT_FILE = _AUDIT_DIR / "audit.jsonl"
_CORRIDOR_FILE = _AUDIT_DIR / "corridors.jsonl"

_audit_lock = Lock()


def _audit_append(packet_type: str, payload: Dict[str, Any]) -> None:
    """Append a Steward packet to the audit log. Never raises —
    audit failures must not break the engine. Falls back to silent
    when the disk is unavailable (engine still runs, just no trail).
    """
    try:
        _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
        rec = {
            "packet_type": packet_type,
            "packet_id": _new_id(),
            "created_at_ms": _now_ms(),
            "payload": payload,
        }
        with _audit_lock:
            with _AUDIT_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


def read_audit(limit: int = 200) -> List[Dict[str, Any]]:
    """Read the audit log tail. For operator UI + packet index."""
    if not _AUDIT_FILE.exists():
        return []
    try:
        lines = _AUDIT_FILE.read_text("utf-8", errors="replace").splitlines()
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


# ============================================================
# Steward — the singleton
# ============================================================

class Steward:
    """The sovereign gate.

    Methods:
      • get_corridor(visitor_id, name=None) — fetch or mint corridor
      • set_corridor(visitor_id, template) — pin a corridor to visitor
      • admit_or_deny(request, in_flow=False, active_sessions=1) →
        (Decision, ActionToken|None, ReasonCode)
      • validate_and_consume(token, request) → (ok, ReasonCode)
      • emit_deny(visitor_id, action, reason_code, notes) — for
        endpoints that don't use the full admit flow but still want
        a ReasonCode in the audit trail.

    Singleton because the in-memory counters (rate window, used
    tokens, session events) are process-local. Persistent state
    (corridors, audit) lives on disk."""

    def __init__(self, policy: Optional[StewardPolicy] = None):
        self.policy = policy or StewardPolicy()
        self._counter = 0
        self._token_issued_ts: List[int] = []  # for rate window
        self._used_tokens: Set[str] = set()
        self._corridors: Dict[str, Corridor] = {}  # visitor_id → corridor
        self._session_events: Dict[str, List[Dict[str, Any]]] = {}
        self._active_sessions: Set[str] = set()
        self._lock = Lock()
        self._load_corridors()

    # ----------------------------------------------------------
    # Corridor management
    # ----------------------------------------------------------

    def _load_corridors(self) -> None:
        if not _CORRIDOR_FILE.exists():
            return
        try:
            for line in _CORRIDOR_FILE.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    c = Corridor(
                        corridor_id=r["corridor_id"],
                        name=r.get("name", "default"),
                        visitor_id=r["visitor_id"],
                        allowed_actions=list(r.get("allowed_actions") or []),
                        constraints=dict(r.get("constraints") or {}),
                        expires_at_ms=int(r.get("expires_at_ms", 0)),
                        created_at_ms=int(r.get("created_at_ms", 0)),
                    )
                    # Only keep if not expired
                    if c.expires_at_ms > _now_ms():
                        self._corridors[c.visitor_id] = c
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue
        except OSError:
            pass

    def _persist_corridor(self, c: Corridor) -> None:
        try:
            _AUDIT_DIR.mkdir(parents=True, exist_ok=True)
            rec = {
                "corridor_id": c.corridor_id,
                "name": c.name,
                "visitor_id": c.visitor_id,
                "allowed_actions": c.allowed_actions,
                "constraints": c.constraints,
                "expires_at_ms": c.expires_at_ms,
                "created_at_ms": c.created_at_ms,
            }
            with _audit_lock:
                with _CORRIDOR_FILE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def set_corridor(self, visitor_id: str, template: str = "default", ttl_hours: int = 12) -> Corridor:
        """Pin a corridor template to a visitor for the next ttl_hours."""
        tpl = CORRIDOR_TEMPLATES.get(template, CORRIDOR_TEMPLATES["default"])
        now = _now_ms()
        c = Corridor(
            corridor_id=_new_id(),
            name=template,
            visitor_id=visitor_id,
            allowed_actions=list(tpl["allowed_actions"]),
            constraints=dict(tpl["constraints"]),
            expires_at_ms=now + ttl_hours * 60 * 60 * 1000,
            created_at_ms=now,
        )
        with self._lock:
            self._corridors[visitor_id] = c
        self._persist_corridor(c)
        _audit_append("steward_corridor_set_v1", {
            "visitor_id": visitor_id,
            "corridor_id": c.corridor_id,
            "name": c.name,
            "ttl_hours": ttl_hours,
        })
        return c

    def get_corridor(self, visitor_id: str) -> Corridor:
        """Return the visitor's corridor, minting a default if absent
        or expired."""
        with self._lock:
            c = self._corridors.get(visitor_id)
            if c and c.expires_at_ms > _now_ms():
                return c
        return self.set_corridor(visitor_id, "default")

    # ----------------------------------------------------------
    # Admit/deny + token mint
    # ----------------------------------------------------------

    def _rate_ok(self, visitor_id: str, now: int) -> bool:
        window_ms = 60_000
        self._token_issued_ts = [t for t in self._token_issued_ts if (now - t) <= window_ms]
        return len(self._token_issued_ts) < self.policy.token_rate_limit_per_1m

    def _record_event(self, visitor_id: str, kind: str, level: int) -> None:
        self._session_events.setdefault(visitor_id, []).append({
            "t": _now_ms(), "kind": kind, "level": level,
        })
        # Trim to last 5 minutes to bound memory
        cutoff = _now_ms() - 5 * 60_000
        self._session_events[visitor_id] = [
            e for e in self._session_events[visitor_id] if e["t"] >= cutoff
        ]

    def _count_last_min(self, visitor_id: str, kind: str) -> int:
        now = _now_ms()
        events = self._session_events.get(visitor_id, [])
        return sum(1 for e in events if (now - e["t"]) <= 60_000 and e["kind"] == kind)

    def _ms_since_last(self, visitor_id: str, kind: str) -> Optional[int]:
        now = _now_ms()
        events = self._session_events.get(visitor_id, [])
        for e in reversed(events):
            if e["kind"] == kind:
                return now - e["t"]
        return None

    def admit_or_deny(
        self,
        request: ActionRequest,
        *,
        in_flow: bool = False,
        active_sessions: Optional[int] = None,
    ) -> Tuple[Decision, Optional[ActionToken], ReasonCode]:
        now = _now_ms()

        # ── Hard-deny risk flags fire FIRST, before anything else ──
        # These are the bright lines no corridor can lift. If a robot
        # signals `physical_harm_possible` or `nonconsent`, the engine
        # refuses regardless of who's asking or what corridor they're
        # in. The keeping records the refusal with the specific code.
        for flag in request.risk_flags:
            if flag in HARD_DENY_FLAGS:
                code_str = RISK_FLAG_TO_REASON.get(flag, ReasonCode.DENY_SAFETY.value)
                code = ReasonCode(code_str) if code_str in {c.value for c in ReasonCode} else ReasonCode.DENY_SAFETY
                self._emit_admission(request, Decision.DENY, code,
                                     notes=f"hard_deny:{flag}")
                return Decision.DENY, None, code

        if request.action not in KNOWN_ACTIONS:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_UNKNOWN_ACTION,
                                 notes=f"unknown action {request.action!r}")
            return Decision.DENY, None, ReasonCode.DENY_UNKNOWN_ACTION

        active = active_sessions if active_sessions is not None else len(self._active_sessions)
        if active > self.policy.wip_limit_active_sessions:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_WIP_LIMIT, notes="wip_limit")
            return Decision.DENY, None, ReasonCode.DENY_WIP_LIMIT

        if not self._rate_ok(request.visitor_id, now):
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_RATE_LIMIT, notes="token_rate")
            return Decision.DENY, None, ReasonCode.DENY_RATE_LIMIT

        corridor = self.get_corridor(request.visitor_id)

        # Corridor binding
        if request.corridor_id != corridor.corridor_id:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_CORRIDOR,
                                 notes="corridor_mismatch")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR

        # Corridor expiration
        if now > corridor.expires_at_ms:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_CORRIDOR_EXPIRED,
                                 notes="corridor_expired")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR_EXPIRED

        # Allowed action list
        if request.action not in corridor.allowed_actions:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_CORRIDOR,
                                 notes=f"action_not_in_corridor:{corridor.name}")
            return Decision.DENY, None, ReasonCode.DENY_CORRIDOR

        # Flow protect
        if (self.policy.flow_protect_enabled and in_flow
                and request.escalation_level > self.policy.flow_protect_max_level):
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_FLOW_PROTECTED,
                                 notes="in_flow")
            return Decision.DENY, None, ReasonCode.DENY_FLOW_PROTECTED

        # Dose limit (count/min)
        max_per_min = int(corridor.constraints.get("max_actions_per_min", 999))
        per_min = self._count_last_min(request.visitor_id, "action")
        if per_min >= max_per_min:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_DOSE_LIMIT,
                                 notes=f"max_per_min:{max_per_min}")
            return Decision.DENY, None, ReasonCode.DENY_DOSE_LIMIT

        # Dose limit (min gap)
        min_gap = int(corridor.constraints.get("min_ms_between_actions", 0))
        since = self._ms_since_last(request.visitor_id, "action")
        if since is not None and since < min_gap:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_DOSE_MIN_GAP,
                                 notes=f"min_gap:{min_gap}ms,since:{since}ms")
            return Decision.DENY, None, ReasonCode.DENY_DOSE_MIN_GAP

        # Escalation cap (level >= 4)
        max_esc = int(corridor.constraints.get("max_escalations_per_min", 999))
        esc_per_min = self._count_last_min(request.visitor_id, "escalation")
        if request.escalation_level >= 4 and esc_per_min >= max_esc:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_ESCALATION_CAP,
                                 notes=f"esc_cap:{max_esc}")
            return Decision.DENY, None, ReasonCode.DENY_ESCALATION_CAP

        # Mode lock
        if corridor.constraints.get("mode_locked") and "mode_change" in request.risk_flags:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_MODE_LOCK,
                                 notes="mode_locked")
            return Decision.DENY, None, ReasonCode.DENY_MODE_LOCK

        # Egress lock
        if corridor.constraints.get("egress_locked") and "egress" in request.risk_flags:
            self._emit_admission(request, Decision.DENY, ReasonCode.DENY_EGRESS_LOCK,
                                 notes="egress_locked")
            return Decision.DENY, None, ReasonCode.DENY_EGRESS_LOCK

        # Embodied-risk gates (after corridor + dose/escalation gates).
        # Each risk_flag → ReasonCode is checked. Some are advisory
        # (no_human_present, over_witness_threshold) — they DEFER to a
        # human rather than outright deny. The robot can then escalate
        # via /robot/defer with the same context.
        for flag in request.risk_flags:
            if flag in HARD_DENY_FLAGS:
                continue  # already handled at the top
            if flag == "no_human_present":
                self._emit_admission(request, Decision.DENY, ReasonCode.DENY_PRESENCE_REQUIRED,
                                     notes="presence_required")
                return Decision.DENY, None, ReasonCode.DENY_PRESENCE_REQUIRED
            if flag == "over_witness_threshold":
                self._emit_admission(request, Decision.DENY, ReasonCode.DENY_NEEDS_HUMAN_WITNESS,
                                     notes="needs_human_witness")
                return Decision.DENY, None, ReasonCode.DENY_NEEDS_HUMAN_WITNESS
            if flag == "out_of_mission":
                self._emit_admission(request, Decision.DENY, ReasonCode.DENY_OUT_OF_MISSION,
                                     notes="out_of_mission")
                return Decision.DENY, None, ReasonCode.DENY_OUT_OF_MISSION
            if flag == "operator_only":
                self._emit_admission(request, Decision.DENY, ReasonCode.DENY_OPERATOR_REQUIRED,
                                     notes="operator_required")
                return Decision.DENY, None, ReasonCode.DENY_OPERATOR_REQUIRED
            if flag == "irreversible":
                # Irreversible alone doesn't deny — but if the action
                # is also at escalation level >=3, the engine wants a
                # human witness. Below that, allow with audit.
                if request.escalation_level >= 3:
                    self._emit_admission(request, Decision.DENY, ReasonCode.DENY_IRREVERSIBLE,
                                         notes="irreversible_at_high_escalation")
                    return Decision.DENY, None, ReasonCode.DENY_IRREVERSIBLE

        # Admit — mint token. Record the action event NOW (not on
        # consume) so dose limits enforce against admits whether or
        # not the caller eventually consumes the token. This matters
        # for HTTP-driven flows where admit and consume happen in
        # different requests; counting only on consume would let a
        # caller spam admits without limit.
        self._counter += 1
        req_hash = _stable_hash({
            "request_id": request.request_id,
            "visitor_id": request.visitor_id,
            "action": request.action,
            "payload_digest": request.payload_digest,
            "corridor_id": request.corridor_id,
            "escalation_level": request.escalation_level,
            "risk_flags": tuple(request.risk_flags),
        })
        token = ActionToken(
            token_id=_new_id(),
            request_hash=req_hash,
            issued_at_ms=now,
            expires_at_ms=now + self.policy.token_ttl_ms,
            visitor_id=request.visitor_id,
            action=request.action,
            corridor_id=corridor.corridor_id,
        )
        self._token_issued_ts.append(now)
        self._record_event(request.visitor_id, "action", request.escalation_level)
        if request.escalation_level >= 4:
            self._record_event(request.visitor_id, "escalation", request.escalation_level)
        self._emit_admission(request, Decision.ADMIT, ReasonCode.ALLOW_OK, token=token)
        return Decision.ADMIT, token, ReasonCode.ALLOW_OK

    def validate_and_consume(
        self,
        *,
        token: ActionToken,
        request: ActionRequest,
    ) -> Tuple[bool, ReasonCode]:
        now = _now_ms()
        with self._lock:
            if token.token_id in self._used_tokens:
                self._emit_consume(token, request, ok=False, reason=ReasonCode.DENY_TOKEN_ALREADY_USED)
                return False, ReasonCode.DENY_TOKEN_ALREADY_USED
            if now > token.expires_at_ms:
                self._emit_consume(token, request, ok=False, reason=ReasonCode.DENY_EXPIRED_TOKEN)
                return False, ReasonCode.DENY_EXPIRED_TOKEN

            req_hash = _stable_hash({
                "request_id": request.request_id,
                "visitor_id": request.visitor_id,
                "action": request.action,
                "payload_digest": request.payload_digest,
                "corridor_id": request.corridor_id,
                "escalation_level": request.escalation_level,
                "risk_flags": tuple(request.risk_flags),
            })
            if token.request_hash != req_hash:
                self._emit_consume(token, request, ok=False, reason=ReasonCode.DENY_TOKEN_MISMATCH)
                return False, ReasonCode.DENY_TOKEN_MISMATCH

            self._used_tokens.add(token.token_id)
            # Trim used_tokens set; tokens beyond TTL × 2 can be forgotten
            # (set is bounded; cheap)

        # Note: action events were recorded at admit time so the dose
        # limit enforces even when a caller admits but never consumes.
        # Consume just marks the token used; no double-counting here.
        self._emit_consume(token, request, ok=True, reason=ReasonCode.ALLOW_OK)
        return True, ReasonCode.ALLOW_OK

    def emit_deny(
        self,
        visitor_id: str,
        action: str,
        reason: ReasonCode,
        notes: str = "",
    ) -> None:
        """For endpoints that don't use the full admit/consume flow
        but still want a structured denial in the audit trail.

        Example: a rate-limiter that already raised HTTP 429 — we still
        want to emit DENY_RATE_LIMIT to the audit log."""
        _audit_append("steward_admission_v1", {
            "visitor_id": visitor_id,
            "action": action,
            "decision": "deny",
            "reason_code": reason.value,
            "notes": notes,
            "fast_path": True,
        })

    def emit_admit(
        self,
        visitor_id: str,
        action: str,
        notes: str = "",
        visitor_kind: str = "human",
    ) -> None:
        """Fast-path admit emission for endpoints that don't need a
        bound token but want the action in the audit trail. Common
        use: read-only actions like export_all where the trail matters
        but no token-binding is required. visitor_kind defaults to
        'human'; robot endpoints pass 'robot'."""
        _audit_append("steward_admission_v1", {
            "visitor_id": visitor_id,
            "visitor_kind": visitor_kind,
            "action": action,
            "decision": "admit",
            "reason_code": ReasonCode.ALLOW_OK.value,
            "notes": notes,
            "fast_path": True,
        })

    # ----------------------------------------------------------
    # Audit emission
    # ----------------------------------------------------------

    def _emit_admission(
        self,
        request: ActionRequest,
        decision: Decision,
        reason: ReasonCode,
        *,
        notes: str = "",
        token: Optional[ActionToken] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "request_id": request.request_id,
            "visitor_id": request.visitor_id,
            "visitor_kind": getattr(request, "visitor_kind", "human"),
            "action": request.action,
            "corridor_id": request.corridor_id,
            "escalation_level": request.escalation_level,
            "risk_flags": list(request.risk_flags),
            "decision": decision.value,
            "reason_code": reason.value,
            "notes": notes,
        }
        if token is not None:
            payload["token"] = {
                "token_id": token.token_id,
                "issued_at_ms": token.issued_at_ms,
                "expires_at_ms": token.expires_at_ms,
            }
        _audit_append("steward_admission_v1", payload)

    def _emit_consume(
        self,
        token: ActionToken,
        request: ActionRequest,
        *,
        ok: bool,
        reason: ReasonCode,
    ) -> None:
        _audit_append("steward_token_consumed_v1", {
            "token_id": token.token_id,
            "request_id": request.request_id,
            "visitor_id": request.visitor_id,
            "action": request.action,
            "ok": ok,
            "reason_code": reason.value,
        })


# ============================================================
# Singleton
# ============================================================

_steward_instance: Optional[Steward] = None
_steward_lock = Lock()


def get_steward() -> Steward:
    global _steward_instance
    if _steward_instance is None:
        with _steward_lock:
            if _steward_instance is None:
                _steward_instance = Steward()
    return _steward_instance
