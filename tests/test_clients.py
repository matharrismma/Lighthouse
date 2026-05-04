"""Tests for the capture-anywhere client scripts in client/.

These scripts are standalone — not part of the engine package — so
we load them with importlib for testing. Coverage focuses on the
pure functions that don't touch the network or external services:
multipart-form construction, file parsing, render output, state-
file roundtrips, wire-packet detection.

Network-dependent paths (POST to /capture, fetch from /chain/since,
etc.) are exercised by the engine's own tests. Here we just want
to know the client-side plumbing works.

Why this matters: the clients were shipped well-documented but
unverified. Each one POSTs into /capture or reads from the engine
on behalf of a user; bugs would silently corrupt their journals.
These tests are the seatbelt.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


# ── Loader: import client/*.py as modules without making them packages ───


CLIENT_DIR = Path(__file__).resolve().parent.parent / "client"


def _load_client(name: str):
    """Load client/<name>.py as a module. Cached via sys.modules so
    repeated calls don't reload."""
    mod_name = f"_client_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    src = CLIENT_DIR / f"{name}.py"
    if not src.exists():
        pytest.skip(f"client script not present: {src}")
    spec = importlib.util.spec_from_file_location(mod_name, src)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── digest_mail.py ─────────────────────────────────────────────────


def test_digest_mail_load_subscribers_handles_comments_and_blanks(tmp_path):
    digest = _load_client("digest_mail")
    f = tmp_path / "subs.txt"
    f.write_text(
        "# this is a comment\n"
        "alice@example.com\n"
        "\n"
        "  bob@example.com  \n"
        "# another comment\n"
        "charlie@example.com\n",
        encoding="utf-8",
    )
    out = digest.load_subscribers(str(f))
    assert "alice@example.com" in out
    assert "bob@example.com" in out
    assert "charlie@example.com" in out
    assert all(not s.startswith("#") for s in out)
    # comments and blank lines stripped
    assert len(out) == 3


def test_digest_mail_load_subscribers_missing_file():
    digest = _load_client("digest_mail")
    out = digest.load_subscribers("/nonexistent/path/subs.txt")
    assert out == []


def test_digest_mail_render_text_includes_doctrine_and_entries():
    digest = _load_client("digest_mail")
    entries = [
        {"seq": 42, "packet_id": "p/test", "overall": "PASS",
         "domain": "governance", "timestamp_iso": "2026-05-04",
         "top_reasons": ["a", "b"]},
    ]
    identity = {"short": "Serves Jesus Christ. Conduit, not source."}
    text = digest.render_text(entries, identity, "https://test.example")
    assert "Concordance digest" in text
    assert "p/test" in text
    assert "1 newly-sealed precedent" in text or "newly-sealed" in text
    assert "Serves Jesus Christ" in text
    assert "https://test.example/ledger/p/test" in text


def test_digest_mail_render_html_escapes_user_content():
    digest = _load_client("digest_mail")
    entries = [{
        "seq": 1, "packet_id": "<script>x</script>", "overall": "PASS",
        "domain": "test", "top_reasons": ["evil <input>"],
    }]
    html = digest.render_html(entries, {}, "https://test.example")
    # Tag injection must be escaped.
    assert "<script>x</script>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;input&gt;" in html


def test_digest_mail_h_escapes_html():
    digest = _load_client("digest_mail")
    assert digest._h("<&>\"") == "&lt;&amp;&gt;&quot;"
    assert digest._h(None) == ""
    assert digest._h(42) == "42"


def test_digest_mail_state_roundtrip(tmp_path, monkeypatch):
    digest = _load_client("digest_mail")
    state_file = tmp_path / "digest_state.json"
    monkeypatch.setattr(digest, "STATE_FILE", str(state_file))
    s = digest._load_state()
    assert s["last_seq"] == 0
    s["last_seq"] = 17
    s["last_sent_at"] = 1700000000
    digest._save_state(s)
    s2 = digest._load_state()
    assert s2["last_seq"] == 17
    assert s2["last_sent_at"] == 1700000000


# ── ipfs_pin.py ────────────────────────────────────────────────────


def test_ipfs_pin_multipart_file_well_formed():
    ipfs = _load_client("ipfs_pin")
    body = ipfs._multipart_file("test.json", b'{"x": 1}',
                                content_type="application/json")
    body_str = body.decode("utf-8", errors="replace")
    # Has the boundary on both sides.
    assert ipfs._BOUNDARY in body_str
    # Closing boundary uses the dash-dash convention.
    assert body.endswith(f"--{ipfs._BOUNDARY}--\r\n".encode())
    # Filename made it in.
    assert 'filename="test.json"' in body_str
    # Content-Type header for the part.
    assert "application/json" in body_str
    # The actual content is present.
    assert b'{"x": 1}' in body


def test_ipfs_pin_multipart_handles_binary_content():
    ipfs = _load_client("ipfs_pin")
    binary = bytes(range(256))
    body = ipfs._multipart_file("binary.dat", binary,
                                content_type="application/octet-stream")
    # Binary survives intact in the multipart body.
    assert binary in body


def test_ipfs_pin_state_roundtrip(tmp_path, monkeypatch):
    ipfs = _load_client("ipfs_pin")
    state_file = tmp_path / "ipfs_pinned.json"
    monkeypatch.setattr(ipfs, "STATE_FILE", str(state_file))
    s = ipfs._load_state()
    assert "pinned" in s
    s["pinned"]["test/abc"] = {
        "cid": "Qm123", "pinned_at": 100, "size_bytes": 42,
    }
    ipfs._save_state(s)
    s2 = ipfs._load_state()
    assert s2["pinned"]["test/abc"]["cid"] == "Qm123"


# ── watch_folder.py ────────────────────────────────────────────────


def test_watch_folder_find_files_filters_by_extension(tmp_path):
    watch = _load_client("watch_folder")
    (tmp_path / "yes.txt").write_text("a")
    (tmp_path / "yep.md").write_text("b")
    (tmp_path / "no.json").write_text("c")
    (tmp_path / "no.bin").write_bytes(b"d")
    found = watch.find_files(
        tmp_path,
        extensions={".txt", ".md"},
        seen=set(),
        min_mtime=None,
    )
    names = sorted(p.name for p in found)
    assert names == ["yep.md", "yes.txt"]


def test_watch_folder_find_files_skips_seen(tmp_path):
    watch = _load_client("watch_folder")
    f = tmp_path / "thing.txt"
    f.write_text("hello")
    seen = {f}
    found = watch.find_files(
        tmp_path, extensions={".txt"}, seen=seen, min_mtime=None,
    )
    assert found == []


def test_watch_folder_find_files_respects_min_mtime(tmp_path):
    import os as _os
    import time as _time
    watch = _load_client("watch_folder")
    old = tmp_path / "old.txt"
    old.write_text("a")
    # Make it look ancient.
    long_ago = _time.time() - 86400  # 1 day ago
    _os.utime(old, (long_ago, long_ago))
    new = tmp_path / "new.txt"
    new.write_text("b")
    cutoff = _time.time() - 3600  # last hour only
    found = watch.find_files(
        tmp_path, extensions={".txt"}, seen=set(), min_mtime=cutoff,
    )
    names = [p.name for p in found]
    assert "new.txt" in names
    assert "old.txt" not in names


def test_watch_folder_find_files_returns_empty_when_dir_missing(tmp_path):
    watch = _load_client("watch_folder")
    out = watch.find_files(
        tmp_path / "does_not_exist",
        extensions={".txt"}, seen=set(), min_mtime=None,
    )
    assert out == []


# ── meshtastic_bridge.py ───────────────────────────────────────────


def test_meshtastic_bridge_looks_like_wire_recognizes_seed_envelope():
    """Confirm the bridge correctly identifies a wire seed packet
    by its leading two bytes (WIRE_VERSION + WIRE_TYPE_SEED)."""
    bridge = _load_client("meshtastic_bridge")
    # Synthesize an actual wire packet via the engine.
    from concordance_engine.wire import SeedWire, WIRE_VERSION, WIRE_TYPE_SEED
    s = SeedWire(text="hello", source="lora_mesh")
    payload = s.to_bytes()
    assert bridge.looks_like_wire(payload) is True
    # First two bytes match.
    assert payload[0] == WIRE_VERSION
    assert payload[1] == WIRE_TYPE_SEED


def test_meshtastic_bridge_looks_like_wire_rejects_non_wire():
    bridge = _load_client("meshtastic_bridge")
    assert bridge.looks_like_wire(b"") is False
    assert bridge.looks_like_wire(b"\x99") is False
    assert bridge.looks_like_wire(b"hello world") is False
    # Right version byte but wrong type byte (e.g. ack only — only seed
    # is wired into the bridge for now).
    from concordance_engine.wire import WIRE_VERSION, WIRE_TYPE_ACK
    assert bridge.looks_like_wire(bytes([WIRE_VERSION, WIRE_TYPE_ACK, 0])) is False


# ── nostr_publish.py ───────────────────────────────────────────────


def test_nostr_publish_state_roundtrip(tmp_path, monkeypatch):
    nostr = _load_client("nostr_publish")
    state_file = tmp_path / "nostr_published.json"
    monkeypatch.setattr(nostr, "STATE_FILE", str(state_file))
    s = nostr._load_state()
    assert "published" in s
    s["published"]["test/abc"] = {
        "event_id": "abc123", "published_at": 100, "relays": ["wss://r1"],
    }
    nostr._save_state(s)
    s2 = nostr._load_state()
    assert s2["published"]["test/abc"]["event_id"] == "abc123"


def test_nostr_publish_default_relays_are_wss():
    """Default relay list must be wss:// URLs (the Nostr standard)."""
    nostr = _load_client("nostr_publish")
    assert isinstance(nostr.DEFAULT_RELAYS, list)
    assert len(nostr.DEFAULT_RELAYS) >= 1
    for r in nostr.DEFAULT_RELAYS:
        assert r.startswith("wss://"), f"non-wss relay in defaults: {r}"


def test_nostr_publish_kind_is_replaceable_parameterized():
    """KIND_SEALED_PRECEDENT must be in NIP-33 replaceable-
    parameterized range (30000-39999)."""
    nostr = _load_client("nostr_publish")
    assert 30000 <= nostr.KIND_SEALED_PRECEDENT <= 39999


# ── telegram_bot.py ────────────────────────────────────────────────


def test_telegram_bot_module_imports_cleanly():
    """The bot script must be importable; if it has a syntax or
    top-level error this test catches it."""
    tg = _load_client("telegram_bot")
    assert hasattr(tg, "main")
    assert hasattr(tg, "post_capture")
    assert hasattr(tg, "tg")  # Telegram API helper
    assert hasattr(tg, "DEFAULT_API")


def test_telegram_bot_default_api_url_present():
    tg = _load_client("telegram_bot")
    assert tg.DEFAULT_API.startswith(("http://", "https://"))


def test_telegram_bot_tg_url_format():
    """Just verify the Telegram API base is set correctly. Don't
    actually call out — the URL building is deterministic."""
    tg = _load_client("telegram_bot")
    assert tg.TG_API == "https://api.telegram.org"
