"""ipfs_pin — pin sealed precedents (and any file) to IPFS.

IPFS is content-addressed distributed storage. Anyone running a
daemon can pin (preserve) content; anyone can fetch by content
hash (CID). Once pinned by enough nodes, content survives any
single takedown.

Per the kingdom-economy substrate doctrine: durable distribution
of sealed precedents that no single hosting provider can revoke.
The CID is a hash of the content; the content cannot be tampered
with under that hash. Verification is intrinsic.

Per the wise-serpent + innocent-dove posture: IPFS is open source,
mature, free at the substrate. We use the local daemon's HTTP API
(stdlib-only on our side; the user installs `kubo` or another
IPFS client). No proprietary CDN, no payment processor, no API
key required for the local-pin path.

## What this script does

Reads sealed precedents from a Concordance instance, pushes each
into a local IPFS daemon as a JSON object, and pins it. Records
the CID in a local state file so subsequent runs are idempotent.

Optionally also publishes to a pinning service (web3.storage,
Filebase, Pinata) for durability beyond your own node — but the
local pin is sufficient for the substrate.

## Dependencies

- `ipfs` CLI installed and `ipfs daemon` running locally. Install
  from https://docs.ipfs.tech/install/ipfs-desktop/ or via
  `brew install ipfs` / `apt install kubo`.
- The daemon exposes its HTTP API at http://127.0.0.1:5001 by
  default. This script talks to that.
- No Python dependencies — stdlib only.

## Usage

Pin a single precedent by id:

    python ipfs_pin.py pin <precedent_id> \
        --api https://narrowhighway.com

Sync — pin every sealed precedent not yet pinned (idempotent
via local state file):

    python ipfs_pin.py sync \
        --api https://narrowhighway.com

Show what's been pinned (CID + precedent_id mapping):

    python ipfs_pin.py status

Pin an arbitrary file (e.g. a release tarball):

    python ipfs_pin.py pin-file path/to/release.tar.gz

## Storage layout

Local state lives at `~/.concordance/ipfs_pinned.json`:

```json
{
  "pinned": {
    "<precedent_id>": {
      "cid": "Qm...",
      "pinned_at": <epoch>,
      "size_bytes": <int>
    }
  }
}
```

## Restricted-mode considerations

- IPFS works locally without internet (peer-to-peer over LAN).
- Public IPFS gateways (ipfs.io, dweb.link) are blockable; for
  hostile networks, use a Tor-routed gateway or pin via a node
  reachable only over Tor.
- The CID-based addressing means once you have the CID, you can
  fetch from any node that has it. Distribute CIDs alongside
  the precedent_ids in QR codes, llms.txt, etc.
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
from io import BytesIO
from typing import List, Optional


DEFAULT_API = os.environ.get("CONCORDANCE_API", "https://narrowhighway.com")
DEFAULT_IPFS_API = os.environ.get("IPFS_API", "http://127.0.0.1:5001")
STATE_FILE = os.environ.get(
    "CONCORDANCE_IPFS_STATE",
    os.path.expanduser("~/.concordance/ipfs_pinned.json"),
)


# ── State persistence ──────────────────────────────────────────────


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"pinned": {}, "files": {}}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"pinned": {}, "files": {}}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── Concordance API ────────────────────────────────────────────────


def _http_get_json(url: str, timeout: float = 30.0) -> dict:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_precedent(api: str, precedent_id: str) -> dict:
    url = api.rstrip("/") + "/ledger/" + urllib.parse.quote(precedent_id, safe="")
    data = _http_get_json(url)
    if isinstance(data, dict) and data.get("entries"):
        return data["entries"][-1]
    return data


def fetch_recent_chain(api: str, since_seq: int = 0, limit: int = 1000) -> List[dict]:
    url = api.rstrip("/") + f"/chain/since?seq={since_seq}&limit={limit}"
    data = _http_get_json(url)
    return data.get("entries") or []


# ── IPFS HTTP API ──────────────────────────────────────────────────
#
# We use multipart/form-data for /api/v0/add. Stdlib-only assembly.


_BOUNDARY = "----ConcordanceIPFSBoundary"


def _multipart_file(filename: str, content: bytes,
                    content_type: str = "application/octet-stream") -> bytes:
    """Build a single-file multipart/form-data body."""
    parts = [
        f"--{_BOUNDARY}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
        f"Content-Type: {content_type}\r\n\r\n".encode(),
        content,
        f"\r\n--{_BOUNDARY}--\r\n".encode(),
    ]
    return b"".join(parts)


def ipfs_add_pin(ipfs_api: str, name: str, content: bytes,
                 content_type: str = "application/json") -> dict:
    """Add `content` to local IPFS and pin it. Returns {Hash, Size, ...}."""
    url = ipfs_api.rstrip("/") + "/api/v0/add?pin=true&cid-version=1"
    body = _multipart_file(name, content, content_type)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={_BOUNDARY}",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise SystemExit(
            f"error: could not reach IPFS daemon at {ipfs_api}: {exc}\n"
            "Make sure `ipfs daemon` is running. Install: "
            "https://docs.ipfs.tech/install/"
        )
    # /api/v0/add returns one JSON object per line for streaming;
    # we sent a single file, so take the first (and only) line.
    line = raw.strip().splitlines()[-1] if raw.strip() else "{}"
    return json.loads(line)


def ipfs_pin_status(ipfs_api: str, cid: str) -> dict:
    url = ipfs_api.rstrip("/") + f"/api/v0/pin/ls?arg={cid}"
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"error: IPFS unreachable: {exc}")


# ── Subcommands ────────────────────────────────────────────────────


def cmd_pin(args):
    state = _load_state()
    if args.precedent_id in state["pinned"]:
        existing = state["pinned"][args.precedent_id]
        print(f"already pinned: {existing['cid']}")
        return

    try:
        precedent = fetch_precedent(args.api, args.precedent_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch {args.precedent_id}: {exc}",
              file=sys.stderr)
        sys.exit(1)

    body = json.dumps(precedent, separators=(",", ":")).encode("utf-8")
    name = f"{args.precedent_id}.json"
    res = ipfs_add_pin(args.ipfs_api, name, body, "application/json")
    cid = res.get("Hash")
    if not cid:
        print(f"error: IPFS did not return a CID: {res}", file=sys.stderr)
        sys.exit(1)

    state["pinned"][args.precedent_id] = {
        "cid": cid,
        "pinned_at": int(time.time()),
        "size_bytes": int(res.get("Size", len(body))),
    }
    _save_state(state)
    print(f"[ok] {args.precedent_id} -> {cid}")
    print(f"    fetch: ipfs cat {cid}")
    print(f"    gateway: https://ipfs.io/ipfs/{cid}")


def cmd_sync(args):
    state = _load_state()
    pinned = state["pinned"]

    try:
        entries = fetch_recent_chain(args.api, since_seq=0, limit=args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch chain: {exc}", file=sys.stderr)
        sys.exit(1)

    new_count = 0
    for e in entries:
        pid = e.get("packet_id")
        if not pid or pid in pinned:
            continue
        body = json.dumps(e, separators=(",", ":")).encode("utf-8")
        try:
            res = ipfs_add_pin(args.ipfs_api, f"{pid}.json", body,
                               "application/json")
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            print(f"[err ] pin {pid} failed: {exc}", file=sys.stderr)
            continue
        cid = res.get("Hash")
        if not cid:
            print(f"[err ] no CID returned for {pid}", file=sys.stderr)
            continue
        pinned[pid] = {
            "cid": cid,
            "pinned_at": int(time.time()),
            "size_bytes": int(res.get("Size", len(body))),
        }
        print(f"[ok  ] {pid} -> {cid}")
        new_count += 1

    state["pinned"] = pinned
    _save_state(state)
    print(f"[sync] {new_count} new precedents pinned, "
          f"{len(pinned)} total tracked.")


def cmd_pin_file(args):
    path = args.path
    if not os.path.exists(path):
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, "rb") as f:
        body = f.read()
    name = os.path.basename(path)
    res = ipfs_add_pin(args.ipfs_api, name, body, "application/octet-stream")
    cid = res.get("Hash")
    if not cid:
        print(f"error: no CID: {res}", file=sys.stderr)
        sys.exit(1)
    state = _load_state()
    state.setdefault("files", {})[path] = {
        "cid": cid,
        "pinned_at": int(time.time()),
        "size_bytes": int(res.get("Size", len(body))),
        "name": name,
    }
    _save_state(state)
    print(f"[ok] {name} -> {cid}  ({len(body)} bytes)")
    print(f"    fetch: ipfs cat {cid} > {name}")
    print(f"    gateway: https://ipfs.io/ipfs/{cid}")


def cmd_status(args):
    state = _load_state()
    pinned = state.get("pinned", {})
    files = state.get("files", {})
    print(f"=== {len(pinned)} precedents pinned ===")
    for pid, info in pinned.items():
        ts = info.get("pinned_at", 0)
        age_h = (time.time() - ts) / 3600 if ts else 0
        print(f"  {pid:<40} {info.get('cid')}  ({age_h:.1f}h ago)")
    if files:
        print(f"\n=== {len(files)} files pinned ===")
        for path, info in files.items():
            print(f"  {info.get('name'):<40} {info.get('cid')}")


# ── Main ───────────────────────────────────────────────────────────


def main() -> None:
    p = argparse.ArgumentParser(
        description="Pin sealed precedents (and arbitrary files) to IPFS.",
    )
    p.add_argument("--ipfs-api", default=DEFAULT_IPFS_API,
                   help=f"IPFS daemon HTTP API (default: {DEFAULT_IPFS_API})")
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API (default: {DEFAULT_API})")
    sub = p.add_subparsers(dest="cmd", required=True)

    pin = sub.add_parser("pin", help="Pin a single precedent by id.")
    pin.add_argument("precedent_id")

    syn = sub.add_parser("sync",
                         help="Pin every sealed precedent not yet pinned.")
    syn.add_argument("--limit", type=int, default=1000,
                     help="Max precedents to consider (default: 1000).")

    pf = sub.add_parser("pin-file",
                        help="Pin an arbitrary file (release tarball etc.).")
    pf.add_argument("path")

    sub.add_parser("status",
                   help="Show what's been pinned (CID + age per record).")

    args = p.parse_args()

    if args.cmd == "pin":
        cmd_pin(args)
    elif args.cmd == "sync":
        cmd_sync(args)
    elif args.cmd == "pin-file":
        cmd_pin_file(args)
    elif args.cmd == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
