from __future__ import annotations
from dataclasses import dataclass

def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x

@dataclass(frozen=True)
class FlowTriad:
    """
    Triadic flow model (human instance):
      Spirit = Source
      Mind   = Channel
      Body   = Sink
    Values are normalized 0..1 for scoring.
    """
    spirit_source: float
    mind_channel: float
    body_sink: float

def flow_health(t: FlowTriad) -> float:
    """Health = correct direction + capacity balance (heuristic)."""
    s = clamp01(t.spirit_source)
    m = clamp01(t.mind_channel)
    b = clamp01(t.body_sink)
    mx = max(s, m, b)
    mn = min(s, m, b)
    spread = mx - mn
    presence = (s + m + b) / 3.0
    return clamp01(0.60 * (1.0 - spread) + 0.40 * presence)

def beauty_score(t: FlowTriad) -> float:
    """Beauty = perceptible signature of internal health (health * economy)."""
    s = clamp01(t.spirit_source)
    m = clamp01(t.mind_channel)
    b = clamp01(t.body_sink)
    health = flow_health(t)
    comp = (max(s, m, b) - (s + m + b) / 3.0)
    economy = clamp01(1.0 - comp)
    return clamp01(health * economy)

def shadow(law_strength: float, capacity: float, load: float) -> float:
    """
    Shadow of Law: boundary distortion when load exceeds capacity.
    Inputs normalized to 0..1.
    shadow = clamp(law_strength * max(0, load - capacity))
    """
    L = clamp01(law_strength)
    C = clamp01(capacity)
    P = clamp01(load)
    overload = max(0.0, P - C)
    return clamp01(L * overload)

def vice_index(source_purity: float, channel_integrity: float, desire_speed: float) -> float:
    """
    Vice = flow that bypasses proper channel to reach sink faster (speed over form).
    vice = clamp(0.60*(D*(1-K)) + 0.40*((1-S)*D))
    """
    S = clamp01(source_purity)
    K = clamp01(channel_integrity)
    D = clamp01(desire_speed)
    bypass = D * (1.0 - K)
    false_source = (1.0 - S) * D
    return clamp01(0.60 * bypass + 0.40 * false_source)
