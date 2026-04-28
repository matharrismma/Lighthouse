"""keeper_gate.py — Minimal Four-Gate Alignment Engine (Shorthand)

Status: REJ (reject), Q (quarantine), CONF (confirmed)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List
import time

class St(str, Enum):
    REJ = "REJ"
    Q = "Q"
    CONF = "CONF"

@dataclass
class Wit:
    n: str
    y: bool
    note: str = ""

@dataclass
class Sub:
    id: str
    sc: str = "A"          # scope: A/M/C
    conf: str = ""         # confession
    red: List[str] = field(default_factory=list)    # shorthand refs (e.g., ["Jn14:6"])
    floor: List[str] = field(default_factory=list)  # shorthand refs (e.g., ["Ex20"])
    risk: str = ""         # floor-risk note
    wits: List[Wit] = field(default_factory=list)
    ts: int = field(default_factory=lambda: int(time.time()))

def scope_defaults(sc: str):
    return {"A": (2, 3600), "M": (3, 86400), "C": (7, 604800)}.get(sc, (3, 86400))

def decide(sub: Sub):
    wmin, wait_s = scope_defaults(sub.sc)

    if not sub.conf.strip():
        return {"st": St.Q, "why": ["CONF missing"]}

    if not sub.red:
        return {"st": St.REJ, "why": ["RED fail (no refs)"]}

    bad = any(k in (sub.risk or "").lower() for k in ["violate", "break", "sin", "deceive", "steal", "harm"])
    if not sub.floor or bad:
        return {"st": St.REJ, "why": ["FLOOR fail (risk)"]}

    if sum(1 for w in sub.wits if w.y) < wmin:
        return {"st": St.Q, "why": [f"BROTHERS wait (<{wmin})"]}

    if (int(time.time()) - sub.ts) < wait_s:
        return {"st": St.Q, "why": [f"GOD wait (<{wait_s}s)"]}

    return {"st": St.CONF, "why": ["All gates pass"]}
