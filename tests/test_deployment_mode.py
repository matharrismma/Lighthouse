"""Tests for deployment mode gating.

Covers:
  - get_mode() defaults and env-var override
  - invalid mode falls back to "open"
  - token_present() logic (file missing, empty, non-empty)
  - writes_allowed() per mode
  - mode_info() dict shape
  - mode_gate_middleware: lockdown → 423, restricted without token → 423,
    open passes through, GET in lockdown passes through

No network calls. Uses tmp_path and monkeypatch for isolation.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from api.deployment_mode import (
    get_mode,
    mode_gate_middleware,
    mode_info,
    token_present,
    writes_allowed,
)


# ── get_mode ──────────────────────────────────────────────────────────────────

def test_get_mode_default_is_open(monkeypatch):
    monkeypatch.delenv("CONCORDANCE_MODE", raising=False)
    assert get_mode() == "open"


def test_get_mode_reads_env(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    assert get_mode() == "lockdown"


def test_get_mode_case_insensitive(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "RESTRICTED")
    assert get_mode() == "restricted"


def test_get_mode_invalid_falls_back_to_open(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "banana")
    assert get_mode() == "open"


def test_get_mode_quantum(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "quantum")
    assert get_mode() == "quantum"


# ── token_present ─────────────────────────────────────────────────────────────

def test_token_present_false_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(tmp_path / "no_such_file.key"))
    assert token_present() is False


def test_token_present_false_when_file_empty(tmp_path, monkeypatch):
    key_file = tmp_path / "empty.key"
    key_file.write_bytes(b"")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    assert token_present() is False


def test_token_present_true_when_file_has_content(tmp_path, monkeypatch):
    key_file = tmp_path / "token.key"
    key_file.write_bytes(b"secret-token-data")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    assert token_present() is True


# ── writes_allowed ────────────────────────────────────────────────────────────

def test_writes_allowed_in_open_mode(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "open")
    assert writes_allowed() is True


def test_writes_blocked_in_lockdown(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    assert writes_allowed() is False


def test_writes_blocked_in_restricted_without_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "restricted")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(tmp_path / "missing.key"))
    assert writes_allowed() is False


def test_writes_allowed_in_restricted_with_token(tmp_path, monkeypatch):
    key_file = tmp_path / "token.key"
    key_file.write_bytes(b"valid-token")
    monkeypatch.setenv("CONCORDANCE_MODE", "restricted")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    assert writes_allowed() is True


def test_writes_blocked_in_quantum_without_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "quantum")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(tmp_path / "missing.key"))
    assert writes_allowed() is False


def test_writes_allowed_in_quantum_with_token(tmp_path, monkeypatch):
    key_file = tmp_path / "token.key"
    key_file.write_bytes(b"quantum-token")
    monkeypatch.setenv("CONCORDANCE_MODE", "quantum")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    assert writes_allowed() is True


# ── mode_info ─────────────────────────────────────────────────────────────────

def test_mode_info_shape_open(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "open")
    info = mode_info()
    assert info["mode"] == "open"
    assert info["writes_enabled"] is True
    assert "token_path" in info
    assert info["token_present"] is None  # not checked in open mode
    assert "description" in info


def test_mode_info_shape_lockdown(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    info = mode_info()
    assert info["mode"] == "lockdown"
    assert info["writes_enabled"] is False
    assert info["token_present"] is None


def test_mode_info_token_present_checked_in_restricted(tmp_path, monkeypatch):
    key_file = tmp_path / "token.key"
    key_file.write_bytes(b"data")
    monkeypatch.setenv("CONCORDANCE_MODE", "restricted")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    info = mode_info()
    assert info["token_present"] is True


# ── mode_gate_middleware ──────────────────────────────────────────────────────

def _make_request(method: str) -> MagicMock:
    req = MagicMock()
    req.method = method
    return req


async def _call_next(request):
    """Stub next handler that returns a 200-like response."""
    resp = MagicMock()
    resp.status_code = 200
    return resp


def _run(coro):
    """Run an async coroutine synchronously for testing."""
    return asyncio.run(coro)


def test_middleware_open_allows_post(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "open")
    req = _make_request("POST")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 200


def test_middleware_open_allows_get(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "open")
    req = _make_request("GET")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 200


def test_middleware_lockdown_blocks_post(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    req = _make_request("POST")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 423


def test_middleware_lockdown_blocks_put(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    req = _make_request("PUT")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 423


def test_middleware_lockdown_allows_get(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    req = _make_request("GET")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 200


def test_middleware_restricted_blocks_post_without_token(tmp_path, monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "restricted")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(tmp_path / "absent.key"))
    req = _make_request("POST")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 423


def test_middleware_restricted_allows_post_with_token(tmp_path, monkeypatch):
    key_file = tmp_path / "token.key"
    key_file.write_bytes(b"valid")
    monkeypatch.setenv("CONCORDANCE_MODE", "restricted")
    monkeypatch.setenv("CONCORDANCE_TOKEN_PATH", str(key_file))
    req = _make_request("POST")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 200


def test_middleware_lockdown_423_body_contains_mode(monkeypatch):
    monkeypatch.setenv("CONCORDANCE_MODE", "lockdown")
    req = _make_request("DELETE")
    resp = _run(mode_gate_middleware(req, _call_next))
    assert resp.status_code == 423
    assert "json" in (resp.media_type or "")
