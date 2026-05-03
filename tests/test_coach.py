"""Tests for the Coach OS port — protocol + Steward.

The Coach module is a core. These tests verify the deterministic
gate sequence, token binding, dose / escalation / mode / egress
locks, and the append-only audit packets.
"""
from __future__ import annotations

import time

import pytest

from concordance_engine.coach import (
    ActionToken,
    Corridor,
    Decision,
    ReasonCode,
    Steward,
    StewardPolicy,
    WedgeRequest,
    new_id,
    now_ms,
    stable_hash,
)
from concordance_engine.coach.protocol import PacketStore


# ── helpers ──────────────────────────────────────────────────────────


def _build_steward(policy: StewardPolicy = None) -> tuple[Steward, PacketStore]:
    store = PacketStore()
    steward = Steward(policy or StewardPolicy(), store)
    return steward, store


def _build_request(
    session_id: str,
    corridor_id: str,
    *,
    wedge_id: str = "PROMPT",
    wedge_level: int = 2,
    risk_flags: list[str] = None,
) -> WedgeRequest:
    return WedgeRequest(
        request_id=new_id(),
        created_at_ms=now_ms(),
        session_id=session_id,
        wedge_id=wedge_id,
        wedge_level=wedge_level,
        requested_effect="test",
        context_digest=stable_hash({"k": "v"}),
        corridor_id=corridor_id,
        risk_flags=list(risk_flags or []),
    )


# ── PacketStore basics ───────────────────────────────────────────────


def test_packet_store_append_and_query():
    store = PacketStore()
    pid = store.append("test_packet", {"session_id": "s1", "x": 1})
    assert pid is not None
    assert len(store.all()) == 1
    assert store.all()[0].packet_type == "test_packet"
    assert store.all()[0].payload["session_id"] == "s1"
    assert store.by_type("test_packet") == store.all()
    assert store.by_session("s1") == store.all()
    assert store.by_session("s2") == []


def test_packet_store_file_backed(tmp_path):
    store = PacketStore(base_dir=tmp_path)
    store.append("test", {"x": 1})
    store.append("test", {"y": 2})
    log_path = tmp_path / "coach_log.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 2


# ── stable_hash determinism ──────────────────────────────────────────


def test_stable_hash_deterministic():
    h1 = stable_hash({"a": 1, "b": 2, "c": 3})
    h2 = stable_hash({"c": 3, "b": 2, "a": 1})
    assert h1 == h2


def test_stable_hash_distinguishes_payloads():
    assert stable_hash({"a": 1}) != stable_hash({"a": 2})


# ── WedgeRequest.hash ────────────────────────────────────────────────


def test_request_hash_binds_to_fields():
    r1 = WedgeRequest(
        request_id="r1", created_at_ms=0, session_id="s",
        wedge_id="PROMPT", wedge_level=1, requested_effect="x",
        context_digest="d", corridor_id="c", risk_flags=[],
    )
    r2 = WedgeRequest(
        request_id="r1", created_at_ms=0, session_id="s",
        wedge_id="PROMPT", wedge_level=2,  # changed level
        requested_effect="x",
        context_digest="d", corridor_id="c", risk_flags=[],
    )
    assert r1.hash() != r2.hash()


# ── Steward: corridor management ─────────────────────────────────────


def test_steward_creates_default_corridor():
    steward, store = _build_steward()
    c = steward.get_corridor("session_a")
    assert isinstance(c, Corridor)
    assert "PROMPT" in c.allowed_wedges
    # The corridor was audited via a directive packet.
    directives = store.by_type("coach_steward_directive_v1")
    assert len(directives) == 1


def test_steward_set_corridor_overrides():
    steward, _ = _build_steward()
    custom = Corridor(
        corridor_id=new_id(),
        target={"name": "custom"},
        allowed_wedges=["WAIT"],
        constraints={
            "max_interventions_per_min": 1,
            "min_ms_between_interventions": 0,
            "max_escalations_per_min": 1,
            "mode_locked": False,
            "egress_locked": False,
        },
        expires_at_ms=now_ms() + 60_000,
    )
    steward.set_corridor("session_b", custom)
    fetched = steward.get_corridor("session_b")
    assert fetched.corridor_id == custom.corridor_id
    assert fetched.allowed_wedges == ["WAIT"]


# ── Steward: admit happy path ────────────────────────────────────────


def test_admit_issues_valid_token():
    steward, store = _build_steward()
    corridor = steward.get_corridor("s1")
    request = _build_request("s1", corridor.corridor_id)
    decision, token, reason = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={"in_flow": False},
    )
    assert decision == Decision.ADMIT
    assert reason == ReasonCode.ALLOW_OK
    assert token is not None
    assert token.request_hash == request.hash()
    # An admission packet was recorded.
    assert len(store.by_type("coach_wedge_admission_v1")) == 1


def test_admit_token_validates_and_consumes():
    steward, store = _build_steward()
    corridor = steward.get_corridor("s1")
    request = _build_request("s1", corridor.corridor_id)
    _, token, _ = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={},
    )
    ok, reason = steward.validate_and_consume(token=token, request=request)
    assert ok is True
    assert reason == ReasonCode.ALLOW_OK
    # A consumed packet was logged.
    assert len(store.by_type("coach_token_consumed_v1")) == 1


def test_token_single_use():
    steward, _ = _build_steward()
    corridor = steward.get_corridor("s1")
    request = _build_request("s1", corridor.corridor_id)
    _, token, _ = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={},
    )
    # First consume: succeeds.
    ok, _ = steward.validate_and_consume(token=token, request=request)
    assert ok
    # Second consume: denied.
    ok2, reason2 = steward.validate_and_consume(token=token, request=request)
    assert not ok2
    assert reason2 == ReasonCode.DENY_TOKEN_ALREADY_USED


def test_token_mismatch_denied():
    steward, _ = _build_steward()
    corridor = steward.get_corridor("s1")
    r1 = _build_request("s1", corridor.corridor_id, wedge_level=2)
    _, token, _ = steward.admit_or_deny(
        r1, active_sessions_count=1, child_state={},
    )
    # Use the token against a DIFFERENT request — should be rejected.
    r2 = _build_request("s1", corridor.corridor_id, wedge_level=3)
    ok, reason = steward.validate_and_consume(token=token, request=r2)
    assert not ok
    assert reason == ReasonCode.DENY_TOKEN_MISMATCH


# ── Steward: deny paths (each gate in the deterministic sequence) ────


def test_corridor_mismatch_denies():
    steward, _ = _build_steward()
    steward.get_corridor("s1")  # establish corridor
    bogus_request = _build_request("s1", corridor_id="not-a-real-corridor")
    decision, token, reason = steward.admit_or_deny(
        bogus_request, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert token is None
    assert reason == ReasonCode.DENY_CORRIDOR


def test_wedge_not_allowed_denies():
    steward, _ = _build_steward()
    corridor = steward.get_corridor("s1")
    bad = _build_request("s1", corridor.corridor_id, wedge_id="UNAUTHORIZED")
    decision, _, reason = steward.admit_or_deny(
        bad, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_CORRIDOR


def test_flow_protect_denies_high_level_when_in_flow():
    steward, _ = _build_steward(StewardPolicy(flow_protect_max_level=2))
    corridor = steward.get_corridor("s1")
    request = _build_request("s1", corridor.corridor_id, wedge_level=4)
    decision, _, reason = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={"in_flow": True},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_FLOW_PROTECTED


def test_dose_limit_denies_after_max_per_min():
    steward, _ = _build_steward()
    custom = Corridor(
        corridor_id=new_id(),
        target={},
        allowed_wedges=["PROMPT"],
        constraints={
            "max_interventions_per_min": 1,
            "min_ms_between_interventions": 0,
            "max_escalations_per_min": 99,
            "mode_locked": False,
            "egress_locked": False,
        },
        expires_at_ms=now_ms() + 60_000,
    )
    steward.set_corridor("s1", custom)
    r1 = _build_request("s1", custom.corridor_id)
    _, t1, _ = steward.admit_or_deny(r1, active_sessions_count=1, child_state={})
    steward.validate_and_consume(token=t1, request=r1)
    # Second within the window: denied.
    r2 = _build_request("s1", custom.corridor_id)
    decision, _, reason = steward.admit_or_deny(
        r2, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_DOSE_LIMIT


def test_mode_lock_denies_mode_change_request():
    steward, _ = _build_steward()
    corridor = steward.get_corridor("s1")  # mode_locked default True
    request = _build_request("s1", corridor.corridor_id,
                             risk_flags=["mode_change"])
    decision, _, reason = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_MODE_LOCK


def test_egress_lock_denies_egress_request():
    steward, _ = _build_steward()
    corridor = steward.get_corridor("s1")  # egress_locked default True
    request = _build_request("s1", corridor.corridor_id,
                             risk_flags=["egress"])
    decision, _, reason = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_EGRESS_LOCK


def test_corridor_expiry_denies():
    steward, _ = _build_steward()
    expired = Corridor(
        corridor_id=new_id(),
        target={},
        allowed_wedges=["PROMPT"],
        constraints={"mode_locked": False, "egress_locked": False},
        expires_at_ms=now_ms() - 1,  # already expired
    )
    steward.set_corridor("s1", expired)
    request = _build_request("s1", expired.corridor_id)
    decision, _, reason = steward.admit_or_deny(
        request, active_sessions_count=1, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_CORRIDOR


def test_wip_limit_denies():
    steward, _ = _build_steward(StewardPolicy(wip_limit_active_sessions=10))
    corridor = steward.get_corridor("s1")
    request = _build_request("s1", corridor.corridor_id)
    decision, _, reason = steward.admit_or_deny(
        request, active_sessions_count=999, child_state={},
    )
    assert decision == Decision.DENY
    assert reason == ReasonCode.DENY_WIP_LIMIT


# ── Steward: every decision is audited ───────────────────────────────


def test_every_admission_decision_is_audited():
    steward, store = _build_steward()
    corridor = steward.get_corridor("s1")
    # Mix of admits and denies.
    r_ok = _build_request("s1", corridor.corridor_id)
    r_bad = _build_request("s1", corridor_id="not-real")
    r_egress = _build_request("s1", corridor.corridor_id,
                              risk_flags=["egress"])
    steward.admit_or_deny(r_ok, active_sessions_count=1, child_state={})
    steward.admit_or_deny(r_bad, active_sessions_count=1, child_state={})
    steward.admit_or_deny(r_egress, active_sessions_count=1, child_state={})
    admissions = store.by_type("coach_wedge_admission_v1")
    assert len(admissions) == 3
    # The packet store is append-only — none of these are mutations.
    for p in admissions:
        assert p.packet_type == "coach_wedge_admission_v1"
        assert "decision" in p.payload
        assert "reason_code" in p.payload
