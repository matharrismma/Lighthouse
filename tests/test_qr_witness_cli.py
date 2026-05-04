"""Subprocess tests for `concordance qr` and `concordance witness`.

These exercise the full CLI path (argparse → dispatch → output) via
real subprocess invocations, like test_broadcast_cli.py does for the
LoRa wire CLI. Pure-function tests in test_witness_signatures.py cover
the underlying primitives; this file confirms the CLI wires them
together correctly.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


CLI = [sys.executable, "-m", "concordance_engine.cli"]


def run(args, stdin: str = "", env: dict | None = None) -> subprocess.CompletedProcess:
    import os as _os
    env_full = _os.environ.copy()
    env_full["PYTHONIOENCODING"] = "utf-8"
    if env:
        env_full.update(env)
    return subprocess.run(
        CLI + args,
        input=stdin,
        capture_output=True,
        text=True,
        env=env_full,
        encoding="utf-8",
    )


# ── concordance qr ──────────────────────────────────────────────────


def test_qr_emits_precedent_url_with_default_host():
    """A bare subject becomes a /ledger/<id> URL on the default host."""
    r = run(["qr", "ledger://test/abc"])
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    assert out.startswith("https://narrowhighway.com/ledger/")
    assert "test" in out  # the precedent id portion is in the URL


def test_qr_capture_flag_emits_share_url():
    """--capture emits /share.html with text= prefilled."""
    r = run(["qr", "--capture", "Mt 5:37 — yes is yes"])
    assert r.returncode == 0, r.stderr
    out = r.stdout.strip()
    assert "/share.html?text=" in out
    # Spaces and unicode em-dash must be URL-encoded.
    assert " " not in out
    assert "Mt%205" in out


def test_qr_no_args_emits_home_url():
    """Bare invocation emits the engine's home URL."""
    r = run(["qr"])
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().endswith("/")


def test_qr_custom_host_used_when_provided():
    r = run(["qr", "--host", "https://my-engine.example", "ledger://test/x"])
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().startswith("https://my-engine.example/ledger/")


def test_qr_host_via_env(monkeypatch):
    r = run(["qr", "ledger://test/x"],
            env={"CONCORDANCE_HOST": "https://env-engine.example"})
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().startswith("https://env-engine.example/ledger/")


def test_qr_subject_and_capture_mutually_exclusive():
    """Both at once is a usage error (exit 4)."""
    r = run(["qr", "--capture", "x", "subject"])
    assert r.returncode == 4
    assert "mutually exclusive" in r.stderr


def test_qr_empty_host_errors():
    """Empty host is a configuration error."""
    r = run(["qr", "ledger://x"],
            env={"CONCORDANCE_HOST": ""})
    # Empty env var triggers the default; host comes from --host arg if
    # given, otherwise the default kicks in. With CONCORDANCE_HOST="" we
    # still fall through to the default. Check the explicit empty case:
    r2 = run(["qr", "--host", "", "ledger://x"])
    assert r2.returncode == 4
    assert "host" in r2.stderr.lower()


# ── concordance witness ─────────────────────────────────────────────


# All witness commands need cryptography installed (lazy via signing.py).
cryptography = pytest.importorskip("cryptography")


def test_witness_sign_emits_attestation_json(tmp_path):
    """`concordance witness sign` produces a valid attestation."""
    # Generate a private key file for the test.
    from concordance_engine import signing
    priv, _pub = signing.generate_keypair()
    key_file = tmp_path / "test.key"
    key_file.write_text(priv, encoding="utf-8")

    r = run(["witness", "sign",
             "ledger://test/decision-1",
             "deadbeef0123",
             "--name", "Alice",
             "--role", "elder",
             "--key", str(key_file)])
    assert r.returncode == 0, r.stderr
    att = json.loads(r.stdout)
    assert att["precedent_id"] == "ledger://test/decision-1"
    assert att["entry_hash"] == "deadbeef0123"
    assert att["witness_name"] == "Alice"
    assert att["witness_role"] == "elder"
    assert att["witness_pubkey"]
    assert att["signature"]


def test_witness_sign_inline_key_works(tmp_path):
    """The --key argument also accepts a literal b64u string when no
    file by that name exists (operator-friendly inline form)."""
    from concordance_engine import signing
    priv, _pub = signing.generate_keypair()
    r = run(["witness", "sign",
             "ledger://test/inline",
             "abc",
             "--name", "X", "--role", "y",
             "--key", priv])
    assert r.returncode == 0, r.stderr
    att = json.loads(r.stdout)
    assert att["witness_name"] == "X"


def test_witness_verify_accepts_valid_attestation(tmp_path):
    """sign → verify roundtrips with exit 0."""
    from concordance_engine import signing
    priv, _pub = signing.generate_keypair()
    sign_r = run(["witness", "sign",
                  "ledger://test/v",
                  "h",
                  "--name", "x", "--role", "y",
                  "--key", priv])
    assert sign_r.returncode == 0

    v_r = run(["witness", "verify"], stdin=sign_r.stdout)
    assert v_r.returncode == 0, v_r.stderr
    res = json.loads(v_r.stdout)
    assert res["ok"] is True
    assert res["reason"] == "ok"


def test_witness_verify_rejects_tampered_attestation(tmp_path):
    """Editing any signed field invalidates the signature; exit 1."""
    from concordance_engine import signing
    priv, _pub = signing.generate_keypair()
    sign_r = run(["witness", "sign",
                  "ledger://test/tamper",
                  "original",
                  "--name", "x", "--role", "y",
                  "--key", priv])
    assert sign_r.returncode == 0
    att = json.loads(sign_r.stdout)
    # Tamper the entry_hash.
    att["entry_hash"] = "different"
    tampered = json.dumps(att)

    v_r = run(["witness", "verify"], stdin=tampered)
    assert v_r.returncode == 1, "tampered must exit nonzero"
    res = json.loads(v_r.stdout)
    assert res["ok"] is False
    assert "signature" in res["reason"].lower()


def test_witness_verify_malformed_input_errors():
    """Non-JSON stdin returns exit 4."""
    r = run(["witness", "verify"], stdin="not valid json at all")
    assert r.returncode == 4
    assert "json" in r.stderr.lower()


def test_witness_list_empty_for_unknown_precedent(tmp_path):
    """`concordance witness list` on a precedent with no attestations
    on file prints a friendly empty message."""
    r = run(["witness", "list", "ledger://test/no-attestations-recorded"],
            env={"CONCORDANCE_WITNESS_DIR": str(tmp_path)})
    assert r.returncode == 0, r.stderr
    assert "no attestations" in r.stdout.lower()


def test_witness_sign_append_then_list_shows_entry(tmp_path):
    """Sign --append writes to the per-precedent JSONL store; list
    surfaces it with a verify mark."""
    from concordance_engine import signing
    priv, _pub = signing.generate_keypair()
    sign_r = run(["witness", "sign",
                  "ledger://test/append-then-list",
                  "h",
                  "--name", "Alice", "--role", "elder",
                  "--key", priv,
                  "--append"],
                 env={"CONCORDANCE_WITNESS_DIR": str(tmp_path)})
    assert sign_r.returncode == 0, sign_r.stderr

    list_r = run(["witness", "list", "ledger://test/append-then-list"],
                 env={"CONCORDANCE_WITNESS_DIR": str(tmp_path)})
    assert list_r.returncode == 0
    # The output should include the witness's name + role + verify mark.
    assert "Alice" in list_r.stdout
    assert "elder" in list_r.stdout
    # ASCII checkmark or unicode — flexible across encoding.
    assert "✓" in list_r.stdout or "ok" in list_r.stdout.lower()
