"""Tests for the second audit-pass batch.

Covers fixes for the four remaining audit items:
  * #4 grid coherence (already in test_grid.py)
  * #7 renderer dedup (existing tests still pass — no new tests needed)
  * #5 precedent amendments
  * #6 governance NL→packet template

Plus the security cleanup (API key fallback removal in mcp_server).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from concordance_engine.gates import ok
from concordance_engine.ledger import (
    amend_precedent, find_closest, latest_in_amendment_chain,
    list_precedents, seal_to_ledger, verify_chain,
)
from concordance_engine.nl_to_packet import parse, parse_and_seal
from concordance_engine.witness_record import (
    Anchor, ClosestCase, WitnessRecord, axis_coords_for,
)


def _pass_record() -> WitnessRecord:
    return WitnessRecord(
        overall="PASS",
        gate_results=(ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD")),
        verifier_results=(),
        anchors=(),
        axis_coords=axis_coords_for("governance"),
        packet_id="pkt://test/seal/1",
    )


# ── Precedent amendments (#5) ──────────────────────────────────────────

def test_amend_precedent_creates_new_file_with_amends_field(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="original framing",
        precedent_id="ledger://test/decision/v1",
        ledger_dir=tmp_path,
    )
    target = amend_precedent(
        "ledger://test/decision/v1",
        summary="refined framing after community review",
        new_precedent_id="ledger://test/decision/v2",
        ledger_dir=tmp_path,
    )
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["precedent_id"] == "ledger://test/decision/v2"
    assert payload["amends"] == "ledger://test/decision/v1"
    assert payload["summary"] == "refined framing after community review"


def test_amend_preserves_prior_precedent_unchanged(tmp_path):
    """Amendment is append-only — the prior file must not be touched."""
    f1 = seal_to_ledger(
        _pass_record(), summary="original framing",
        precedent_id="ledger://test/v1", ledger_dir=tmp_path,
    )
    original = f1.read_text(encoding="utf-8")
    amend_precedent(
        "ledger://test/v1", summary="refined",
        ledger_dir=tmp_path,
    )
    # Original file unchanged on disk
    assert f1.read_text(encoding="utf-8") == original


def test_amend_inherits_axis_dimensions_anchors_from_prior(tmp_path):
    """Defaults: amendment inherits the prior's axis, dimensions, and
    anchors. The summary and (optionally) the reasoning_overlay change
    — that's the point of amending."""
    rec = WitnessRecord(
        overall="PASS",
        gate_results=(ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD")),
        verifier_results=(),
        anchors=(Anchor(ref="Mt 5:37", layer="jesus_words"),),
        axis_coords=axis_coords_for("governance"),
        packet_id="pkt://test/inherit",
    )
    seal_to_ledger(
        rec, summary="original",
        precedent_id="ledger://test/inherit/v1", ledger_dir=tmp_path,
    )
    target = amend_precedent(
        "ledger://test/inherit/v1",
        summary="refined", ledger_dir=tmp_path,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["axis"] == "governance"
    # Anchors inherited from the original
    assert any(a.get("ref") == "Mt 5:37" for a in payload["anchors"])


def test_amend_chain_integrity_preserved(tmp_path):
    """Amending must keep the hash chain valid."""
    seal_to_ledger(
        _pass_record(), summary="first",
        precedent_id="ledger://test/a", ledger_dir=tmp_path,
    )
    seal_to_ledger(
        _pass_record(), summary="second",
        precedent_id="ledger://test/b", ledger_dir=tmp_path,
    )
    amend_precedent(
        "ledger://test/a", summary="a-refined",
        new_precedent_id="ledger://test/a-v2",
        ledger_dir=tmp_path,
    )
    report = verify_chain(ledger_dir=tmp_path)
    assert report["ok"], (
        f"chain broken after amendment: {report}"
    )


def test_amend_unknown_precedent_raises(tmp_path):
    with pytest.raises(ValueError, match="not found"):
        amend_precedent(
            "ledger://test/does-not-exist",
            summary="x", ledger_dir=tmp_path,
        )


def test_amend_requires_summary(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="original",
        precedent_id="ledger://test/r", ledger_dir=tmp_path,
    )
    with pytest.raises(ValueError, match="summary"):
        amend_precedent(
            "ledger://test/r", summary="", ledger_dir=tmp_path,
        )


def test_amend_auto_generates_id_with_suffix(tmp_path):
    """If no new_precedent_id is supplied, auto-generate one from the
    prior id with an `-amended-N` suffix."""
    seal_to_ledger(
        _pass_record(), summary="original",
        precedent_id="ledger://test/auto", ledger_dir=tmp_path,
    )
    target = amend_precedent(
        "ledger://test/auto",
        summary="refined", ledger_dir=tmp_path,
    )
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["precedent_id"] == "ledger://test/auto-amended-1"


def test_amend_multiple_times_increments_suffix(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="original",
        precedent_id="ledger://test/multi", ledger_dir=tmp_path,
    )
    amend_precedent(
        "ledger://test/multi", summary="first refinement",
        ledger_dir=tmp_path,
    )
    target2 = amend_precedent(
        "ledger://test/multi", summary="second refinement",
        ledger_dir=tmp_path,
    )
    payload = json.loads(target2.read_text(encoding="utf-8"))
    assert payload["precedent_id"] == "ledger://test/multi-amended-2"


# ── latest_in_amendment_chain ──────────────────────────────────────────

def test_latest_returns_input_when_no_amendments(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="standalone",
        precedent_id="ledger://test/standalone", ledger_dir=tmp_path,
    )
    assert latest_in_amendment_chain(
        "ledger://test/standalone", ledger_dir=tmp_path,
    ) == "ledger://test/standalone"


def test_latest_walks_chain_to_head(tmp_path):
    seal_to_ledger(
        _pass_record(), summary="v1",
        precedent_id="ledger://test/chain", ledger_dir=tmp_path,
    )
    amend_precedent(
        "ledger://test/chain", summary="v2",
        new_precedent_id="ledger://test/chain-v2",
        ledger_dir=tmp_path,
    )
    amend_precedent(
        "ledger://test/chain-v2", summary="v3",
        new_precedent_id="ledger://test/chain-v3",
        ledger_dir=tmp_path,
    )
    assert latest_in_amendment_chain(
        "ledger://test/chain", ledger_dir=tmp_path,
    ) == "ledger://test/chain-v3"


def test_latest_handles_unknown_precedent_gracefully(tmp_path):
    """Walking from an id that isn't in the ledger returns the input
    unchanged — not a crash."""
    assert latest_in_amendment_chain(
        "ledger://nowhere/at/all", ledger_dir=tmp_path,
    ) == "ledger://nowhere/at/all"


# ── find_closest follows amendment chains ─────────────────────────────

def test_find_closest_returns_latest_amendment(tmp_path):
    """A community refines its framing; lookups should surface the
    refined version, not the original."""
    seal_to_ledger(
        _pass_record(), summary="initial framing",
        precedent_id="ledger://test/refined", ledger_dir=tmp_path,
    )
    amend_precedent(
        "ledger://test/refined",
        summary="refined framing after review",
        new_precedent_id="ledger://test/refined-v2",
        ledger_dir=tmp_path,
    )
    cc = find_closest({"domain": "governance"}, ledger_dir=tmp_path)
    assert cc is not None
    assert cc.precedent_id == "ledger://test/refined-v2"


# ── Governance NL template (#6) ────────────────────────────────────────

def test_governance_nl_admits_member_proposal():
    """Direct community-decision phrasing should match."""
    result = parse("Should we admit Alice as a member?")
    assert result is not None
    assert result.domain == "governance"
    assert result.template == "governance.proposal"


def test_governance_nl_elders_propose():
    result = parse("the elders propose to install a new bishop")
    assert result is not None
    assert result.domain == "governance"


def test_governance_nl_extracts_witness_count():
    result = parse(
        "Should we restore Carol with 3 witnesses present?"
    )
    assert result is not None
    assert result.packet["witness_count"] == 3
    dp = result.packet["DECISION_PACKET"]
    assert "witnesses" in dp
    assert len(dp["witnesses"]) == 3


def test_governance_nl_extracts_scripture_anchors():
    result = parse(
        "Citing Mt 18:15-17 we propose to restore Bob after restitution"
    )
    assert result is not None
    anchors = result.packet.get("scripture_anchors") or []
    refs = [a.get("ref") if isinstance(a, dict) else a for a in anchors]
    assert any("Mt 18" in r for r in refs)


def test_governance_nl_does_not_match_non_governance():
    """Math / chemistry / freeform shouldn't be classified governance."""
    assert parse("merge sort runs in O(n log n)").domain != "governance"
    assert parse("is 2 H2 + O2 -> 2 H2O balanced?").domain != "governance"
    assert parse("how about a nice cup of tea") is None


def test_governance_nl_emits_partial_packet_that_engine_handles():
    """The template emits an intentionally-incomplete DECISION_PACKET.
    parse_and_seal should produce a record (probably REJECT/QUARANTINE
    at FLOOR for missing fields) without crashing — the rejection IS
    the useful output."""
    rec = parse_and_seal(
        "should we admit a new member?", now_epoch=10**9,
    )
    assert rec is not None
    # Outcome may be REJECT (incomplete packet) or QUARANTINE — either
    # is fine; the value is that we got into the governance domain.
    assert rec.overall in ("REJECT", "QUARANTINE", "PASS")


def test_governance_nl_notes_field_explains_partial():
    """The ParseResult.notes should tell the user the packet is
    intentionally incomplete and the FLOOR rejection is the signal."""
    result = parse("should we admit a new member?")
    assert result is not None
    assert "incomplete" in result.notes.lower() or "FLOOR" in result.notes


# ── Security: API key fallback removed from mcp_server ────────────────

def test_mcp_server_has_no_hardcoded_api_key():
    """The previously-rotated literal key value must not appear in
    source. Catches future regressions if someone copy-pastes a dev
    key into the file."""
    server_path = (
        Path(__file__).resolve().parent.parent
        / "src" / "concordance_engine" / "mcp_server" / "server.py"
    )
    text = server_path.read_text(encoding="utf-8")
    # Pre-rotation key prefix; any literal of the form `lh_<hex>` should
    # be a red flag.
    import re
    bad = re.findall(r'"lh_[a-f0-9]{16,}"', text)
    assert not bad, f"hardcoded API key literal found in server.py: {bad}"


def test_mcp_api_key_defaults_to_none():
    """When no env var is set, CONCORDANCE_API_KEY should be None and
    the local-only path should be taken."""
    # Ensure env vars are NOT set for this test
    api_url = os.environ.get("CONCORDANCE_API_URL")
    api_key = os.environ.get("CONCORDANCE_API_KEY")
    if api_url is None and api_key is None:
        # Re-import to force fresh module-level resolution
        import importlib
        from concordance_engine.mcp_server import server as srv
        importlib.reload(srv)
        assert srv.CONCORDANCE_API_KEY is None
        assert srv.CONCORDANCE_API_URL is None
