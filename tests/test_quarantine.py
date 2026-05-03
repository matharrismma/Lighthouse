"""Tests for the Quarantine Airlock state machine.

Per canonical 03_ARCH/QUARANTINE_AIRLOCK.md:
  * Default rule: Ideas are quarantined by default.
  * Three zones: Holding / Decontamination / Core.
  * Three roles: Q / Scribe / Guide.
  * Admission format: structured packet with hypothesis, backlog, decision.
"""
from __future__ import annotations

import json

import pytest

from concordance_engine.quarantine import (
    Decision,
    QuarantineError,
    QuarantinePacket,
    QuarantineStore,
    Role,
    RoleAction,
    Zone,
    admit,
    capture,
    decontaminate,
)


# ── capture (Scribe → HOLDING) ───────────────────────────────────────


def test_capture_lands_in_holding():
    p = capture("a raw idea about quarantine flow")
    assert p.zone == Zone.HOLDING.value
    assert p.raw == "a raw idea about quarantine flow"
    assert p.id.startswith("q-")
    assert len(p.history) == 1
    assert p.history[0].role == Role.SCRIBE.value
    assert p.history[0].action == "captured"


def test_capture_normalizes_text():
    p = capture("hello world   with   spaces")
    assert p.normalized == "hello world with spaces"


def test_capture_records_tags():
    p = capture("idea", tags=["scripture", "draft"])
    assert p.tags == ["scripture", "draft"]


def test_capture_rejects_empty():
    with pytest.raises(QuarantineError):
        capture("")
    with pytest.raises(QuarantineError):
        capture("   ")


def test_capture_creates_unique_ids():
    p1 = capture("idea one")
    p2 = capture("idea two")
    assert p1.id != p2.id


# ── decontaminate (Q: HOLDING → DECONTAMINATION) ────────────────────


def test_decontaminate_moves_to_decontamination():
    p = capture("raw input")
    out = decontaminate(p, hypothesis="this idea claims X about Y")
    assert out.zone == Zone.DECONTAMINATION.value
    assert out.hypothesis == "this idea claims X about Y"
    assert out.history[-1].role == Role.Q.value
    assert out.history[-1].action == "moved_to_decontamination"


def test_decontaminate_records_backlog_items():
    p = capture("raw")
    decontaminate(p, hypothesis="h", backlog_items=["check ref", "compare against canon"])
    assert p.backlog_items == ["check ref", "compare against canon"]


def test_decontaminate_requires_hypothesis():
    p = capture("raw")
    with pytest.raises(QuarantineError, match="hypothesis"):
        decontaminate(p, hypothesis="")
    with pytest.raises(QuarantineError, match="hypothesis"):
        decontaminate(p, hypothesis="   ")


def test_decontaminate_rejects_non_holding_packet():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    with pytest.raises(QuarantineError, match="HOLDING"):
        decontaminate(p, hypothesis="h2")


# ── admit (Guide: ACCEPT/REJECT/DEFER) ───────────────────────────────


def test_admit_accept_moves_to_core():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    out = admit(p, decision=Decision.ACCEPT, rationale="aligns with canon")
    assert out.zone == Zone.CORE.value
    assert out.decision == Decision.ACCEPT.value
    assert out.history[-1].role == Role.GUIDE.value
    assert out.history[-1].action == "accepted"


def test_admit_reject_keeps_in_holding_with_reason():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    out = admit(p, decision=Decision.REJECT, rationale="contradicts canon §3")
    assert out.zone == Zone.HOLDING.value
    assert out.decision == Decision.REJECT.value
    assert out.rejection_reason == "contradicts canon §3"
    assert out.history[-1].action == "rejected"


def test_admit_defer_stays_in_decontamination():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    out = admit(p, decision=Decision.DEFER, rationale="needs another source")
    assert out.zone == Zone.DECONTAMINATION.value
    assert out.decision == Decision.DEFER.value
    assert out.history[-1].action == "deferred"


def test_admit_reject_requires_rationale():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    with pytest.raises(QuarantineError, match="rationale"):
        admit(p, decision=Decision.REJECT, rationale="")


def test_admit_rejects_holding_packet():
    """Guide cannot decide on a packet that hasn't been decontaminated."""
    p = capture("raw")
    with pytest.raises(QuarantineError, match="DECONTAMINATION"):
        admit(p, decision=Decision.ACCEPT)


def test_admit_rejects_already_accepted_packet():
    """A packet already in CORE shouldn't be re-admitted."""
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    admit(p, decision=Decision.ACCEPT)
    with pytest.raises(QuarantineError, match="DECONTAMINATION"):
        admit(p, decision=Decision.ACCEPT)


def test_admit_rejects_non_decision_enum():
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    with pytest.raises(QuarantineError, match="Decision"):
        admit(p, decision="accept")  # bare string, not enum


def test_admit_defer_then_accept_flows_through():
    """Defer → more work → accept is the canonical re-evaluation path."""
    p = capture("raw")
    decontaminate(p, hypothesis="h")
    admit(p, decision=Decision.DEFER, rationale="not yet")
    # Still in DECONTAMINATION — Guide can issue another decision.
    out = admit(p, decision=Decision.ACCEPT, rationale="now sufficient")
    assert out.zone == Zone.CORE.value
    assert out.decision == Decision.ACCEPT.value


# ── Persistence (QuarantineStore) ────────────────────────────────────


def test_store_save_and_load_roundtrip(tmp_path):
    store = QuarantineStore(base_dir=tmp_path)
    p = capture("raw input for roundtrip")
    decontaminate(p, hypothesis="h")
    store.save(p)
    loaded = store.load(p.id)
    assert loaded is not None
    assert loaded.id == p.id
    assert loaded.zone == Zone.DECONTAMINATION.value
    assert loaded.hypothesis == "h"
    assert len(loaded.history) == len(p.history)
    assert loaded.history[0].role == Role.SCRIBE.value


def test_store_load_missing_returns_none(tmp_path):
    store = QuarantineStore(base_dir=tmp_path)
    assert store.load("q-doesnotexist") is None


def test_store_list_all_filters_by_zone(tmp_path):
    store = QuarantineStore(base_dir=tmp_path)
    p_holding = capture("a")
    p_decon = capture("b")
    decontaminate(p_decon, hypothesis="h")
    p_core = capture("c")
    decontaminate(p_core, hypothesis="h")
    admit(p_core, decision=Decision.ACCEPT)
    for pkt in (p_holding, p_decon, p_core):
        store.save(pkt)

    all_pkts = store.list_all()
    assert len(all_pkts) == 3

    holding_only = store.list_all(zone=Zone.HOLDING)
    assert [pkt.id for pkt in holding_only] == [p_holding.id]

    core_only = store.list_all(zone=Zone.CORE)
    assert [pkt.id for pkt in core_only] == [p_core.id]


def test_store_list_all_empty_dir_returns_empty(tmp_path):
    store = QuarantineStore(base_dir=tmp_path / "no_such_dir")
    assert store.list_all() == []


def test_store_delete_removes_file(tmp_path):
    store = QuarantineStore(base_dir=tmp_path)
    p = capture("raw")
    store.save(p)
    assert store.delete(p.id) is True
    assert store.load(p.id) is None
    assert store.delete(p.id) is False


def test_store_save_writes_valid_json(tmp_path):
    store = QuarantineStore(base_dir=tmp_path)
    p = capture("raw input")
    decontaminate(p, hypothesis="h")
    target = store.save(p)
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["id"] == p.id
    assert data["zone"] == Zone.DECONTAMINATION.value
    assert isinstance(data["history"], list)
    assert data["history"][0]["role"] == Role.SCRIBE.value


def test_store_uses_env_override(tmp_path, monkeypatch):
    """CONCORDANCE_QUARANTINE_DIR overrides the default location."""
    target = tmp_path / "env_override"
    monkeypatch.setenv("CONCORDANCE_QUARANTINE_DIR", str(target))
    store = QuarantineStore()  # no explicit base_dir
    assert store.base_dir == target
    p = capture("raw")
    store.save(p)
    assert (target / f"{p.id}.json").exists()


# ── QuarantinePacket dict roundtrip ─────────────────────────────────


def test_packet_to_dict_and_back():
    p = capture("raw")
    decontaminate(p, hypothesis="h", backlog_items=["item1"])
    admit(p, decision=Decision.ACCEPT, rationale="ok")
    d = p.to_dict()
    p2 = QuarantinePacket.from_dict(d)
    assert p2.id == p.id
    assert p2.zone == p.zone
    assert p2.decision == p.decision
    assert p2.backlog_items == p.backlog_items
    assert len(p2.history) == len(p.history)
    assert all(isinstance(a, RoleAction) for a in p2.history)


def test_packet_from_dict_handles_missing_optionals():
    """Backwards-compat: older packet JSON may not have every field."""
    minimal = {"id": "q-test", "raw": "x"}
    p = QuarantinePacket.from_dict(minimal)
    assert p.id == "q-test"
    assert p.raw == "x"
    assert p.zone == Zone.HOLDING.value
    assert p.history == []
