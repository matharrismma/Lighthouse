"""Smoke + integration tests for the FastAPI surface.

Two categories:

1. **Import smoke test.** Prevents last night's whole class of bug —
   a truncated handler in api/app.py (commit 572d03e) sat broken
   because nothing in the test suite imported the module. Adding
   `from api import app` to CI catches the next syntax error before
   the live service goes 502.

2. **/seal endpoint integration.** The new endpoint is the agent-
   facing surface for tonight's WitnessRecord schema. Tests confirm
   the response shape carries axis_coords, anchor.layer info on
   verifier rules, and never a fabricated answer field.

The tests use FastAPI's TestClient (not subprocess), so they run in
the same Python process as pytest. No live server required.
"""
from __future__ import annotations

import pytest

from fastapi.testclient import TestClient


# ── Import smoke test ──────────────────────────────────────────────────

def test_api_app_imports_cleanly():
    """The single most-load-bearing test. If this passes, api/app.py is
    syntactically valid and all of its module-level imports resolve.
    Last night's SyntaxError-in-production bug would have been caught
    at PR-review time by this test."""
    from api import app
    assert app.app is not None
    # Confirm the engine import branch took the success path; otherwise
    # half the endpoints will 503.
    assert app._ENGINE_AVAILABLE, (
        f"engine not importable inside api/app.py — "
        f"{app._ENGINE_ERROR}"
    )


def test_api_app_registers_expected_routes():
    """Lock in the route inventory. Adding a route is cheap; removing
    one shouldn't be silent."""
    from api import app as a
    paths = {r.path for r in a.app.routes if hasattr(r, "path")}
    expected_minimum = {
        "/health",
        "/version",
        "/validate",
        "/submit",
        "/seal",
        "/ledger",
        "/ledger/verify",
        "/ledger/{packet_id}",
        "/llms.txt",
        "/",
    }
    missing = expected_minimum - paths
    assert not missing, f"routes missing: {missing}"


# ── /version endpoint ─────────────────────────────────────────────────

def test_version_endpoint_returns_engine_info():
    from api.app import app
    client = TestClient(app)
    r = client.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert "git_sha" in data
    assert "schema_version" in data
    assert data["engine_available"] is True


# ── /seal endpoint ─────────────────────────────────────────────────────

def _client():
    from api.app import app
    return TestClient(app)


def test_seal_returns_witness_record_shape():
    """A passing chemistry packet should produce a sealed record with
    the WitnessRecord shape — not the legacy EngineResult shape."""
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "chemistry",
            "claims": ["water is H2O"],
            "created_epoch": 1,
            "witness_count": 0,
            "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # WitnessRecord-specific fields (NOT in old EngineResult)
    assert "schema_version" in body
    assert "verifier_results" in body  # first-class, not buried
    assert "axis_coords" in body
    # Old EngineResult fields still present for compat
    assert body["overall"] == "PASS"
    assert "gate_results" in body


def test_seal_axis_coords_resolved_for_known_domain():
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "mathematics",
            "claims": ["2+2=4"],
            "created_epoch": 1,
            "witness_count": 0, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200
    coords = r.json().get("axis_coords")
    assert coords is not None
    assert coords["axis"] == "mathematics"
    assert "reasoning" in coords["dimensions"]


def test_seal_no_fabricated_answer_field():
    """The doctrine: the engine categorizes, it does not answer.
    Confirmed at the API surface for any sealed record."""
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "chemistry", "claims": ["x"],
            "created_epoch": 1, "witness_count": 0, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200
    body = r.json()
    forbidden = {"final_answer", "answer", "engine_answer", "verdict_answer"}
    assert not (forbidden & set(body.keys())), (
        f"fabricated answer field present: {forbidden & set(body.keys())}"
    )


def test_seal_writes_to_ledger_and_returns_seq():
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "chemistry", "claims": ["sodium chloride is NaCl"],
            "created_epoch": 1, "witness_count": 0, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200
    body = r.json()
    # ledger_seq populated when the ledger append succeeded
    assert body.get("ledger_seq") is not None
    assert body.get("ledger_entry_hash") is not None


def test_seal_rejects_malformed_packet_at_schema():
    """Tonight's schema validation enforces at the API surface."""
    client = _client()
    r = client.post("/seal", json={
        "packet": {"domain": 42},  # int, not string
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["overall"] == "REJECT"
    # The reject should cite schema validation
    red_rejects = [
        gr for gr in body["gate_results"]
        if gr["gate"] == "RED" and gr["status"] == "REJECT"
    ]
    assert red_rejects
    reasons = " ".join(red_rejects[0]["reasons"])
    assert "schema" in reasons.lower()


def test_seal_with_anchors_passes_them_through():
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "chemistry", "claims": ["x"],
            "created_epoch": 1, "witness_count": 0, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
        "anchors": [
            {"ref": "Mt 5:37", "layer": "jesus_words"},
            {"ref": "Gen 1:1", "layer": "bible"},
        ],
    })
    assert r.status_code == 200
    body = r.json()
    anchors = body.get("anchors") or []
    refs = [a.get("ref") for a in anchors]
    assert "Mt 5:37" in refs
    layers = [a.get("layer") for a in anchors]
    assert "jesus_words" in layers


def test_seal_rejects_malformed_anchors_at_422():
    client = _client()
    r = client.post("/seal", json={
        "packet": {"domain": "chemistry", "claims": ["x"],
                   "created_epoch": 1, "witness_count": 0,
                   "required_witnesses": 0},
        "now_epoch": 9999999999,
        "anchors": [{"layer": "jesus_words"}],  # missing ref
    })
    assert r.status_code == 422


def test_seal_verifier_results_carry_anchors_when_annotated():
    """A governance packet that triggers witness_count_consistency
    should produce a verifier result whose data carries the Mt 18:16
    anchor (from tonight's rule-anchor rollout). End-to-end through
    the API."""
    client = _client()
    r = client.post("/seal", json={
        "packet": {
            "domain": "governance",
            "DECISION_PACKET": {
                "title": "Test decision",
                "scope": "adapter",
                "red_items": ["no theft"],
                "floor_items": ["affirm consent"],
                "way_path": "consult elders before binding",
                "execution_steps": ["step 1"],
                "witnesses": ["Alice", "Bob"],
            },
            "witness_count": 2,
            "scope": "adapter",
            "created_epoch": 1, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # Find the witness_count_consistency result
    wcc = next(
        (v for v in body["verifier_results"]
         if v["name"] == "governance.witness_count_consistency"),
        None,
    )
    assert wcc is not None, "witness_count_consistency verifier didn't fire"
    assert wcc.get("data", {}).get("anchor", {}).get("ref") == "Mt 18:16"


# ── Existing endpoints still work ──────────────────────────────────────

def test_health_still_works():
    client = _client()
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_validate_still_returns_old_engine_result_shape():
    """Backward compat: /validate must keep the old EngineResult shape
    so existing callers don't break when /seal becomes available."""
    client = _client()
    r = client.post("/validate", json={
        "packet": {
            "domain": "chemistry", "claims": ["water is H2O"],
            "created_epoch": 1, "witness_count": 0, "required_witnesses": 0,
        },
        "now_epoch": 9999999999,
    })
    assert r.status_code == 200
    body = r.json()
    # Old shape
    assert set(body.keys()) >= {"overall", "gate_results", "packet_hash", "elapsed_ms"}
    # No WitnessRecord-specific fields (the legacy contract)
    assert "schema_version" not in body
    assert "axis_coords" not in body
