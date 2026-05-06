"""Peer registry — known Concordance instances that can sync packets.

Storage: data/peers.json  (list of peer dicts)

Each peer:
    {
      "instance_id": "<first 16 chars of pubkey>",
      "url": "http://192.168.1.42:8000",
      "pubkey": "<base64url Ed25519 public key>",
      "registered_at": <epoch>,
      "last_seen": <epoch>,
      "packets_synced": <int>
    }

The registry is append-on-register, update-on-seen. It never auto-removes
entries — that's a manual operation so we don't silently lose trust chains
from temporarily-offline nodes.

Override storage root via PEER_REGISTRY_PATH env var.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


def _registry_path() -> Path:
    return Path(os.environ.get("PEER_REGISTRY_PATH", "data/peers.json"))


_LOCK = threading.Lock()


def _read_all() -> List[Dict[str, Any]]:
    path = _registry_path()
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_all(peers: List[Dict[str, Any]]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(peers, f, indent=2, default=str)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (OSError, AttributeError):
                pass
        tmp.replace(path)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def register(url: str, pubkey: str, instance_id: str) -> Dict[str, Any]:
    """Register or update a peer. Returns the peer record."""
    now = int(time.time())
    with _LOCK:
        peers = _read_all()
        for p in peers:
            if p.get("instance_id") == instance_id:
                p["url"] = url
                p["pubkey"] = pubkey
                p["last_seen"] = now
                _write_all(peers)
                return dict(p)
        peer: Dict[str, Any] = {
            "instance_id": instance_id,
            "url": url,
            "pubkey": pubkey,
            "registered_at": now,
            "last_seen": now,
            "packets_synced": 0,
        }
        peers.append(peer)
        _write_all(peers)
        return dict(peer)


def list_peers() -> List[Dict[str, Any]]:
    """Return all registered peers."""
    with _LOCK:
        return list(_read_all())


def get_peer(instance_id: str) -> Optional[Dict[str, Any]]:
    """Return a single peer by instance_id, or None."""
    with _LOCK:
        for p in _read_all():
            if p.get("instance_id") == instance_id:
                return dict(p)
        return None


def update_seen(instance_id: str, packets_synced: int = 0) -> None:
    """Record a successful sync event for a known peer."""
    now = int(time.time())
    with _LOCK:
        peers = _read_all()
        for p in peers:
            if p.get("instance_id") == instance_id:
                p["last_seen"] = now
                p["packets_synced"] = p.get("packets_synced", 0) + packets_synced
                _write_all(peers)
                return


def remove_peer(instance_id: str) -> bool:
    """Remove a peer by instance_id. Returns True if found and removed."""
    with _LOCK:
        peers = _read_all()
        filtered = [p for p in peers if p.get("instance_id") != instance_id]
        if len(filtered) == len(peers):
            return False
        _write_all(filtered)
        return True
