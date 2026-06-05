"""Calibre — the floor made calculable.

The moral/structural layer of the floor, as deterministic formulas. Ported
into the live engine from lw/09_calibre (M.R. Harris, public domain) so the
tools can finally reach it. Until now Calibre lived in the kernel package and
was wired into nothing — every tool stood on a shard of the floor. This is
the first orphan brought home.

Triadic flow (a human, a system, a teaching — any vessel):
    Spirit = Source   →   Mind = Channel   →   Body = Sink

All inputs normalized to [0,1]. All outputs in [0,1]. No I/O, no deps —
pure functions, so any tool can call them and the result is the same today
and tomorrow (a fixed reference; the circle can tighten against it).
"""
from __future__ import annotations
from dataclasses import dataclass


def clamp01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


@dataclass(frozen=True)
class FlowTriad:
    """Spirit=Source, Mind=Channel, Body=Sink. Each in [0,1]."""
    spirit_source: float
    mind_channel: float
    body_sink: float


def flow_health(t: FlowTriad) -> float:
    """Health = correct direction + capacity balance.

    High when all three are present (presence) and balanced (low spread).
    A vessel is healthy when spirit, mind, and body are all flowing and
    none is starved or hoarding.
    """
    s, m, b = clamp01(t.spirit_source), clamp01(t.mind_channel), clamp01(t.body_sink)
    spread = max(s, m, b) - min(s, m, b)
    presence = (s + m + b) / 3.0
    return clamp01(0.60 * (1.0 - spread) + 0.40 * presence)


def beauty_score(t: FlowTriad) -> float:
    """Beauty = the perceptible signature of internal health (health x economy).

    Health made visible with nothing wasted. Excess composition (one part
    bloated above the mean) costs economy. Depth demonstrated through simplicity.
    """
    s, m, b = clamp01(t.spirit_source), clamp01(t.mind_channel), clamp01(t.body_sink)
    health = flow_health(t)
    comp = max(s, m, b) - (s + m + b) / 3.0
    economy = clamp01(1.0 - comp)
    return clamp01(health * economy)


def shadow(law_strength: float, capacity: float, load: float) -> float:
    """Shadow of Law = boundary distortion when load exceeds capacity.

        shadow = law_strength * max(0, load - capacity)

    This is the SAME term that the Nested Control Systems framework names as
    the mechanism of chronic disease: a control layer fails when load outruns
    its capacity. The shadow of the Law and the shadow on a failing organ are
    one equation, read at two scales. Diagnostic of overload — not "evil".
    """
    L, C, P = clamp01(law_strength), clamp01(capacity), clamp01(load)
    overload = max(0.0, P - C)
    return clamp01(L * overload)


def vice_index(source_purity: float, channel_integrity: float, desire_speed: float) -> float:
    """Vice = flow that bypasses the proper channel to reach the sink faster.

        bypass        = desire * (1 - channel_integrity)
        false_source  = (1 - source_purity) * desire
        vice          = 0.60*bypass + 0.40*false_source

    Speed over form. Acting on desire without knowledge (bypass), or from a
    corrupt source (false_source). The structural shape of sin.
    """
    S, K, D = clamp01(source_purity), clamp01(channel_integrity), clamp01(desire_speed)
    bypass = D * (1.0 - K)
    false_source = (1.0 - S) * D
    return clamp01(0.60 * bypass + 0.40 * false_source)


def score_triad(spirit: float, mind: float, body: float) -> dict:
    """Convenience: the full Calibre reading for a triad, as a dict."""
    t = FlowTriad(spirit, mind, body)
    return {
        "triad": {"spirit_source": clamp01(spirit), "mind_channel": clamp01(mind), "body_sink": clamp01(body)},
        "health": round(flow_health(t), 4),
        "beauty": round(beauty_score(t), 4),
    }
