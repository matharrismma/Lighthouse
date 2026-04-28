"""the_way_kernel_min.py

A minimal, universal kernel that enforces the Biblical Alignment Protocol:

INPUT → ALIGN → ACT → WITNESS → WAIT → CONFIRM/PRUNE

This file is deliberately small and readable for technical + non-technical review.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
import time
import json
import hashlib

# ---------- Core enums ----------

class Status(str, Enum):
    QUARANTINE = "QUARANTINE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"

class Action(str, Enum):
    OPEN = "OPEN"
    BUILD = "BUILD"
    RESERVE = "RESERVE"
    PRUNE = "PRUNE"
    HOLD = "HOLD"

# ---------- Core data ----------

@dataclass
class Witness:
    name: str
    affirms: bool
    note: str = ""

@dataclass
class Entry:
    # required humility key
    confession: str

    # Gate 1 (RED) and Gate 2 (FLOOR) are hard gates
    aligns_with_red: bool
    violates_floor: bool

    # Scripture anchors in extreme shorthand (edition-specific mapping happens elsewhere)
    refs: List[str] = field(default_factory=list)  # e.g., ["Jn15:2", "Pr4:23"]

    # minimal action
    action: Action = Action.HOLD

    # Gate 3 (BROTHERS) and Gate 4 (GOD) are soft gates
    witnesses: List[Witness] = field(default_factory=list)
    submitted_at: float = field(default_factory=time.time)
    wait_seconds: int = 3600  # default: 1 hour
    status: Status = Status.QUARANTINE

    # outcomes (optional until after execution)
    outcome: Optional[str] = None  # "fruit"|"mixed"|"failed"

    def waited(self, now: Optional[float] = None) -> bool:
        now = time.time() if now is None else now
        return (now - self.submitted_at) >= self.wait_seconds

    def witness_count(self) -> int:
        return sum(1 for w in self.witnesses if w.affirms)

    def digest(self) -> str:
        # digest excludes status so the history is auditable as it evolves
        payload = {
            "confession": self.confession,
            "aligns_with_red": self.aligns_with_red,
            "violates_floor": self.violates_floor,
            "refs": self.refs,
            "action": self.action.value,
            "witnesses": [{"name": w.name, "affirms": w.affirms, "note": w.note} for w in self.witnesses],
            "submitted_at": self.submitted_at,
            "wait_seconds": self.wait_seconds,
            "outcome": self.outcome,
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(s.encode("utf-8")).hexdigest()

    def decide(self, required_witnesses: int = 2) -> Status:
        # Gate 1: RED
        if not self.aligns_with_red:
            self.status = Status.REJECTED
            return self.status

        # Gate 2: FLOOR
        if self.violates_floor:
            self.status = Status.REJECTED
            return self.status

        # Gate 3: BROTHERS (witness threshold)
        if self.witness_count() < required_witnesses:
            self.status = Status.QUARANTINE
            return self.status

        # Gate 4: GOD (waiting)
        if not self.waited():
            self.status = Status.QUARANTINE
            return self.status

        self.status = Status.CONFIRMED
        return self.status

# ---------- Tiny demo runner ----------

def demo():
    e = Entry(
        confession="I may be wrong. I acted in faith according to Jn15:2 and Pr4:23.",
        aligns_with_red=True,
        violates_floor=False,
        refs=["Jn15:2", "Pr4:23"],
        action=Action.PRUNE,
        wait_seconds=2,  # short for demo
    )
    print("SUB", e.digest(), e.status)

    e.witnesses.append(Witness("Brother_1", True, "Aligned; protects the floor."))
    e.witnesses.append(Witness("Brother_2", True, "Aligned; prudent waiting."))
    print("WIT", e.digest(), e.decide())

    time.sleep(2.1)
    print("DEC", e.digest(), e.decide())

if __name__ == "__main__":
    demo()
