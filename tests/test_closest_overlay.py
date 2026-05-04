"""Tests for closest-case overlay on the journal capture flow.

The principal goal is to assist in wisdom by showing how engineered
the realm is. The closest-case overlay is one of the most direct
expressions of that goal: when a user writes, the engine shows them
that the well already holds something with similar shape, with the
precedent's summary and reasoning trace visible inline.

These tests verify the path end-to-end:
- The /journal/write response carries `closest_precedent` when one
  matches; null when not.
- The base-axis stripping ("governance.proposal" → "governance")
  works so packet shapes detected by the categorizer line up with
  the ledger's axis-indexed dimensions.
- Anchor-bearing precedents are matched on overlap.
- Distance is recorded in categorization and surfaces in response.
- Empty case (no matching axis) gracefully returns null without
  raising.
"""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

import pytest


@pytest.fixture
def client():
    from api.app import app
    return TestClient(app)


def test_governance_anchor_match_returns_full_precedent(client):
    """A decision-shaped seed with Mt 18:15-17 should match the
    admit-member-007 governance precedent and return its body."""
    r = client.post("/journal/write", json={
        "text": "Decision: should we admit Bob to membership? Mt 18:15-17. We have 3 witnesses.",
        "identity_acknowledged": True,
    })
    assert r.status_code == 200
    data = r.json()

    assert "closest_precedent" in data
    cp = data["closest_precedent"]
    assert cp is not None, "expected a precedent match for governance + Mt 18:15-17"
    assert cp.get("precedent_id"), "precedent must have an id"
    assert cp.get("axis") == "governance"
    assert cp.get("summary"), "precedent should include a human-readable summary"

    # The precedent's anchors must include Mt 18:15-17.
    anchor_refs = []
    for a in (cp.get("anchors") or []):
        if isinstance(a, dict):
            anchor_refs.append(a.get("ref"))
        else:
            anchor_refs.append(a)
    assert "Mt 18:15-17" in anchor_refs

    # Distance is recorded on the categorization.
    cat = data.get("entry", {}).get("categorization", {})
    assert cat.get("closest_precedent_id") == cp["precedent_id"]
    assert isinstance(cat.get("closest_precedent_distance"), (int, float))


def test_unrecognized_axis_returns_null(client):
    """A seed with no detected packet shape — or a shape unknown to
    the grid — should return closest_precedent: null without raising."""
    r = client.post("/journal/write", json={
        "text": "today was nice, the dog wagged his tail",
        "identity_acknowledged": True,
    })
    assert r.status_code == 200
    data = r.json()
    # Either no packet shape was detected, or no precedent matched.
    # Either way: closest_precedent must be null, not absent and not
    # an error.
    assert "closest_precedent" in data
    cp = data["closest_precedent"]
    assert cp is None or cp.get("precedent_id") is None


def test_capture_endpoint_also_carries_overlay(client):
    """The /capture funnel should also include closest_precedent in
    its response — it's the same enrichment path."""
    r = client.post("/capture", json={
        "text": "Decision: should we admit Bob? Mt 18:15-17.",
        "source": "test",
        "identity_acknowledged": True,
    })
    assert r.status_code == 200
    data = r.json()
    assert "closest_precedent" in data


def test_reasoning_overlay_is_preserved(client):
    """The reasoning_overlay structure on the precedent (the step-by-
    step trace of how the original decision was kept) should arrive
    intact so the frontend can render the 'how that one was kept'
    drawer."""
    r = client.post("/journal/write", json={
        "text": "Decision: should we admit Bob to membership? Mt 18:15-17.",
        "identity_acknowledged": True,
    })
    assert r.status_code == 200
    data = r.json()
    cp = data.get("closest_precedent")
    if cp is None:
        pytest.skip("no precedent matched in test fixtures")
    overlay = cp.get("reasoning_overlay")
    if overlay:
        assert isinstance(overlay, dict)
        # Each step should have a non-empty string explanation.
        for k, v in overlay.items():
            assert isinstance(v, str)
            assert v.strip()


def test_unit_capture_records_closest_match():
    """Direct unit test of the journal.capture path — the bug fix that
    strips the subtype from 'governance.proposal' to 'governance' so
    find_closest can match it."""
    from concordance_engine import journal
    e = journal.capture(
        "Decision: should we admit Bob to membership? Mt 18:15-17. Witnesses present.",
        look_up_precedent=True,
    )
    # The categorizer should detect a packet shape.
    assert e.categorization.detected_packet_shape, \
        "categorizer should detect a packet shape on a governance-like seed"
    # The base axis should be recognized by the grid; precedent lookup
    # should run and produce a match.
    assert e.categorization.closest_precedent_id, \
        "expected closest_precedent_id to be populated for governance seed"
    assert isinstance(e.categorization.closest_precedent_distance, (int, float))
    assert e.categorization.closest_precedent_distance >= 0
    assert e.categorization.closest_precedent_distance <= 1
