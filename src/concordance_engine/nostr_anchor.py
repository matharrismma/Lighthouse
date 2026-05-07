"""Nostr permanent anchor for sealed WitnessRecords.

Publishes a signed Nostr event (NIP-01) to configured relays whenever a
verdict is sealed.  The event ID becomes the `permanent_ref` in the
WitnessRecord — an independently-verifiable, censorship-resistant
content-address that no single party controls.

Design decisions:
  * BIP-340 Schnorr signing in pure Python — correct per spec, zero
    extra dependencies, works on LoRa target hardware.
  * Event ID computed synchronously so the caller gets a stable anchor
    ref immediately; the relay broadcast happens fire-and-forget.
  * Graceful degradation: if broadcast fails the seal still succeeds;
    the event_id is still valid (any relay can re-accept it later).

Key storage
-----------
  Default:  ~/.concordance/nostr_key.json  ({"seckey_hex": "..."})
  Override: CONCORDANCE_NOSTR_KEY env var  (raw 64-char hex)

Relays
------
  Default:  wss://relay.damus.io, wss://nos.lol,
            wss://nostr-pub.wellorder.net, wss://relay.nostr.info
  Override: CONCORDANCE_NOSTR_RELAYS  (comma-separated wss:// list)
  Add self: run nostr-rs-relay on the same host; include in the list.

Event format
------------
  Kind 30078 (NIP-78 application-specific data):
    d-tag:   "concordance:verdict"
    content: JSON payload with verdict, domain, hash, packet_id
    #t tags: ["concordance", "verdict", <verdict_lower>]
    #h tag:  content_hash (the payload the WitnessRecord hashes to)

  The event ID (SHA-256 of the serialized event) is the permanent ref.
  Anyone holding the event ID can query any Nostr relay to independently
  verify the verdict existed at the stated timestamp.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("concordance.nostr")

# ── secp256k1 curve parameters (BIP-340) ──────────────────────────────

_P  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
_N  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
_Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
_Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8

_Point = Optional[Tuple[int, int]]


def _point_add(P1: _Point, P2: _Point) -> _Point:
    if P1 is None:
        return P2
    if P2 is None:
        return P1
    x1, y1 = P1
    x2, y2 = P2
    if x1 == x2:
        if y1 != y2:
            return None           # point at infinity
        # point doubling
        m = (3 * x1 * x1 * pow(2 * y1, _P - 2, _P)) % _P
    else:
        m = ((y2 - y1) * pow(x2 - x1, _P - 2, _P)) % _P
    x3 = (m * m - x1 - x2) % _P
    y3 = (m * (x1 - x3) - y1) % _P
    return (x3, y3)


def _scalar_mul(k: int, point: Tuple[int, int]) -> _Point:
    result: _Point = None
    addend: _Point = point
    while k:
        if k & 1:
            result = _point_add(result, addend)
        addend = _point_add(addend, addend)
        k >>= 1
    return result


def _tagged_hash(tag: str, *parts: bytes) -> bytes:
    """BIP-340 tagged hash: SHA256(SHA256(tag) || SHA256(tag) || msg)."""
    t = hashlib.sha256(tag.encode()).digest()
    return hashlib.sha256(t + t + b"".join(parts)).digest()


def _schnorr_sign(seckey_int: int, msg32: bytes, aux: bytes) -> bytes:
    """BIP-340 Schnorr signature. Returns 64 bytes (R.x || s)."""
    assert len(msg32) == 32
    assert len(aux) == 32

    # Normalise secret key so the public key has even y
    P_pt = _scalar_mul(seckey_int, (_Gx, _Gy))
    assert P_pt is not None
    if P_pt[1] & 1:                        # y is odd → negate
        seckey_int = _N - seckey_int
    P_x = P_pt[0].to_bytes(32, "big")

    # Deterministic nonce (BIP-340 §Signing)
    t = (seckey_int ^ int.from_bytes(_tagged_hash("BIP0340/aux", aux), "big"))
    rand = _tagged_hash("BIP0340/nonce", t.to_bytes(32, "big"), P_x, msg32)
    k = int.from_bytes(rand, "big") % _N
    assert k != 0, "nonce is zero — regenerate aux"

    R_pt = _scalar_mul(k, (_Gx, _Gy))
    assert R_pt is not None
    if R_pt[1] & 1:                        # R.y is odd → negate k
        k = _N - k
    R_x = R_pt[0].to_bytes(32, "big")

    e = int.from_bytes(
        _tagged_hash("BIP0340/challenge", R_x, P_x, msg32), "big"
    ) % _N
    s = (k + e * seckey_int) % _N
    return R_x + s.to_bytes(32, "big")


def _pubkey_from_seckey(seckey_int: int) -> bytes:
    """32-byte x-only public key (even-y normalised)."""
    P_pt = _scalar_mul(seckey_int, (_Gx, _Gy))
    assert P_pt is not None
    if P_pt[1] & 1:
        seckey_int = _N - seckey_int
        P_pt = _scalar_mul(seckey_int, (_Gx, _Gy))
        assert P_pt is not None
    return P_pt[0].to_bytes(32, "big")


# ── Key management ─────────────────────────────────────────────────────

def _key_path() -> Path:
    if "CONCORDANCE_DATA_DIR" in os.environ:
        return Path(os.environ["CONCORDANCE_DATA_DIR"]) / "nostr_key.json"
    return Path.home() / ".concordance" / "nostr_key.json"


def _load_or_create_key() -> int:
    """Return the node's Nostr private key as an integer.

    Priority: CONCORDANCE_NOSTR_KEY env var → persisted key file →
    freshly generated key (saved for reuse).
    """
    env = os.environ.get("CONCORDANCE_NOSTR_KEY", "").strip()
    if env:
        return int(env, 16)

    kpath = _key_path()
    if kpath.exists():
        try:
            data = json.loads(kpath.read_text())
            return int(data["seckey_hex"], 16)
        except Exception:
            pass

    # Generate fresh key
    seckey = int.from_bytes(secrets.token_bytes(32), "big") % _N
    while seckey == 0:
        seckey = int.from_bytes(secrets.token_bytes(32), "big") % _N

    kpath.parent.mkdir(parents=True, exist_ok=True)
    pubkey = _pubkey_from_seckey(seckey).hex()
    kpath.write_text(json.dumps({
        "seckey_hex": hex(seckey)[2:].zfill(64),
        "pubkey_hex": pubkey,
        "note": "Concordance Engine Nostr anchor key. Keep private.",
    }, indent=2))
    _log.info("nostr: generated new keypair pubkey=%s", pubkey[:16])
    return seckey


# ── Event construction ─────────────────────────────────────────────────

_DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://nostr-pub.wellorder.net",
    "wss://relay.nostr.info",
]

KIND_APP_DATA = 30078   # NIP-78 application-specific data


def _relay_list() -> List[str]:
    env = os.environ.get("CONCORDANCE_NOSTR_RELAYS", "")
    if env.strip():
        return [r.strip() for r in env.split(",") if r.strip()]
    return list(_DEFAULT_RELAYS)


def _build_event(
    seckey_int: int,
    verdict: str,
    domain: str,
    content_hash: str,
    packet_id: Optional[str],
    now: int,
) -> Dict[str, Any]:
    """Build and sign a NIP-78 kind-30078 Nostr event."""
    pubkey_hex = _pubkey_from_seckey(seckey_int).hex()

    payload = {
        "verdict": verdict,
        "domain": domain,
        "hash": content_hash,
    }
    if packet_id:
        payload["pkt"] = packet_id

    tags = [
        ["d", "concordance:verdict"],
        ["t", "concordance"],
        ["t", "verdict"],
        ["t", verdict.lower()],
        ["h", content_hash],
    ]

    event: Dict[str, Any] = {
        "pubkey":     pubkey_hex,
        "created_at": now,
        "kind":       KIND_APP_DATA,
        "tags":       tags,
        "content":    json.dumps(payload, separators=(",", ":")),
    }

    # NIP-01: event ID = SHA-256 of the serialization
    serial = json.dumps(
        [0, event["pubkey"], event["created_at"],
         event["kind"], event["tags"], event["content"]],
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    event_id = hashlib.sha256(serial).hexdigest()
    event["id"] = event_id

    # BIP-340 Schnorr signature over the event ID bytes
    msg32 = bytes.fromhex(event_id)
    sig = _schnorr_sign(seckey_int, msg32, secrets.token_bytes(32))
    event["sig"] = sig.hex()

    return event


# ── WebSocket broadcast ────────────────────────────────────────────────

async def _send_to_relay(relay_url: str, event: Dict[str, Any], timeout: float = 6.0) -> bool:
    """Send a signed event to one relay. Returns True on success."""
    try:
        import websockets  # type: ignore
        msg = json.dumps(["EVENT", event])
        async with websockets.connect(
            relay_url,
            open_timeout=timeout,
            close_timeout=2.0,
        ) as ws:
            await ws.send(msg)
            # Wait for OK or NOTICE; don't block indefinitely
            try:
                response = await asyncio.wait_for(ws.recv(), timeout=timeout)
                parsed = json.loads(response)
                if parsed[0] == "OK" and parsed[2] is True:
                    _log.debug("nostr: %s accepted %s", relay_url, event["id"][:12])
                    return True
                _log.debug("nostr: %s response: %s", relay_url, response[:120])
                return True   # still published even if relay says duplicate
            except asyncio.TimeoutError:
                return True   # relay accepted but didn't respond in time
    except Exception as exc:
        _log.debug("nostr: %s failed: %s", relay_url, exc)
        return False


async def _broadcast(event: Dict[str, Any]) -> None:
    """Broadcast an event to all configured relays concurrently."""
    relays = _relay_list()
    tasks = [_send_to_relay(r, event) for r in relays]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    ok = sum(1 for r in results if r is True)
    _log.info("nostr: broadcast %s → %d/%d relays accepted", event["id"][:16], ok, len(relays))


def _broadcast_sync(event: Dict[str, Any]) -> None:
    """Run the async broadcast in a fresh event loop (called from a thread)."""
    try:
        asyncio.run(_broadcast(event))
    except Exception as exc:
        _log.warning("nostr: broadcast thread error: %s", exc)


# ── Public API ─────────────────────────────────────────────────────────

# Module-level key (loaded once, reused)
_SECKEY: Optional[int] = None


def _get_seckey() -> int:
    global _SECKEY
    if _SECKEY is None:
        _SECKEY = _load_or_create_key()
    return _SECKEY


def anchor_verdict(
    verdict: str,
    domain: str,
    content_hash: str,
    packet_id: Optional[str] = None,
    broadcast: bool = True,
    executor=None,
) -> str:
    """Sign and optionally broadcast a verdict event.  Always returns
    the event_id (deterministic, computed synchronously so the caller
    can store it immediately without waiting for relay confirmation).

    Parameters
    ----------
    verdict      : "PASS" | "REJECT" | "QUARANTINE"
    domain       : domain string ("theology", "chemistry", …)
    content_hash : WitnessRecord.to_dict()["content_hash"]
    packet_id    : optional stable packet identifier
    broadcast    : fire-and-forget relay broadcast (default True)
    executor     : ThreadPoolExecutor to submit broadcast work to

    Returns
    -------
    Nostr event ID (64-char hex SHA-256).  Use as permanent_ref.
    """
    seckey = _get_seckey()
    now = int(time.time())
    event = _build_event(seckey, verdict, domain, content_hash, packet_id, now)
    event_id: str = event["id"]

    if broadcast:
        try:
            if executor is not None:
                executor.submit(_broadcast_sync, event)
            else:
                import threading
                t = threading.Thread(target=_broadcast_sync, args=(event,), daemon=True)
                t.start()
        except Exception as exc:
            _log.warning("nostr: could not schedule broadcast: %s", exc)

    return event_id


def nostr_pubkey() -> str:
    """Return the hex x-only public key for this node's Nostr identity."""
    return _pubkey_from_seckey(_get_seckey()).hex()
