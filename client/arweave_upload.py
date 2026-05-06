"""arweave_upload — upload sealed receipts to Arweave for permanent storage.

Arweave is pay-once permanent storage. Once confirmed (~30 min, 20 blocks),
data is stored for 200+ years via Arweave's endowment model. No active
pinning required — upload once, accessible forever by TX ID.

The TX ID serves as the canonical permanent reference embedded in
WitnessRecord.arweave_txid. It is content-addressed: SHA-256 of the
RSA signature, so the ID is stable and tamper-evident.

## Wallet

Arweave uses RSA-4096 JWK wallets. Get one at https://arweave.app/ (free).
Point to it via ARWEAVE_WALLET_PATH or ARWEAVE_WALLET_JSON (inline JSON).

AR tokens are needed to pay the storage endowment. For small receipts
(< 10KB each), cost is negligible (sub-cent). The tool queries the
network for current price automatically.

## Dependencies

- `cryptography` — already required by the engine (signing.py)
- stdlib only beyond that — no arweave-python-client package needed

## Usage

    python arweave_upload.py upload <precedent_id>
    python arweave_upload.py sync [--limit 500]
    python arweave_upload.py upload-file path/to/file.json
    python arweave_upload.py status

Environment:
    ARWEAVE_WALLET_PATH  — path to JWK wallet JSON file
    ARWEAVE_WALLET_JSON  — inline wallet JSON (alternative to file path)
    ARWEAVE_GATEWAY      — gateway URL (default: https://arweave.net)
    CONCORDANCE_API      — Concordance API base URL
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── repo path bootstrap ────────────────────────────────────────────────
_here = Path(__file__).parent
_repo = _here.parent
sys.path.insert(0, str(_repo / "src"))

DEFAULT_API = os.environ.get("CONCORDANCE_API", "https://narrowhighway.com")
DEFAULT_GATEWAY = os.environ.get("ARWEAVE_GATEWAY", "https://arweave.net")
STATE_FILE = os.environ.get(
    "CONCORDANCE_ARWEAVE_STATE",
    os.path.expanduser("~/.concordance/arweave_uploaded.json"),
)
APP_NAME = "Concordance"
APP_VERSION = "1.1"


# ── Encoding helpers ───────────────────────────────────────────────────

def _b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _sha384(data: bytes) -> bytes:
    return hashlib.sha384(data).digest()


# ── Arweave deep hash (SHA-384 recursive) ─────────────────────────────
# Reference: arweave-js utils/deep-hash.ts

def _deep_hash(data: Any) -> bytes:
    """Compute the Arweave deep hash of a nested structure.

    Leaves (bytes/str) → SHA-384("blob" + str(len) + data)
    Lists              → SHA-384(fold each element into running acc)
    """
    if isinstance(data, list):
        tag = b"list" + str(len(data)).encode()
        acc = _sha384(tag)
        for item in data:
            h = _deep_hash(item)
            acc = _sha384(acc + h)
        return acc

    if isinstance(data, str):
        data = data.encode("utf-8")
    tag = b"blob" + str(len(data)).encode()
    return _sha384(_sha384(tag) + _sha384(data))


# ── Arweave Merkle data_root (format v2, single chunk) ────────────────
# Reference: arweave-js utils/merkle.ts, generateLeaves

def _int_to_buf32(n: int) -> bytes:
    return n.to_bytes(32, "big")


def _compute_data_root(data: bytes) -> bytes:
    """Merkle root for a single chunk. For data <= 256 KB the tree is
    one leaf: id = SHA-256(SHA-256(data) + SHA-256(max_offset))."""
    data_hash = _sha256(data)
    note = _int_to_buf32(len(data))
    note_hash = _sha256(note)
    return _sha256(data_hash + note_hash)


# ── Wallet ─────────────────────────────────────────────────────────────

def _load_wallet() -> Optional[Dict[str, Any]]:
    """Load the Arweave JWK wallet from env. Returns None if not configured."""
    inline = os.environ.get("ARWEAVE_WALLET_JSON", "").strip()
    if inline:
        try:
            return json.loads(inline)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"error: ARWEAVE_WALLET_JSON is invalid JSON: {exc}")

    path = os.environ.get("ARWEAVE_WALLET_PATH", "").strip()
    if path:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"error: could not load wallet from {path}: {exc}")

    return None


def _wallet_address(jwk: Dict[str, Any]) -> str:
    """Arweave wallet address = base64url(SHA-256(modulus_bytes))."""
    n_bytes = _b64u_decode(jwk["n"])
    return _b64u_encode(_sha256(n_bytes))


def _jwk_to_private_key(jwk: Dict[str, Any]):
    """Build a cryptography RSAPrivateKey from an Arweave JWK."""
    try:
        from cryptography.hazmat.primitives.asymmetric.rsa import (
            RSAPrivateNumbers, RSAPublicNumbers,
        )
        from cryptography.hazmat.backends import default_backend
    except ImportError as exc:
        raise SystemExit(
            "error: Arweave signing requires the `cryptography` package.\n"
            "Install: pip install cryptography"
        ) from exc

    def _i(key: str) -> int:
        return int.from_bytes(_b64u_decode(jwk[key]), "big")

    pub = RSAPublicNumbers(_i("e"), _i("n"))
    priv = RSAPrivateNumbers(_i("p"), _i("q"), _i("d"), _i("dp"), _i("dq"), _i("qi"), pub)
    return priv.private_key(default_backend())


# ── Network helpers ────────────────────────────────────────────────────

def _http_get(url: str, timeout: float = 15.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _http_post_json(url: str, body: dict, timeout: float = 60.0) -> Tuple[int, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def _fetch_anchor(gateway: str) -> str:
    """Get the current TX anchor (last 50 blocks' reward addr hash)."""
    url = gateway.rstrip("/") + "/tx_anchor"
    return _http_get(url).strip()


def _fetch_price(gateway: str, data_size: int) -> int:
    """Get the current Winston fee for uploading data_size bytes."""
    url = gateway.rstrip("/") + f"/price/{data_size}"
    return int(_http_get(url).strip())


# ── Transaction builder ────────────────────────────────────────────────

def _build_and_sign_tx(
    data_bytes: bytes,
    tags: List[Dict[str, str]],
    jwk: Dict[str, Any],
    gateway: str,
    reward: Optional[int] = None,
) -> Dict[str, Any]:
    """Build and sign an Arweave format-v2 data transaction.

    Returns the complete signed TX dict ready for POST /tx.
    """
    # Encode tags (name/value as base64url strings per Arweave spec)
    encoded_tags = [
        {"name": _b64u_encode(t["name"].encode()), "value": _b64u_encode(t["value"].encode())}
        for t in tags
    ]

    anchor = _fetch_anchor(gateway)
    if reward is None:
        reward = _fetch_price(gateway, len(data_bytes))

    data_b64u = _b64u_encode(data_bytes)
    data_root = _compute_data_root(data_bytes)
    owner_bytes = _b64u_decode(jwk["n"])

    # Signature data: deep hash of TX fields (arweave-js order)
    sig_data = _deep_hash([
        b"2",                          # format
        owner_bytes,                   # owner = RSA modulus raw bytes
        b"",                           # target (empty for data tx)
        b"0",                          # quantity (no AR transfer)
        str(reward).encode(),          # reward in Winston
        _b64u_decode(anchor),          # last_tx anchor
        [[_b64u_decode(t["name"]), _b64u_decode(t["value"])]
         for t in encoded_tags],       # tags as raw bytes pairs
        str(len(data_bytes)).encode(), # data_size
        data_root,                     # Merkle root
    ])

    # RSA-PSS signature (SHA-256, MGF1-SHA-256, salt=32)
    try:
        from cryptography.hazmat.primitives.asymmetric import padding as _padding
        from cryptography.hazmat.primitives import hashes as _hashes
    except ImportError as exc:
        raise SystemExit("error: cryptography package required") from exc

    priv = _jwk_to_private_key(jwk)
    signature = priv.sign(
        sig_data,
        _padding.PSS(
            mgf=_padding.MGF1(_hashes.SHA256()),
            salt_length=32,
        ),
        _hashes.SHA256(),
    )

    sig_b64u = _b64u_encode(signature)
    tx_id = _b64u_encode(_sha256(signature))

    return {
        "format": 2,
        "id": tx_id,
        "last_tx": anchor,
        "owner": jwk["n"],
        "tags": encoded_tags,
        "target": "",
        "quantity": "0",
        "data": data_b64u,
        "data_size": str(len(data_bytes)),
        "data_root": _b64u_encode(data_root),
        "reward": str(reward),
        "signature": sig_b64u,
    }


def upload_data(
    data_bytes: bytes,
    tags: List[Dict[str, str]],
    *,
    gateway: str = DEFAULT_GATEWAY,
    dry_run: bool = False,
) -> str:
    """Sign and upload data to Arweave. Returns the TX ID.

    Raises SystemExit on wallet missing or submission error.
    """
    jwk = _load_wallet()
    if jwk is None:
        raise SystemExit(
            "error: no Arweave wallet configured.\n"
            "Set ARWEAVE_WALLET_PATH=/path/to/wallet.json "
            "or ARWEAVE_WALLET_JSON='{...}'"
        )

    tx = _build_and_sign_tx(data_bytes, tags, jwk, gateway)
    tx_id = tx["id"]

    if dry_run:
        print(f"[dry-run] would upload {len(data_bytes)} bytes → txid: {tx_id}")
        return tx_id

    url = gateway.rstrip("/") + "/tx"
    status, body = _http_post_json(url, tx)
    if status not in (200, 202):
        raise SystemExit(f"error: Arweave submission failed ({status}): {body}")

    return tx_id


# ── Concordance API helpers ────────────────────────────────────────────

def _http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
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


# ── State ──────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {"uploaded": {}, "files": {}}
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"uploaded": {}, "files": {}}


def _save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── CLI subcommands ────────────────────────────────────────────────────

def _receipt_tags(precedent_id: str) -> List[Dict[str, str]]:
    return [
        {"name": "Content-Type",  "value": "application/json"},
        {"name": "App-Name",      "value": APP_NAME},
        {"name": "App-Version",   "value": APP_VERSION},
        {"name": "Type",          "value": "soulbound-receipt"},
        {"name": "Precedent-Id",  "value": precedent_id},
    ]


def cmd_upload(args) -> None:
    state = _load_state()
    pid = args.precedent_id

    if pid in state["uploaded"] and not args.force:
        info = state["uploaded"][pid]
        print(f"already uploaded: {info['txid']}")
        print(f"    view: {DEFAULT_GATEWAY}/{info['txid']}")
        return

    try:
        record = fetch_precedent(args.api, pid)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch {pid}: {exc}", file=sys.stderr)
        sys.exit(1)

    body = json.dumps(record, separators=(",", ":")).encode("utf-8")
    tags = _receipt_tags(pid)

    try:
        txid = upload_data(body, tags, gateway=args.gateway, dry_run=args.dry_run)
    except SystemExit:
        raise

    state["uploaded"][pid] = {
        "txid": txid,
        "uploaded_at": int(time.time()),
        "size_bytes": len(body),
        "gateway_url": f"{args.gateway.rstrip('/')}/{txid}",
    }
    _save_state(state)
    print(f"[ok] {pid}")
    print(f"     txid: {txid}")
    print(f"     view: {args.gateway.rstrip('/')}/{txid}")


def cmd_sync(args) -> None:
    state = _load_state()
    uploaded = state["uploaded"]

    try:
        entries = fetch_recent_chain(args.api, since_seq=0, limit=args.limit)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"error: could not fetch chain: {exc}", file=sys.stderr)
        sys.exit(1)

    new_count = 0
    for e in entries:
        pid = e.get("packet_id")
        if not pid or (pid in uploaded and not args.force):
            continue
        body = json.dumps(e, separators=(",", ":")).encode("utf-8")
        tags = _receipt_tags(pid)
        try:
            txid = upload_data(body, tags, gateway=args.gateway, dry_run=args.dry_run)
        except SystemExit:
            raise
        except Exception as exc:
            print(f"[err ] {pid}: {exc}", file=sys.stderr)
            continue

        uploaded[pid] = {
            "txid": txid,
            "uploaded_at": int(time.time()),
            "size_bytes": len(body),
            "gateway_url": f"{args.gateway.rstrip('/')}/{txid}",
        }
        print(f"[ok  ] {pid} → {txid}")
        new_count += 1

    state["uploaded"] = uploaded
    _save_state(state)
    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}{new_count} new receipts uploaded, {len(uploaded)} total tracked.")


def cmd_upload_file(args) -> None:
    path = Path(args.path)
    if not path.exists():
        print(f"error: file not found: {path}", file=sys.stderr)
        sys.exit(1)
    body = path.read_bytes()
    ext = path.suffix.lower()
    content_type = "application/json" if ext == ".json" else "application/octet-stream"
    tags = [
        {"name": "Content-Type", "value": content_type},
        {"name": "App-Name",     "value": APP_NAME},
        {"name": "App-Version",  "value": APP_VERSION},
        {"name": "File-Name",    "value": path.name},
    ]
    txid = upload_data(body, tags, gateway=args.gateway, dry_run=args.dry_run)
    state = _load_state()
    state.setdefault("files", {})[str(path)] = {
        "txid": txid,
        "uploaded_at": int(time.time()),
        "size_bytes": len(body),
        "name": path.name,
    }
    _save_state(state)
    print(f"[ok] {path.name} → {txid}  ({len(body):,} bytes)")
    print(f"     view: {args.gateway.rstrip('/')}/{txid}")


def cmd_status(args) -> None:
    state = _load_state()
    uploaded = state.get("uploaded", {})
    files = state.get("files", {})
    print(f"=== {len(uploaded)} receipts uploaded ===")
    for pid, info in sorted(uploaded.items(), key=lambda x: x[1].get("uploaded_at", 0), reverse=True):
        age_h = (time.time() - info.get("uploaded_at", 0)) / 3600
        kb = info.get("size_bytes", 0) / 1024
        print(f"  {pid:<40} {info.get('txid', '?')}  ({age_h:.1f}h ago, {kb:.1f}KB)")
    if files:
        print(f"\n=== {len(files)} files uploaded ===")
        for path, info in files.items():
            print(f"  {info.get('name', path):<40} {info.get('txid', '?')}")
    if not uploaded and not files:
        print("  (nothing uploaded yet — run 'sync' to upload sealed receipts)")


# ── Main ───────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Upload sealed Concordance receipts to Arweave (permanent storage).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Wallet: set ARWEAVE_WALLET_PATH or ARWEAVE_WALLET_JSON.\n"
            "Get a wallet at https://arweave.app/ (free to create, needs AR tokens to upload).\n"
        ),
    )
    p.add_argument("--gateway", default=DEFAULT_GATEWAY,
                   help=f"Arweave gateway (default: {DEFAULT_GATEWAY})")
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API (default: {DEFAULT_API})")
    p.add_argument("--dry-run", action="store_true",
                   help="Build and sign the transaction but do not submit it")

    sub = p.add_subparsers(dest="cmd", required=True)

    upl = sub.add_parser("upload", help="Upload a single precedent by ID.")
    upl.add_argument("precedent_id")
    upl.add_argument("--force", action="store_true", help="Re-upload even if already tracked")

    syn = sub.add_parser("sync", help="Upload all unsealed precedents (idempotent).")
    syn.add_argument("--limit", type=int, default=500,
                     help="Max entries to consider per run (default: 500)")
    syn.add_argument("--force", action="store_true", help="Re-upload already-tracked entries")

    uf = sub.add_parser("upload-file", help="Upload an arbitrary file.")
    uf.add_argument("path", help="Path to file")

    sub.add_parser("status", help="Show upload history.")

    args = p.parse_args()
    dispatch = {
        "upload": cmd_upload,
        "sync": cmd_sync,
        "upload-file": cmd_upload_file,
        "status": cmd_status,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
