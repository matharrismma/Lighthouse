"""meshtastic_bridge — Concordance ↔ Meshtastic mesh radio bridge.

Listens to a Meshtastic radio over USB serial; decodes inbound
binary packets that look like Concordance wire seeds; POSTs them
to the local engine's `/capture`. Optionally subscribes to local
seal events and broadcasts compact-encoded outbound packets.

Per project_lora_mesh_substrate.md — this is the wilderness layer.
When the world's networks are hostile or absent, sub-GHz license-
free spectrum still works. A $20-30 LoRa node + this bridge
script + a microSD with the engine = a community can keep its
journal, witness one another, and federate sealed precedents
without a single piece of conventional infrastructure.

## Dependencies

- The official `meshtastic` Python package (Meshtastic, Inc.):
  `pip install meshtastic`. It's open source (GPL-3.0). Required
  to talk to the radio over USB serial.
- `pubsub` is auto-installed alongside; we use its event bus.
- The Concordance engine (this repo) — for `wire.py`. Imported
  via `from concordance_engine.wire import SeedWire, ...`.

If `meshtastic` is not installed, the script prints clear
instructions and exits — no implicit dependency, no silent
failure.

## Usage

    # Receive only — listen for inbound wire packets, post to /capture
    python meshtastic_bridge.py --port /dev/ttyUSB0 \
        --api http://localhost:8000

    # Send a seed onto the mesh from an existing journal entry
    python meshtastic_bridge.py --port /dev/ttyUSB0 --send j-abc123

    # Daemon mode — listen for incoming AND broadcast on every
    # local seal event (poll the engine's /ledger for new entries)
    python meshtastic_bridge.py --port /dev/ttyUSB0 --bridge

## Wire packet identification

Concordance wire packets begin with:
    0x01  <- WIRE_VERSION
    0x01  <- WIRE_TYPE_SEED  (or 0x02..0x04 for other types)

Meshtastic data packets carry an arbitrary byte payload. We
distinguish Concordance packets by checking the first two bytes
match a known (WIRE_VERSION, WIRE_TYPE_*) pair. Non-Concordance
mesh traffic (other apps, plain text messages) is logged and
ignored.

## Per the doctrine

- Reads are free. Anyone listening on the mesh can decode public
  Concordance packets — the well is free water.
- Writes (broadcasts) are alignment-acknowledged. The bridge
  refuses to broadcast a seed without `identity_acknowledged`
  set on the source entry.
- The four gates downstream catch misalignment by content, not by
  trusting the source.
- This script is read-then-act, never auto-act. Every inbound
  wire packet gets POST'd to `/capture`, which records it tagged
  as `source:lora_mesh` and runs whatever local categorization /
  calibration is configured. Sealing remains a separate operator
  decision.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional, Set

# Defensive import of the wire format. The bridge is in client/
# but ships alongside the engine, so this should always work in
# a normal install.
try:
    # When the package is installed:
    from concordance_engine.wire import (
        SeedWire, WIRE_VERSION, WIRE_TYPE_SEED, wire_to_capture_payload,
    )
except ImportError as exc:  # pragma: no cover — install-time guidance
    print(
        "error: could not import concordance_engine.wire — install the "
        "engine first (pip install concordance-engine) or run this "
        f"script from the repo root.\n  {exc}",
        file=sys.stderr,
    )
    sys.exit(2)


DEFAULT_API = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
DEFAULT_PORT = os.environ.get("MESHTASTIC_PORT", None)


# ── Concordance API helpers ─────────────────────────────────────────


def post_capture(api: str, payload: dict, timeout: float = 30.0) -> dict:
    """POST payload to /capture. Returns parsed JSON response."""
    url = api.rstrip("/") + "/capture"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_journal_entry(api: str, seed_id: str, timeout: float = 30.0) -> dict:
    """Fetch a single journal entry by id."""
    url = api.rstrip("/") + "/journal/" + urllib.parse.quote(seed_id, safe="")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Wire packet detection ───────────────────────────────────────────


def looks_like_wire(payload: bytes) -> bool:
    """Check if a byte payload begins with a Concordance wire envelope."""
    if len(payload) < 2:
        return False
    return payload[0] == WIRE_VERSION and payload[1] in (
        WIRE_TYPE_SEED,  # only seeds for now; witness/precedent come later
    )


# ── Inbound: mesh → /capture ────────────────────────────────────────


def handle_inbound(api: str, payload: bytes, source_node: Optional[str]) -> None:
    """Decode an inbound wire packet and POST to /capture."""
    try:
        seed = SeedWire.from_bytes(payload)
    except ValueError as exc:
        print(f"[skip] not a valid wire seed: {exc}", file=sys.stderr)
        return

    capture = wire_to_capture_payload(seed)
    if source_node:
        capture["source_meta"]["mesh_origin_node"] = source_node

    try:
        result = post_capture(api, capture)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[err ] /capture failed: {exc}", file=sys.stderr)
        return

    seed_id = (result.get("entry") or {}).get("id", "?")
    text_preview = (seed.text or "").replace("\n", " ")[:60]
    print(f"[mesh→engine] {source_node or '?'} planted {seed_id}: {text_preview!r}")


# ── Outbound: journal entry → mesh ──────────────────────────────────


def broadcast_seed(iface, api: str, seed_id: str) -> None:
    """Fetch a journal entry and broadcast it as a wire packet on the mesh."""
    try:
        entry = fetch_journal_entry(api, seed_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[err ] could not fetch {seed_id}: {exc}", file=sys.stderr)
        return

    # Refuse to broadcast unless identity was acknowledged on the
    # source entry. The well is open; what you broadcast must have
    # passed the doorway.
    user_tags = entry.get("user_tags") or []
    if "identity_acknowledged" not in user_tags:
        print(
            f"[deny] {seed_id} was not identity_acknowledged at write-time; "
            "refusing to broadcast.",
            file=sys.stderr,
        )
        return

    # Build the SeedWire from the fetched entry.
    cat = entry.get("categorization") or {}
    wire = SeedWire(
        text=entry.get("text", ""),
        anchors=list(cat.get("detected_anchors") or []),
        scope=cat.get("detected_scope") or "personal",
        action_shape=(cat.get("detected_action_shapes") or [""])[0] or "",
        source="lora_mesh",
        author_id=entry.get("author_id", "") or entry.get("id", ""),
        epoch=int(entry.get("written_at") or 0),
    )
    payload = wire.to_bytes()
    if len(payload) > 230:
        # SF7 packet limit. SF12 is even smaller. v1 doesn't fragment;
        # we surface the failure and let the operator decide.
        print(
            f"[deny] {seed_id} encoded to {len(payload)} bytes "
            "(LoRa SF7 limit ~230). Shorten the seed or wait for "
            "fragmentation support.",
            file=sys.stderr,
        )
        return

    # Send via Meshtastic. Use the data port number 256 (PRIVATE_APP)
    # so we don't collide with text-message traffic on the mesh.
    iface.sendData(
        payload,
        portNum=256,                     # PRIVATE_APP
        wantAck=False,                    # broadcast — no ack expected
        wantResponse=False,
    )
    print(f"[engine→mesh] broadcast {seed_id} as {len(payload)}B wire packet")


# ── Bridge mode (daemon) ────────────────────────────────────────────


def run_bridge(iface, api: str, poll_interval: float = 30.0) -> None:
    """Daemon: listen for inbound mesh wire packets AND poll the local
    journal for newly-acknowledged seeds, broadcasting them onto the mesh."""
    print(f"[bridge] api: {api}")
    print(f"[bridge] poll interval: {poll_interval}s")
    seen: Set[str] = set()

    # Prime `seen` with whatever's in the journal at startup so we
    # don't broadcast historical seeds.
    try:
        recent = json.loads(urllib.request.urlopen(
            api.rstrip("/") + "/journal/recent?limit=50", timeout=10
        ).read())
        for e in recent.get("entries") or []:
            seen.add(e.get("id", ""))
        print(f"[bridge] seen {len(seen)} historical seeds at startup; "
              "only newer ones will be broadcast")
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[warn] could not prime seen-set: {exc}", file=sys.stderr)

    last_poll = time.time()
    try:
        while True:
            now = time.time()
            if now - last_poll >= poll_interval:
                last_poll = now
                try:
                    recent = json.loads(urllib.request.urlopen(
                        api.rstrip("/") + "/journal/recent?limit=20",
                        timeout=10,
                    ).read())
                    for e in recent.get("entries") or []:
                        sid = e.get("id", "")
                        if not sid or sid in seen:
                            continue
                        seen.add(sid)
                        # Only broadcast acknowledged seeds.
                        if "identity_acknowledged" in (e.get("user_tags") or []):
                            broadcast_seed(iface, api, sid)
                        else:
                            print(f"[bridge] {sid} not acknowledged; skip mesh broadcast")
                except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                    print(f"[warn] poll failed: {exc}", file=sys.stderr)
            # Light sleep — meshtastic listener runs on its own thread
            # via pubsub callbacks set up in main().
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[bridge] stopped", file=sys.stderr)


# ── Main ────────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Bridge between a Meshtastic LoRa radio and a "
                    "Concordance engine instance.",
    )
    p.add_argument("--port", default=DEFAULT_PORT,
                   help="Serial port the Meshtastic radio is on "
                        "(e.g. /dev/ttyUSB0, COM3). Or env MESHTASTIC_PORT. "
                        "If omitted, meshtastic auto-detects.")
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API base URL (default: {DEFAULT_API})")
    p.add_argument("--send", metavar="SEED_ID",
                   help="Broadcast a single journal entry onto the mesh, "
                        "then exit.")
    p.add_argument("--bridge", action="store_true",
                   help="Run as a daemon: listen for inbound + broadcast "
                        "newly-acknowledged local seeds.")
    p.add_argument("--poll-interval", type=float, default=30.0,
                   help="Seconds between local journal polls in bridge mode "
                        "(default: 30).")
    args = p.parse_args()

    # Defensive import of meshtastic — keep this script useful for
    # offline testing of the wire format even when the radio package
    # isn't installed. Only --send and --bridge actually need it.
    needs_radio = bool(args.send) or args.bridge or not args.send
    if needs_radio:
        try:
            import meshtastic.serial_interface as _mt_serial
            from pubsub import pub as _pubsub
        except ImportError as exc:
            print(
                "error: meshtastic package not installed. Install it with:\n"
                "  pip install meshtastic\n"
                f"  ({exc})",
                file=sys.stderr,
            )
            sys.exit(2)

        # Open the radio.
        try:
            iface = _mt_serial.SerialInterface(devPath=args.port)
        except Exception as exc:  # noqa: BLE001 — many possible serial errors
            print(f"error: could not open Meshtastic radio: {exc}",
                  file=sys.stderr)
            sys.exit(1)

        node_info = iface.getMyNodeInfo() or {}
        node_id = node_info.get("user", {}).get("id", "?")
        print(f"[radio] connected as {node_id}")

        # Install the inbound listener. Meshtastic emits "meshtastic.receive"
        # for every received packet; we filter to our portNum.
        def on_receive(packet, interface):  # noqa: ARG001 — pubsub callback
            decoded = packet.get("decoded") or {}
            if decoded.get("portnum") != "PRIVATE_APP" \
               and decoded.get("portnum") != 256:
                return
            payload = decoded.get("payload")
            if not payload or not looks_like_wire(payload):
                return
            from_id = packet.get("fromId") or packet.get("from")
            handle_inbound(args.api, bytes(payload), str(from_id) if from_id else None)

        _pubsub.subscribe(on_receive, "meshtastic.receive")

        # Dispatch.
        if args.send:
            broadcast_seed(iface, args.api, args.send)
            # Give the radio a moment to actually transmit before we close.
            time.sleep(2.0)
            iface.close()
            return

        if args.bridge:
            try:
                run_bridge(iface, args.api, args.poll_interval)
            finally:
                iface.close()
            return

        # Default: receive-only mode. Sit and listen.
        print("[radio] receive-only mode. Ctrl-C to stop.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            print("\n[radio] stopped", file=sys.stderr)
        finally:
            iface.close()
        return


if __name__ == "__main__":
    main()
