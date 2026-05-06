"""Domain-partitioned packet store — the Journal in packet form.

Verified packets are written to data/packets/{domain}.jsonl, one entry
per line. Each entry carries the input spec, the full tool results, and
a timestamp. The collection grows into a queryable, domain-indexed
knowledge base of verified claims.

Storage layout:
    data/packets/number_theory.jsonl
    data/packets/cryptography.jsonl
    data/packets/quantum_computing.jsonl
    ...

Each line:
    {
      "id": "<uuid>",
      "timestamp_iso": "...", "timestamp_epoch": 123456,
      "domain": "number_theory",
      "spec": {<input fields>},
      "results": {<tool output — check name → {status, detail, data}>},
      "summary": "CONFIRMED|MISMATCH|PARTIAL|NOT_APPLICABLE|ERROR"
    }

Override storage root via PACKET_STORE_DIR env var.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Make the engine importable when running from the api/ directory.
_engine_path = os.environ.get("CONCORDANCE_ENGINE_PATH")
if _engine_path:
    sys.path.insert(0, str(Path(_engine_path) / "src"))


def _try_sign(data: dict) -> dict:
    """Sign a dict with the instance key if the engine is available.
    Returns the original dict if signing is unavailable (no private key,
    cryptography not installed, etc.) — signing is best-effort so the
    packet store works even in minimal deployments.
    """
    try:
        from concordance_engine.instance_identity import sign_dict
        return sign_dict(data)
    except Exception:
        return data


def _store_dir() -> Path:
    return Path(os.environ.get("PACKET_STORE_DIR", "data/packets"))


def _summarize(results: Any) -> str:
    """Derive overall summary from a tool-result dict.

    Handles two shapes returned by ALL_TOOLS wrappers:
      {"checks": [{"status": "CONFIRMED", ...}, ...]}   ← array form
      {"check_name": {"status": "CONFIRMED", ...}, ...} ← flat dict form
    """
    if not isinstance(results, dict):
        return "UNKNOWN"
    # Array form: {"checks": [...]}
    if "checks" in results and isinstance(results["checks"], list):
        statuses = [c.get("status", "") for c in results["checks"]
                    if isinstance(c, dict)]
    else:
        # Flat dict form: {name: {status: ...}}
        statuses = [v["status"] for v in results.values()
                    if isinstance(v, dict) and "status" in v]
    if not statuses:
        return "NOT_APPLICABLE"
    if any(s == "ERROR" for s in statuses):
        return "ERROR"
    if any(s == "MISMATCH" for s in statuses):
        return "MISMATCH"
    if all(s == "CONFIRMED" for s in statuses):
        return "CONFIRMED"
    if all(s == "NOT_APPLICABLE" for s in statuses):
        return "NOT_APPLICABLE"
    if any(s == "CONFIRMED" for s in statuses):
        return "PARTIAL"
    return "NOT_APPLICABLE"


class PacketStore:
    def __init__(self, base_dir: Optional[Path] = None):
        self._base = base_dir or _store_dir()
        self._domain_locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _lock_for(self, domain: str) -> threading.Lock:
        with self._meta_lock:
            if domain not in self._domain_locks:
                self._domain_locks[domain] = threading.Lock()
            return self._domain_locks[domain]

    def _path(self, domain: str) -> Path:
        safe = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in domain)
        return self._base / f"{safe}.jsonl"

    def append(self, domain: str, spec: Dict[str, Any],
                results: Any) -> Dict[str, Any]:
        """Write one verified packet entry. Returns the full entry dict."""
        now = int(time.time())
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        entry = {
            "id": str(uuid.uuid4()),
            "timestamp_iso": iso,
            "timestamp_epoch": now,
            "domain": domain,
            "spec": spec,
            "results": results,
            "summary": _summarize(results),
        }
        entry = _try_sign(entry)
        path = self._path(domain)
        lock = self._lock_for(domain)
        with lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    pass
        return entry

    def list(self, domain: str, limit: int = 50,
             offset: int = 0) -> List[Dict[str, Any]]:
        """Return entries for a domain, newest first."""
        path = self._path(domain)
        if not path.exists():
            return []
        lines: List[Dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        lines.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        continue
        lines.reverse()
        return lines[offset: offset + limit]

    def get(self, domain: str, entry_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a single entry by id. Returns None if not found."""
        path = self._path(domain)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                    if entry.get("id") == entry_id:
                        return entry
                except json.JSONDecodeError:
                    continue
        return None

    def domains(self) -> List[str]:
        """Return sorted list of domains that have stored entries."""
        if not self._base.exists():
            return []
        return sorted(p.stem for p in self._base.glob("*.jsonl"))

    def verify_signature(self, entry: Dict[str, Any]) -> tuple:
        """Verify the instance signature on a stored packet entry.
        Returns (ok: bool, detail: str).
        """
        try:
            from concordance_engine.instance_identity import verify_dict
            return verify_dict(entry)
        except Exception as exc:
            return False, f"signature check unavailable: {exc}"

    def stats(self) -> Dict[str, Any]:
        """Per-domain entry counts and summary breakdowns."""
        result: Dict[str, Any] = {}
        for domain in self.domains():
            path = self._path(domain)
            count = 0
            by_summary: Dict[str, int] = {}
            try:
                with path.open("r", encoding="utf-8") as f:
                    for line in f:
                        if not line.strip():
                            continue
                        count += 1
                        try:
                            s = json.loads(line).get("summary", "UNKNOWN")
                        except json.JSONDecodeError:
                            s = "UNKNOWN"
                        by_summary[s] = by_summary.get(s, 0) + 1
            except OSError:
                pass
            result[domain] = {"count": count, "by_summary": by_summary}
        return result


_store: Optional[PacketStore] = None


def get_packet_store() -> PacketStore:
    global _store
    if _store is None:
        _store = PacketStore()
    return _store
