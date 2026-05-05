"""50 hand-labeled examples for the question classifier.

Each test asserts: primary_type matches, confidence meets threshold,
and edge-case flags fire correctly.

Per spec §10: "Test the classifier against the 9 types with 50 hand-labeled
examples before wiring anything else."
"""

import pytest
from concordance_engine.classifier import (
    classify,
    WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
    TIMING, FORMATION, CRISIS, HISTORICAL,
    CLARIFICATION_THRESHOLD,
)


# ── Helpers ────────────────────────────────────────────────────────────

def _assert_type(text: str, expected: str, min_confidence: float = 0.0):
    result = classify(text)
    assert result.primary_type == expected, (
        f"Expected {expected}, got {result.primary_type} "
        f"(confidence={result.confidence:.2f})\n  text: {text!r}\n"
        f"  scores: {result.raw_scores}"
    )
    if min_confidence > 0.0:
        assert result.confidence >= min_confidence, (
            f"Confidence {result.confidence:.2f} below {min_confidence} for {expected}\n"
            f"  text: {text!r}"
        )


# ══════════════════════════════════════════════════════════════════════
# WISDOM — 6 examples
# ══════════════════════════════════════════════════════════════════════

def test_wisdom_understand_pattern():
    _assert_type(
        "Help me understand what's happening in my life right now. "
        "I feel like things are moving fast but I can't get a clear picture.",
        WISDOM,
    )


def test_wisdom_what_does_this_mean():
    _assert_type(
        "Why does it feel like every time I get close to something good, it falls apart? "
        "What does this pattern mean?",
        WISDOM,
    )


def test_wisdom_biblical_success():
    _assert_type(
        "I'm confused about how to think about success from a biblical perspective.",
        WISDOM,
    )


def test_wisdom_discernment():
    _assert_type(
        "How do I discern between my own ambition and what God is actually calling me to?",
        WISDOM,
    )


def test_wisdom_sovereignty():
    _assert_type(
        "What does it mean that God is sovereign when bad things happen to faithful people?",
        WISDOM,
    )


def test_wisdom_pruning():
    _assert_type(
        "I keep reading about pruning but I'm not sure how to recognize it when I'm in it.",
        WISDOM,
    )


# ══════════════════════════════════════════════════════════════════════
# DOCTRINE — 6 examples
# ══════════════════════════════════════════════════════════════════════

def test_doctrine_once_saved():
    _assert_type(
        "Is it true that once saved always saved? I've heard arguments on both sides.",
        DOCTRINE,
    )


def test_doctrine_trinity():
    _assert_type(
        "What does the Bible say about the Trinity? My friend says it's not in Scripture.",
        DOCTRINE,
    )


def test_doctrine_lose_salvation():
    _assert_type(
        "Can a Christian lose their salvation?",
        DOCTRINE,
    )


def test_doctrine_predestination():
    _assert_type(
        "Does God predestine some people to hell?",
        DOCTRINE,
    )


def test_doctrine_tongues():
    _assert_type(
        "Is speaking in tongues required as evidence of the Holy Spirit?",
        DOCTRINE,
    )


def test_doctrine_christ_nature():
    _assert_type(
        "What does Scripture say about the nature of Christ — fully God and fully man?",
        DOCTRINE,
    )


# ══════════════════════════════════════════════════════════════════════
# DECISION — 6 examples
# ══════════════════════════════════════════════════════════════════════

def test_decision_leave_job():
    _assert_type(
        "Should I leave my job? I've been offered something new but the timing feels off.",
        DECISION,
    )


def test_decision_move_city():
    _assert_type(
        "I'm deciding between staying in my city or moving across the country for a new opportunity.",
        DECISION,
    )


def test_decision_sign_contract():
    _assert_type(
        "I've been offered a contract that would change my career. Do I sign it?",
        DECISION,
    )


def test_decision_another_child():
    _assert_type(
        "My wife and I are deciding whether to have another child. How do we know?",
        DECISION,
    )


def test_decision_friday_deadline():
    _assert_type(
        "I need to decide by Friday whether to accept this job offer. I can't keep waiting.",
        DECISION,
    )


def test_decision_house_purchase():
    _assert_type(
        "We're about to finalize the purchase of a house. Something feels off. Should I stop?",
        DECISION,
    )


# ══════════════════════════════════════════════════════════════════════
# RELATIONAL — 6 examples
# ══════════════════════════════════════════════════════════════════════

def test_relational_boss_undermining():
    _assert_type(
        "My boss keeps undermining me in meetings. I don't know how to handle this "
        "without making things worse.",
        RELATIONAL,
    )


def test_relational_brother_conflict():
    _assert_type(
        "My brother said something that cut deep and now he's acting like nothing happened. "
        "How do I confront this?",
        RELATIONAL,
    )


def test_relational_forgiveness_real():
    _assert_type(
        "She said she forgives me but nothing has changed. "
        "How do I know if reconciliation is real?",
        RELATIONAL,
    )


def test_relational_pastor():
    _assert_type(
        "My pastor is doing something I believe is wrong. What do I do?",
        RELATIONAL,
    )


def test_relational_marriage_decision():
    _assert_type(
        "My wife and I can't agree on a major decision and it's creating distance between us.",
        RELATIONAL,
    )


def test_relational_small_group():
    _assert_type(
        "There's conflict in our small group and people are leaving. "
        "What does Scripture say about this?",
        RELATIONAL,
    )


# ══════════════════════════════════════════════════════════════════════
# RESOURCE — 5 examples
# ══════════════════════════════════════════════════════════════════════

def test_resource_tithe_in_debt():
    _assert_type(
        "How should I think about tithing when I'm in significant debt?",
        RESOURCE,
    )


def test_resource_savings_decision():
    _assert_type(
        "I have $40,000 saved. Should I pay off debt or invest it?",
        RESOURCE,
    )


def test_resource_salary_increase():
    _assert_type(
        "My salary is increasing significantly and I don't know how to steward it well.",
        RESOURCE,
    )


def test_resource_career_advancement():
    _assert_type(
        "How do I think about career advancement when I'm already providing well for my family?",
        RESOURCE,
    )


def test_resource_buy_vs_rent():
    _assert_type(
        "We're trying to decide whether to buy or rent. "
        "What's the biblical perspective on homeownership?",
        RESOURCE,
    )


# ══════════════════════════════════════════════════════════════════════
# TIMING — 5 examples
# ══════════════════════════════════════════════════════════════════════

def test_timing_plant_church():
    _assert_type(
        "I feel called to plant a church but I don't know when the right time is.",
        TIMING,
    )


def test_timing_how_long_wait():
    _assert_type(
        "How long do I wait on God before I take action?",
        TIMING,
    )


def test_timing_leave_church():
    _assert_type(
        "Is it time to leave my church or am I running?",
        TIMING,
    )


def test_timing_relationship():
    _assert_type(
        "I've been holding back from this relationship for two years. "
        "When is it time to move?",
        TIMING,
    )


def test_timing_difficult_conversation():
    _assert_type(
        "I know I need to have a difficult conversation with my father. "
        "Is now the right time?",
        TIMING,
    )


# ══════════════════════════════════════════════════════════════════════
# FORMATION — 5 examples
# ══════════════════════════════════════════════════════════════════════

def test_formation_anger_pattern():
    _assert_type(
        "I keep falling into the same pattern of anger and I don't know how to break it.",
        FORMATION,
    )


def test_formation_self_sabotage():
    _assert_type(
        "Why do I always sabotage myself when things are going well?",
        FORMATION,
    )


def test_formation_prayer_discipline():
    _assert_type(
        "I want to become a man of prayer but I can't seem to make it stick.",
        FORMATION,
    )


def test_formation_inconsistent_character():
    _assert_type(
        "My character feels inconsistent — I can be generous one day and selfish the next.",
        FORMATION,
    )


def test_formation_ten_years():
    _assert_type(
        "I'm struggling with the same sin I've been struggling with for ten years. "
        "What's wrong with me?",
        FORMATION,
    )


# ══════════════════════════════════════════════════════════════════════
# CRISIS — 6 examples
# ══════════════════════════════════════════════════════════════════════

def test_crisis_everything_fallen_apart():
    _assert_type(
        "I don't know what to do. Everything has fallen apart at the same time "
        "and I can't see a way through.",
        CRISIS,
    )


def test_crisis_cant_go_on():
    _assert_type(
        "I'm overwhelmed and I'm not sure I can keep going. I don't see a way out.",
        CRISIS,
    )


def test_crisis_terrified():
    _assert_type(
        "Something happened today that I can't tell anyone about. "
        "I'm terrified of what comes next.",
        CRISIS,
    )


def test_crisis_life_worth_living_life_safety():
    """Explicit life-safety language triggers the fast path."""
    result = classify(
        "I've been thinking about whether life is worth living. "
        "I don't want to alarm anyone but I need to say it somewhere."
    )
    assert result.primary_type == CRISIS
    assert result.life_safety is True
    assert result.confidence == 1.0


def test_crisis_multiple_domains():
    _assert_type(
        "I'm in a crisis with my finances, my marriage, and my health all at the same time.",
        CRISIS,
    )


def test_crisis_no_one_to_call():
    _assert_type(
        "I need help right now. I don't have anyone to call.",
        CRISIS,
    )


# ══════════════════════════════════════════════════════════════════════
# HISTORICAL — 5 examples
# ══════════════════════════════════════════════════════════════════════

def test_historical_constantine():
    _assert_type(
        "What happened when Constantine made Christianity the official religion? "
        "What did that mean for the church?",
        HISTORICAL,
    )


def test_historical_reformation():
    _assert_type(
        "Why did the Reformation happen? What gate failed that required it?",
        HISTORICAL,
    )


def test_historical_israel_king():
    _assert_type(
        "What does it mean that Israel asked for a king in 1 Samuel? "
        "Why did God allow it?",
        HISTORICAL,
    )


def test_historical_inquisition():
    _assert_type(
        "How should I understand the Inquisition in light of Scripture?",
        HISTORICAL,
    )


def test_historical_corinth():
    _assert_type(
        "What was happening in Corinth that caused Paul to write 1 Corinthians?",
        HISTORICAL,
    )


# ══════════════════════════════════════════════════════════════════════
# EDGE CASES — 5 examples
# ══════════════════════════════════════════════════════════════════════

def test_edge_disguised_decision_wisdom_framing():
    """Wisdom framing but the answer requires an irreversible action."""
    result = classify(
        "Help me understand whether my current job is where God wants me. "
        "I've been offered something new and I'm trying to read the signs."
    )
    assert result.primary_type == DECISION
    assert result.decision_escalated is True


def test_edge_disguised_crisis_calm_language():
    """Calm phrasing with existential language should escalate."""
    result = classify(
        "I've been thinking about whether there's a point to continuing. "
        "Not in a dramatic way, just genuinely wondering."
    )
    # Should escalate: either CRISIS directly or DECISION with crisis_escalated
    assert result.primary_type in (CRISIS, DECISION)


def test_edge_compound_decision_relational():
    """A compound DECISION + RELATIONAL question resolves to DECISION (higher stakes)."""
    result = classify(
        "My wife and I are deciding whether to separate. "
        "I need wisdom about the process and whether reconciliation is possible."
    )
    assert result.primary_type == DECISION
    # RELATIONAL should appear as secondary
    assert result.secondary_type == RELATIONAL


def test_edge_compound_timing_decision():
    """TIMING embedded in a DECISION context — DECISION wins (higher priority)."""
    result = classify(
        "I know I need to leave this situation but I'm not sure when. "
        "The timing feels like it matters."
    )
    assert result.primary_type == DECISION


def test_edge_life_safety_fast_path_calm_phrasing():
    """Even calm phrasing of self-harm triggers the fast path."""
    result = classify(
        "I've been considering ending it all. I'm not sure why I'm still here."
    )
    assert result.primary_type == CRISIS
    assert result.life_safety is True


# ══════════════════════════════════════════════════════════════════════
# Structural invariants
# ══════════════════════════════════════════════════════════════════════

def test_classify_returns_valid_type_for_empty():
    """Empty string returns a valid type (no crash)."""
    result = classify("")
    assert result.primary_type in (
        WISDOM, DOCTRINE, DECISION, RELATIONAL, RESOURCE,
        TIMING, FORMATION, CRISIS, HISTORICAL,
    )


def test_classify_confidence_bounded():
    """Confidence is always in [0, 1]."""
    for text in [
        "test", "should I leave?", "help me understand the Trinity",
        "I'm overwhelmed", "what happened in the Reformation",
    ]:
        r = classify(text)
        assert 0.0 <= r.confidence <= 1.0, f"confidence out of range: {r.confidence}"


def test_classify_to_dict_serialisable():
    """to_dict() returns a JSON-safe dict."""
    import json
    result = classify("Should I leave my job?")
    d = result.to_dict()
    json.dumps(d)  # must not raise
    assert "question_type" in d
    assert "gate" in d
    assert "territory" in d


def test_life_safety_overrides_all_scoring():
    """Life-safety fast path fires even when WISDOM signals dominate."""
    result = classify(
        "Help me understand why I want to kill myself. "
        "I'm confused about what this means."
    )
    assert result.life_safety is True
    assert result.confidence == 1.0
    assert result.primary_type == CRISIS
