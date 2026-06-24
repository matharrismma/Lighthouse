"""autonomy.py — a control-loop governor for autonomous agents.

Control theory for autonomous systems, made into a discipline an agent can wrap
its own loop in (teaching: control_theory_for_autonomous_systems). It closes the
loop around an explicit REFERENCE (the true goal), keeps it STABLE (a Lyapunov-
style convergence/drift check — stop when converged, stop when drifting, never
run away), BOUNDS actuation, FAILS SAFE on uncertainty (when the signal is bad,
hold — never actuate on a guess), records every tick (OBSERVABILITY), and refuses
to self-authorize irreversible/outward actions: the highest loop closes around
authority (the gates / a human / God), never the agent itself. No finite
autonomous regulator is sufficient unto itself.

This is the cybernetic form of alignment: an autonomous goal-seeker with no human
in the loop is exactly where things go wrong (Goodhart, reward-hacking, drift,
runaway). The governor is the antidote, in code.

Sovereign: stdlib only.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

CONTINUE = "continue"
STOP = "stop"
HOLD = "hold"  # fail-safe: do NOT actuate this tick

# Outward / irreversible actions the governor will NEVER auto-authorize — they must
# go up to authority (the BROTHERS/GOD gates, or a human). Mirrors the safety
# boundary: the loop is a servant under authority, not the final authority.
GATED = ("send", "publish", "post", "delete", "pay", "transfer", "purchase",
         "withdraw", "deposit", "trade", "grant", "share", "email", "submit",
         "deploy_public", "broadcast")


@dataclass
class Tick:
    i: int
    error: float          # distance-to-goal; lower is better, 0 = reached
    acted: bool
    note: str
    decision: str         # CONTINUE | STOP | HOLD
    reason: str
    ts: int

    def as_dict(self) -> Dict[str, Any]:
        return {"i": self.i, "error": self.error, "acted": self.acted,
                "note": self.note, "decision": self.decision,
                "reason": self.reason, "ts": self.ts}


@dataclass
class Governor:
    """Wrap an autonomous loop. Call tick(error) each iteration; obey the decision.

    error = a scalar 'distance to the goal' (work remaining, dissonance, |setpoint
    - output|). The loop's job is to drive it down. The governor decides when to
    keep going, when to stop (converged / drifting / bounded), and when to hold.
    """
    reference: str                         # the TRUE goal, stated explicitly
    tolerance: float = 0.0                 # error <= tolerance  => converged, STOP
    max_ticks: int = 100                   # hard runaway bound
    patience: int = 3                      # non-improving ticks tolerated before STOP
    max_actuation_per_tick: float = 1.0    # bounded actuation magnitude
    history: List[Tick] = field(default_factory=list)
    _best: Optional[float] = None
    _stall: int = 0

    def clamp(self, magnitude: float) -> float:
        """Bounded actuation: never push harder than the per-tick limit."""
        lim = abs(self.max_actuation_per_tick)
        return max(-lim, min(lim, magnitude))

    def tick(self, error: float, acted: bool = True, note: str = "",
             uncertain: bool = False) -> Tick:
        i = len(self.history) + 1
        ts = int(time.time())

        if uncertain:
            # FAIL-SAFE first: a bad/uncertain signal -> hold, never actuate on a guess.
            d, r = HOLD, "uncertain signal — fail-safe HOLD; do not actuate"
        elif error <= self.tolerance:
            d, r = STOP, f"converged (error {error} <= tolerance {self.tolerance})"
        elif i >= self.max_ticks:
            d, r = STOP, f"hit max_ticks {self.max_ticks} — bounded stop, no runaway"
        else:
            improved = (self._best is None) or (error < self._best - 1e-9)
            if improved:
                self._best = error
                self._stall = 0
                d, r = CONTINUE, "error decreasing — converging"
            else:
                self._stall += 1
                if self._stall >= self.patience:
                    d, r = STOP, (f"no progress for {self._stall} ticks (error not "
                                  f"decreasing) — stop drifting, hand back to authority")
                else:
                    d, r = CONTINUE, (f"no improvement ({self._stall}/{self.patience}) "
                                      "— one more tick")

        t = Tick(i, error, acted, note, d, r, ts)
        self.history.append(t)
        return t

    def authorize(self, action: str) -> Dict[str, Any]:
        """The authority ceiling. The governor auto-approves only reversible/internal
        actions; anything outward or irreversible is refused and sent up to the
        gates / a human. The loop never self-authorizes these."""
        a = (action or "").lower()
        gated = any(k in a for k in GATED)
        return {
            "action": action,
            "auto_ok": not gated,
            "requires_authority": gated,
            "note": ("autonomous OK — reversible / internal" if not gated else
                     "STOP: outward/irreversible — needs authority (BROTHERS/GOD gate "
                     "or a human); the loop never self-authorizes this"),
        }

    def converged(self) -> bool:
        return bool(self.history and self.history[-1].decision == STOP
                    and self.history[-1].reason.startswith("converged"))

    def summary(self) -> Dict[str, Any]:
        last = self.history[-1] if self.history else None
        return {
            "reference": self.reference,
            "ticks": len(self.history),
            "best_error": self._best,
            "last_decision": (last.decision if last else None),
            "last_reason": (last.reason if last else None),
            "converged": self.converged(),
        }

    def log(self, path: str) -> None:
        """Observability: append this run's ticks to a JSONL audit trail, so an
        autonomous run is always reviewable after the fact."""
        with open(path, "a", encoding="utf-8") as fh:
            for t in self.history:
                fh.write(json.dumps({"reference": self.reference, **t.as_dict()},
                                    ensure_ascii=False) + "\n")


# Example — how the ingestion /loop is (now nameably) a control loop:
#
#   gov = Governor(reference="ingest the clean-source roadmap texts",
#                  tolerance=0, patience=2, max_ticks=20)
#   while True:
#       remaining = count_uningested()                 # the error
#       if extraction_was_bad:                          # bad signal
#           t = gov.tick(remaining, acted=False, uncertain=True)   # -> HOLD (defer)
#       else:
#           ingest_one(); t = gov.tick(count_uningested())          # act, re-measure
#       auth = gov.authorize("deploy_public")           # -> requires_authority
#       if t.decision == STOP: break                    # converged / drift / bound
