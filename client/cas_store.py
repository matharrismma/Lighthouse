"""cas_store — manage the in-house content-addressable store (CAS).

The CAS is the in-house replacement for Arweave. Every sealed receipt is
stored locally by its SHA-256 content hash. The hash is both the address
and the integrity proof — no external service, no tokens, no pinning.

Works offline. Replicates over the existing Concordance federation
endpoints. Runs on microSD, LoRa mesh node, or a full server.

Usage:
    python cas_store.py store <precedent_id>    # pull from API, store locally
    python cas_store.py sync [--limit 500]      # store all unsealed precedents
    python cas_store.py store-file path/to/file # store arbitrary JSON
    python cas_store.py fetch <content_hash>    # retrieve and print record
    python cas_store.py verify <content_hash>   # re-hash and confirm integrity
    python cas_store.py push <content_hash>     # push to a remote node's /cas
    python cas_store.py status                  # summary stats

Environment:
    CONCORDANCE_CAS_DIR  — local CAS storage directory (default: data/cas/)
    CONCORDANCE_API      — Concordance API base URL
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional

# ── repo path bootstrap ─────────────────────────────────────────────────
_here = Path(__file__).parent
_repo = _here.parent
sys.path.insert(0, str(_repo / "src"))

from concordance_engine.cas import (
    store, fetch, exists, verify, list_hashes, stats, content_hash_of,
)

DEFAULT_API = os.environ.get("CONCORDANCE_API", "https://narrowhighway.com")


# ── Remote helpers ──────────────────────────────────────────────────────

def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _post_json(url: str, body: dict, api_key: Optional[str] = None) -> tuple:
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def fetch_precedent(api: str, precedent_id: str) -> dict:
    url = api.rstrip("/") + "/ledger/" + urllib.parse.quote(precedent_id, safe="")
    data = _get_json(url)
    if isinstance(data, dict) and data.get("entries"):
        return data["entries"][-1]
    return data


def fetch_chain(api: str, since_seq: int = 0, limit: int = 1000) -> List[dict]:
    url = api.rstrip("/") + f"/chain/since?seq={since_seq}&limit={limit}"
    data = _get_json(url)
    return data.get("entries") or []


# ── CLI subcommands ─────────────────────────────────────────────────────

def cmd_store(args) -> None:
    """Pull a single precedent from the API and store it in the local CAS."""
    try:
        record = fetch_precedent(args.api, args.precedent_id)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch '{args.precedent_id}': {exc}", file=sys.stderr)
        sys.exit(1)

    h = store(record)
    print(f"[ok] {args.precedent_id}")
    print(f"     hash: {h}")
    print(f"     fetch: GET /cas/{h}")


def cmd_sync(args) -> None:
    """Store every unsealed precedent from the chain into the local CAS."""
    try:
        entries = fetch_chain(args.api, since_seq=0, limit=args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch chain: {exc}", file=sys.stderr)
        sys.exit(1)

    new_count = 0
    for e in entries:
        pid = e.get("packet_id", "")
        h = content_hash_of(e)
        if exists(h) and not args.force:
            continue
        store(e)
        print(f"[ok  ] {pid or '?':<40}  {h[:16]}...")
        new_count += 1

    total = len(list_hashes())
    print(f"\n{new_count} new records stored, {total} total in CAS.")


def cmd_store_file(args) -> None:
    """Store an arbitrary JSON file in the local CAS."""
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON in {path}: {exc}", file=sys.stderr)
        sys.exit(1)

    h = store(record)
    print(f"[ok] {path.name}  →  {h}")


def cmd_fetch(args) -> None:
    """Retrieve a record by content hash and print it."""
    record = fetch(args.content_hash)
    if record is None:
        print(f"error: not found: {args.content_hash}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(record, indent=2))


def cmd_verify(args) -> None:
    """Re-hash the stored record and confirm it matches."""
    ok, detail = verify(args.content_hash)
    marker = "[ok]" if ok else "[!!]"
    print(f"{marker} {args.content_hash[:32]}...  {detail}")
    if not ok:
        sys.exit(1)


def cmd_push(args) -> None:
    """Push a local CAS record to a remote Concordance node's /cas endpoint."""
    record = fetch(args.content_hash)
    if record is None:
        print(f"error: not found locally: {args.content_hash}", file=sys.stderr)
        sys.exit(1)

    url = args.remote.rstrip("/") + "/cas"
    api_key = os.environ.get("CONCORDANCE_API_KEY", "")
    status, resp = _post_json(url, record, api_key=api_key or None)
    if status in (200, 201):
        remote_hash = resp.get("content_hash", "?")
        print(f"[ok] pushed → {remote_hash}")
        if remote_hash != args.content_hash:
            print(f"[!!] warning: remote hash {remote_hash} != local {args.content_hash}",
                  file=sys.stderr)
    else:
        print(f"error: push failed ({status}): {resp}", file=sys.stderr)
        sys.exit(1)


def cmd_status(args) -> None:
    """Print CAS summary statistics."""
    s = stats()
    hashes = list_hashes()
    print(f"CAS location : {s['base_dir']}")
    print(f"Records      : {s['count']}")
    print(f"Total size   : {s['total_bytes'] / 1024:.1f} KB")
    if args.verbose and hashes:
        print("\nAll hashes:")
        for h in hashes:
            print(f"  {h}")


# ── Main ────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Manage the Concordance in-house content-addressable store (CAS).",
    )
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API base URL (default: {DEFAULT_API})")
    sub = p.add_subparsers(dest="cmd", required=True)

    st = sub.add_parser("store", help="Pull a precedent from the API and store it locally.")
    st.add_argument("precedent_id")

    sy = sub.add_parser("sync", help="Store all chain entries not yet in local CAS.")
    sy.add_argument("--limit", type=int, default=500)
    sy.add_argument("--force", action="store_true", help="Re-store already-present entries")

    sf = sub.add_parser("store-file", help="Store an arbitrary JSON file.")
    sf.add_argument("path")

    fe = sub.add_parser("fetch", help="Retrieve a record by content hash.")
    fe.add_argument("content_hash")

    ve = sub.add_parser("verify", help="Re-hash and confirm integrity of a stored record.")
    ve.add_argument("content_hash")

    pu = sub.add_parser("push", help="Push a local record to a remote node.")
    pu.add_argument("content_hash")
    pu.add_argument("--remote", default=DEFAULT_API,
                    help="Remote Concordance API URL")

    ss = sub.add_parser("status", help="Print CAS summary statistics.")
    ss.add_argument("-v", "--verbose", action="store_true",
                    help="List all stored hashes")

    args = p.parse_args()
    dispatch = {
        "store": cmd_store, "sync": cmd_sync, "store-file": cmd_store_file,
        "fetch": cmd_fetch, "verify": cmd_verify,
        "push": cmd_push, "status": cmd_status,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
