"""coach — the engine's core two-plane architecture.

Per Matt 2026-05-03: *"The coach module is a core. We are coaching
and programming. We take their disorder and make order. We allow them
to tap into what makes them special. We are the conduit."*

This package ports `coach_fractal_os` (the canonical reference at
iCloud_archive/_inspect/coach_fractal_os_v1_extracted/) into the live
engine as a first-class module.

Architecture:

  ┌──────────────────────────────────────────────┐
  │  MAIN PLANE  —  Coach + Scribe (mind/body)   │
  │  • relational; runs the user's session       │
  │  • captures raw input (Scribe)               │
  │  • suggests candidate moves (Coach)          │
  │  • produces WedgeRequests at the boundary    │
  └──────────────────────────────────────────────┘
                       │
                       │  request → admit/deny → token → execute → log
                       ▼
  ┌──────────────────────────────────────────────┐
  │  STEWARD PLANE  —  sovereign gate (spirit)   │
  │  • defines the corridor (target + allowed    │
  │    wedges + constraints + expiry)            │
  │  • admits or denies via short-lived tokens   │
  │  • emits append-only audit packets           │
  └──────────────────────────────────────────────┘

Three minimal abstractions:

  * **Corridor** — a session-scoped path with a target, allowed
    wedges, dose/escalation/mode/egress constraints, and a TTL.
  * **WedgeRequest** — Main plane's request to perform a wedge
    (an action) inside the active corridor.
  * **ActionToken** — short-lived, single-use, request-hash-bound
    admission token issued by the Steward when the wedge is allowed.

What this gives the engine that it didn't have before:

  * **Sovereign-gate enforcement at runtime, not just at packet
    submission.** Today the engine runs four gates on a packet when
    asked. With the Steward plane, every action a Coach (human or
    agent) wants to take must request admission — and an action
    without a valid token cannot execute. Constraint reveals
    alignment.

  * **Per-session corridors.** A user opens a session with a target;
    the Steward defines the path; the Coach operates inside it. Drift
    becomes physically impossible (the token won't issue) rather than
    only detectable after the fact.

  * **Dose / escalation / mode / egress locks.** From the Coach OS
    spec — corridor constraints that prevent runaway interventions,
    escalation cascades, mode-flips, and unauthorized exits. These
    are runtime physics, not policy notes.

The packetization here mirrors the canonical Coach OS spec but uses
the engine's existing vocabulary where it overlaps (Anchor, Witness,
Audit Chain).
"""

from .protocol import (
    ActionToken,
    Decision,
    Plane,
    ReasonCode,
    WedgeRequest,
    new_id,
    now_ms,
    stable_hash,
)
from .steward import (
    Corridor,
    Steward,
    StewardPolicy,
)

__all__ = [
    "ActionToken",
    "Corridor",
    "Decision",
    "Plane",
    "ReasonCode",
    "Steward",
    "StewardPolicy",
    "WedgeRequest",
    "new_id",
    "now_ms",
    "stable_hash",
]
