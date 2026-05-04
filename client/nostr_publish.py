"""nostr_publish — publish sealed precedents to Nostr relays.

Nostr is a decentralized protocol: each event is a JSON object
signed by a secp256k1 (Schnorr) key, broadcast to one or more
relays. There's no central authority; anyone can run a relay; any
client speaking WebSocket can subscribe.

Per the wise-serpent + innocent-dove posture: Nostr is what social
media would have been if it were built for the kingdom economy.
Ed25519-shaped keys (close cousin to the secp256k1 it actually
uses), federated relays, no central authority, public-by-default
but private chats possible. We publish sealed precedents as Nostr
events; any Nostr client subscribed to them, anywhere in the
world, sees them.

Per "free use, alignment to execute": reading our published
precedents off Nostr is free (anyone with a Nostr client can
subscribe). Publishing requires alignment — we only publish
sealed precedents (those that survived the four gates). Anything
in quarantine or rejected stays out.

## Dependencies

- `pip install pynostr` — Python Nostr client library, MIT-licensed.
  If absent, this script prints clear setup instructions and exits.

## Usage

Generate a key once (store the hex private key somewhere safe;
losing it means losing the ability to publish under that pubkey):

    python nostr_publish.py keygen
    # prints:
    #   private_key (hex):  abcdef0123456789...
    #   public_key  (hex):  fedcba9876543210...
    #   nsec:               nsec1...
    #   npub:               npub1...

Publish a single sealed precedent:

    python nostr_publish.py publish ledger://...id... \
        --nsec nsec1... \
        --api https://narrowhighway.com \
        --relay wss://relay.damus.io \
        --relay wss://nos.lol

Publish all newly-sealed precedents (idempotent — uses local
state file to track what's been published):

    python nostr_publish.py sync \
        --nsec nsec1... \
        --api https://narrowhighway.com \
        --relay wss://relay.damus.io

## Event format we publish

Each sealed precedent becomes a Nostr event:

    {
      "id":         "<sha256 of the canonical event fields>",
      "pubkey":     "<hex secp256k1 public key>",
      "created_at": <unix epoch>,
      "kind":       30700,
      "tags": [
        ["d", "<precedent_id>"],          # parameterized identifier
        ["axis", "<domain axis>"],
        ["serves", "Jesus Christ"],
        ["concordance", "sealed-precedent"],
        ["url", "<host>/ledger/<precedent_id>"]
      ],
      "content":    "<JSON of the precedent>",
      "sig":        "<Schnorr signature>"
    }

`kind: 30700` is a parameterized replaceable event (per NIP-33),
so re-publishing the same precedent_id (`d` tag) updates the
record across relays without creating duplicates.

## Choosing relays

Recommended public relays as of 2025 (subject to change):

- `wss://relay.damus.io` (US, free)
- `wss://nos.lol` (free)
- `wss://relay.snort.social` (free)
- `wss://relay.nostr.band` (search-friendly)

Or run your own relay (e.g. `nostream`, `khatru`) — minimal infra,
fits in a microSD.

## Connection to other doctrine

- **Kingdom-economy substrate** — Nostr matches our principles
  almost exactly: keypair-based identity (no credit score, no KYC),
  federated (no single deplatformer), free read (anyone subscribes),
  open standard (any client). Adding Nostr means our well becomes
  reachable from the existing federated social graph for free.
- **Wise serpents + innocent doves** — public-key crypto is wise
  (verifiable provenance); plain identity tags ("serves Jesus
  Christ") are innocent.
- **Free use, alignment to execute** — only sealed precedents are
  published; the four gates remain the alignment check.

## Restricted-mode considerations

When the network is hostile, public relays may block your IP. Two
fallbacks:
- Run a local Nostr relay that your peers connect to via Tor (use
  Tor's HiddenServicePort to expose the relay)
- Encode published events as wire-format packets and broadcast
  over LoRa mesh — see meshtastic_bridge.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable, List, Optional


DEFAULT_API = os.environ.get("CONCORDANCE_API", "https://narrowhighway.com")
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
]
KIND_SEALED_PRECEDENT = 30700  # parameterized replaceable event
STATE_FILE = os.environ.get(
    "CONCORDANCE_NOSTR_STATE",
    os.path.expanduser("~/.concordance/nostr_published.json"),
)


def _require_pynostr():
    """Import pynostr or exit with setup instructions."""
    try:
        from pynostr.event import Event
        from pynostr.key import PrivateKey
        from pynostr.relay_manager import RelayManager
        return Event, PrivateKey, RelayManager
    except ImportError as exc:
        print(
            "error: pynostr not installed. Install with:\n"
            "  pip install pynostr\n"
            f"  ({exc})\n\n"
            "Alternative: use the `nak` CLI from "
            "https://github.com/fiatjaf/nak — single Go binary, no Python "
            "deps. Build the event JSON shape from this script's docstring "
            "and pipe to `nak event publish`.",
            file=sys.stderr,
        )
        sys.exit(2)


# ── State persistence ──────────────────────────────────────────────


def _load_state() -> dict:
    path = STATE_FILE
    if not os.path.exists(path):
        return {"published": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"published": {}}


def _save_state(state: dict) -> None:
    path = STATE_FILE
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── Concordance API helpers ────────────────────────────────────────


def _http_get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "concordance-nostr/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_precedent(api: str, precedent_id: str) -> dict:
    url = api.rstrip("/") + "/ledger/" + urllib.parse.quote(precedent_id, safe="")
    return _http_get_json(url)


def fetch_recent_precedents(api: str, since_seq: int = 0, limit: int = 100) -> List[dict]:
    url = (api.rstrip("/")
           + f"/chain/since?seq={since_seq}&limit={limit}")
    data = _http_get_json(url)
    return data.get("entries") or []


# ── Event construction ────────────────────────────────────────────


def build_event(precedent: dict, host: str, public_key: str):
    """Build a Nostr event for a sealed precedent. Returns the
    pynostr Event object (unsigned)."""
    Event, _, _ = _require_pynostr()

    pid = precedent.get("packet_id") or precedent.get("id") or ""
    axis = precedent.get("domain") or precedent.get("axis") or "unknown"

    content = json.dumps({
        "precedent_id": pid,
        "axis": axis,
        "overall": precedent.get("overall"),
        "summary": precedent.get("summary") or precedent.get("top_reasons", []),
        "sealed_at": precedent.get("timestamp_iso") or precedent.get("sealed_at"),
        "entry_hash": precedent.get("entry_hash"),
    }, separators=(",", ":"))

    tags = [
        ["d", pid],
        ["axis", axis],
        ["serves", "Jesus Christ"],
        ["concordance", "sealed-precedent"],
        ["url", f"{host.rstrip('/')}/ledger/{pid}"],
    ]

    e = Event(
        content=content,
        pubkey=public_key,
        kind=KIND_SEALED_PRECEDENT,
        tags=tags,
        created_at=int(time.time()),
    )
    return e


def publish_event(event, relays: List[str], private_key) -> List[str]:
    """Sign the event and publish to relays. Returns list of relay URLs
    that accepted (best-effort; pynostr's API doesn't surface every
    relay's response cleanly, so this is a best-effort log)."""
    _, _, RelayManager = _require_pynostr()

    event.sign(private_key.hex())

    rm = RelayManager(timeout=6.0)
    for r in relays:
        rm.add_relay(r)
    rm.publish_event(event)
    rm.run_sync()
    # Drain any pending messages.
    while rm.message_pool.has_ok_notices():
        ok = rm.message_pool.get_ok_notice()
        # ok is (relay_url, event_id, accepted, message)
        # not all relays send OK; we just log.
        print(f"[relay] {ok}")
    rm.close_all_relay_connections()
    return relays


# ── Subcommands ────────────────────────────────────────────────────


def cmd_keygen(args):
    _, PrivateKey, _ = _require_pynostr()
    pk = PrivateKey()
    print("private_key (hex): ", pk.hex())
    print("public_key  (hex): ", pk.public_key.hex())
    print("nsec:              ", pk.bech32())
    print("npub:              ", pk.public_key.bech32())
    print()
    print("Save the private key (or nsec) somewhere safe. Losing it")
    print("means losing the ability to publish under this pubkey.")


def _load_privkey(args):
    Event, PrivateKey, _ = _require_pynostr()
    if args.nsec:
        return PrivateKey.from_nsec(args.nsec)
    if args.hex:
        return PrivateKey.from_hex(args.hex)
    print("error: provide --nsec or --hex", file=sys.stderr)
    sys.exit(2)


def cmd_publish(args):
    privkey = _load_privkey(args)
    pubkey_hex = privkey.public_key.hex()

    try:
        precedent = fetch_precedent(args.api, args.precedent_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch {args.precedent_id}: {exc}",
              file=sys.stderr)
        sys.exit(1)

    if not precedent or not precedent.get("entries"):
        # /ledger/{id} returns {entries: [...]}; pick the most recent.
        if isinstance(precedent, dict) and precedent.get("entries"):
            precedent = precedent["entries"][-1]
        else:
            print(f"error: no precedent found for {args.precedent_id}",
                  file=sys.stderr)
            sys.exit(1)
    elif precedent.get("entries"):
        precedent = precedent["entries"][-1]

    event = build_event(precedent, args.api, pubkey_hex)
    relays = args.relay or DEFAULT_RELAYS
    print(f"[publish] relays: {relays}")
    publish_event(event, relays, privkey)
    print(f"[ok] published precedent {args.precedent_id} as event {event.id}")

    state = _load_state()
    state["published"][args.precedent_id] = {
        "event_id": event.id,
        "published_at": int(time.time()),
        "relays": relays,
    }
    _save_state(state)


def cmd_sync(args):
    privkey = _load_privkey(args)
    pubkey_hex = privkey.public_key.hex()
    state = _load_state()
    published = state.get("published", {})

    try:
        entries = fetch_recent_precedents(args.api, since_seq=0,
                                          limit=args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch chain: {exc}", file=sys.stderr)
        sys.exit(1)

    relays = args.relay or DEFAULT_RELAYS
    new_count = 0
    for e in entries:
        pid = e.get("packet_id")
        if not pid or pid in published:
            continue
        event = build_event(e, args.api, pubkey_hex)
        try:
            publish_event(event, relays, privkey)
        except Exception as exc:  # noqa: BLE001 — best effort
            print(f"[err ] publish {pid} failed: {exc}", file=sys.stderr)
            continue
        published[pid] = {
            "event_id": event.id,
            "published_at": int(time.time()),
            "relays": relays,
        }
        print(f"[ok  ] {pid} -> {event.id}")
        new_count += 1

    state["published"] = published
    _save_state(state)
    print(f"[sync] {new_count} new precedents published, "
          f"{len(published)} total tracked.")


# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Publish sealed precedents to Nostr relays.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("keygen", help="Generate a new secp256k1 keypair.")

    pub = sub.add_parser("publish", help="Publish one precedent by id.")
    pub.add_argument("precedent_id", help="Precedent id from /ledger.")
    pub.add_argument("--nsec", help="Private key in bech32 nsec form.")
    pub.add_argument("--hex", help="Private key in hex form.")
    pub.add_argument("--api", default=DEFAULT_API,
                     help=f"Concordance API (default: {DEFAULT_API}).")
    pub.add_argument("--relay", action="append", default=None,
                     help="Relay URL (wss://...). May be repeated. "
                          f"Defaults: {', '.join(DEFAULT_RELAYS)}")

    syn = sub.add_parser("sync",
                         help="Publish all newly-sealed precedents not yet "
                              "in the local state file.")
    syn.add_argument("--nsec")
    syn.add_argument("--hex")
    syn.add_argument("--api", default=DEFAULT_API)
    syn.add_argument("--relay", action="append", default=None)
    syn.add_argument("--limit", type=int, default=100,
                     help="Max precedents to consider per sync (default: 100).")

    args = p.parse_args()

    if args.cmd == "keygen":
        cmd_keygen(args)
    elif args.cmd == "publish":
        cmd_publish(args)
    elif args.cmd == "sync":
        cmd_sync(args)


if __name__ == "__main__":
    main()
