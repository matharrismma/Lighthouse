from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto

class Tier(Enum):
    """Identity/authority tier."""
    MILK = auto()
    MEAT = auto()

class Block(Enum):
    """Single blocking gate when upgrade cannot occur."""
    NONE = auto()
    LAW = auto()
    WAIT = auto()
    WITNESS = auto()
    MUTUAL = auto()
    PROOF = auto()
    ALIGN = auto()

class Result(Enum):
    PASS_ = auto()
    WAIT = auto()
    FAIL = auto()

@dataclass(frozen=True)
class Rules:
    """Default automatic rules (tunable per context/scale)."""
    witness_min: int = 1
    align_min: float = 0.75
    chaff_max: float = 0.35

    # refinement
    burn_rate: float = 0.25
    burn_gain: float = 0.05
    firstfruits_ratio: float = 0.10

    # harvest dynamics
    harvest_gain: float = 1.10
    w_align: float = 0.50
    w_clean: float = 0.25

    # harvest ceiling (default: unbounded, preserves prior behavior).
    # Set a finite value to cap fruit growth; useful when Calibre is run
    # as a forecast model rather than as an alignment metaphor.
    fruit_ceiling: float = float("inf")

    # signals->metrics mapping
    w_rumination: float = 0.30
    w_grudge: float = 0.40
    w_replay: float = 0.25
    w_shame_lock: float = 0.35

    w_peace: float = 0.25
    w_obedience: float = 0.35
    w_clarity: float = 0.20

    contradiction_cap: float = 0.49

    # streak smoothing for transitions (optional)
    align_streak_required: int = 3
    proof_streak_required: int = 1

@dataclass(frozen=True)
class Contract:
    """Cycle inputs (mutual + gates)."""
    law_ok: bool
    wait_open: bool
    witness: int
    mutual: bool
    proof: bool

@dataclass
class State:
    """Ledgerless state (current metrics + consecrated reseed store)."""
    tier: Tier = Tier.MILK
    align: float = 0.0      # 0..1 (coherence)
    chaff: float = 0.0      # 0..1 (noise/drag)
    fruit: float = 0.0      # >=0
    firstfruits: float = 0.0

    # transition smoothers
    access: int = 0         # 0..3 (progress without identity flip)
    align_streak: int = 0
    proof_streak: int = 0

@dataclass(frozen=True)
class Signals:
    """Standard detector envelope (ledgerless)."""
    # negative markers (0..1)
    rumination: float = 0.0
    replay: float = 0.0
    grudge: float = 0.0
    shame_lock: bool = False
    contradiction: bool = False

    # positive markers (0..1)
    peace: float = 0.0
    obedience: float = 0.0
    clarity: float = 0.0

    # fruit markers
    fruit_delta: float = 0.0
    stewardship: float = 0.0
