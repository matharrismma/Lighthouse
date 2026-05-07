"""
node-init.py — Generate Concordance node identity
──────────────────────────────────────────────────
Called by install.sh to create a unique Ed25519 signing key and node config.
Safe to call repeatedly — skips if key already exists.

Usage:
  python local/node-init.py [output_path]
  python local/node-init.py /etc/concordance/node_key.json
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import socket
import sys

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, PublicFormat, PrivateFormat, NoEncryption,
    )
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def generate_identity(out_path: pathlib.Path) -> dict:
    if out_path.exists():
        existing = json.loads(out_path.read_text())
        print(f"  node_id  : {existing.get('node_id', '?')}")
        print(f"  hostname : {existing.get('hostname', '?')}")
        print("  (existing key, skipped)")
        return existing

    if not HAS_CRYPTO:
        # Fallback: derive a stable ID from hostname + MAC address
        import uuid
        hostname = socket.gethostname()
        mac      = uuid.getnode()
        seed     = f"{hostname}:{mac}".encode()
        node_id  = hashlib.sha256(seed).hexdigest()[:20]
        record   = {
            "node_id":    node_id,
            "hostname":   hostname,
            "public_key": hashlib.sha256(seed + b":pub").hexdigest(),
            "private_key": "(cryptography package not installed — key strength reduced)",
            "warning":    "Install cryptography: pip install cryptography",
        }
    else:
        key      = Ed25519PrivateKey.generate()
        pub      = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        priv     = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
        hostname = socket.gethostname()
        node_id  = hashlib.sha256(bytes.fromhex(pub)).hexdigest()[:20]
        record   = {
            "node_id":     node_id,
            "hostname":    hostname,
            "public_key":  pub,
            "private_key": priv,
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2))
    out_path.chmod(0o640)

    print(f"  node_id  : {record['node_id']}")
    print(f"  hostname : {record['hostname']}")
    print(f"  key file : {out_path}")
    return record


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 \
             else pathlib.Path("/etc/concordance/node_key.json")
    generate_identity(target)
