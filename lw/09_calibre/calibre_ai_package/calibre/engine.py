from __future__ import annotations
from typing import Tuple
from .model import Rules, Contract, State, Signals, Result, Block, Tier
from .formulas import clamp01

def setup(c: Contract, r: Rules) -> Tuple[Result, Block]:
    if not c.law_ok:
        return Result.FAIL, Block.LAW
    if not c.wait_open:
        return Result.WAIT, Block.WAIT
    if c.witness < r.witness_min:
        return Result.WAIT, Block.WITNESS
    return Result.PASS_, Block.NONE

def position(c: Contract) -> Tuple[Result, Block]:
    if not c.mutual:
        return Result.FAIL, Block.MUTUAL
    if not c.proof:
        return Result.WAIT, Block.PROOF
    return Result.PASS_, Block.NONE

def convert(s: State, r: Rules) -> Tuple[Result, Block]:
    if s.align < r.align_min or s.chaff > r.chaff_max:
        return Result.WAIT, Block.ALIGN
    return Result.PASS_, Block.NONE

def upgrade(c: Contract, s: State, r: Rules) -> Tuple[Result, Block]:
    """Smoothed Milk->Meat upgrade using access + streaks."""
    res, blk = setup(c, r)
    if res != Result.PASS_:
        return res, blk

    res, blk = position(c)
    if res != Result.PASS_:
        return res, blk

    # streak tracking
    s.proof_streak = (s.proof_streak + 1) if c.proof else 0
    if s.align >= r.align_min and s.chaff <= r.chaff_max:
        s.align_streak += 1
    else:
        s.align_streak = 0

    # quiet progress: access climbs with consistent alignment (bounded)
    if s.align_streak >= 1 and s.access < 3:
        s.access += 1

    res, blk = convert(s, r)
    if res != Result.PASS_:
        return res, blk

    if (
        s.access >= 3
        and s.align_streak >= r.align_streak_required
        and s.proof_streak >= r.proof_streak_required
    ):
        s.tier = Tier.MEAT
        return Result.PASS_, Block.NONE

    return Result.WAIT, Block.ALIGN

def calibrate(s: State, sig: Signals, r: Rules) -> None:
    """Signals -> (align, chaff, fruit) mapping (ledgerless)."""
    neg = (
        r.w_rumination * clamp01(sig.rumination)
        + r.w_grudge * clamp01(sig.grudge)
        + r.w_replay * clamp01(sig.replay)
        + (r.w_shame_lock if sig.shame_lock else 0.0)
    )
    chaff = clamp01(0.70 * s.chaff + 0.30 * clamp01(neg))

    pos = (
        r.w_peace * clamp01(sig.peace)
        + r.w_obedience * clamp01(sig.obedience)
        + r.w_clarity * clamp01(sig.clarity)
    )
    align_raw = clamp01(0.70 * s.align + 0.30 * clamp01(pos) + (0.15 * (1.0 - chaff)))

    if sig.contradiction:
        align = min(align_raw, r.contradiction_cap)
    else:
        align = clamp01(align_raw - 0.20 * chaff)

    fruit = max(0.0, s.fruit + max(0.0, sig.fruit_delta))
    fruit = fruit * (1.0 + 0.10 * clamp01(sig.stewardship))

    s.align = align
    s.chaff = chaff
    s.fruit = fruit

def burn(s: State, r: Rules) -> None:
    s.chaff = clamp01(s.chaff * (1.0 - r.burn_rate))
    s.align = clamp01(s.align + r.burn_gain)

def firstfruits(s: State, r: Rules) -> None:
    s.firstfruits += max(0.0, s.fruit * r.firstfruits_ratio)

def harvest(s: State, r: Rules) -> None:
    clean = 1.0 - s.chaff
    mult = 1.0 + (s.align * r.w_align) + (clean * r.w_clean)
    grown = max(0.0, s.fruit * r.harvest_gain * mult)
    # Cap if a finite ceiling is configured. Default ceiling is +inf,
    # which preserves the unbounded behavior of v0.1.
    s.fruit = min(grown, r.fruit_ceiling)

def step(c: Contract, s: State, r: Rules, sig: Signals) -> Tuple[State, Result, Block]:
    """One automatic cycle: Calibrate -> Burn -> Firstfruits -> Harvest -> Upgrade."""
    calibrate(s, sig, r)
    burn(s, r)
    firstfruits(s, r)
    harvest(s, r)
    res, blk = upgrade(c, s, r)
    return s, res, blk
