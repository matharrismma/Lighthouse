"""Offline queue — durable local buffer for verify calls that fail or arrive
when the verifier layer is temporarily unavailable.

When POST /verify/{domain} is called and the verifier is unavailable (import
error, network partition, temporary engine failure), the request is enqueued
here. A background thread periodically retries queued items and writes
successful results to the packet store.

Storage: data/offline_queue.jsonl — one pending entry per line.
Completed entries are moved to data/offline_queue_completed.jsonl.

This is the offline-first foundation required for LoRa mesh deployment:
packets queued locally sync when the node reconnects, whether that's in
5 seconds or 5 days.

Override storage root via OFFLINE_QUEUE_DIR env var.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


def _queue_dir() -> Path:
    return Path(os.environ.get("OFFLINE_QUEUE_DIR", "data"))


def _queue_path() -> Path:
    return _queue_dir() / "offline_queue.jsonl"


def _completed_path() -> Path:
    return _queue_dir() / "offline_queue_completed.jsonl"


_QUEUE_LOCK = threading.Lock()
_COMPLETED_LOCK = threading.Lock()


def enqueue(domain: str, spec: Dict[str, Any], reason: str = "") -> str:
    """Add a pending verify request to the offline queue.

    Returns the queue entry id. The background retry thread will attempt
    to process this entry on the next tick.
    """
    entry_id = str(uuid.uuid4())
    now = int(time.time())
    entry = {
        "id": entry_id,
        "queued_at": now,
        "queued_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "domain": domain,
        "spec": spec,
        "reason": reason,
        "attempts": 0,
        "last_attempt": None,
        "status": "pending",
    }
    path = _queue_path()
    with _QUEUE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, separators=(",", ":"), default=str) + "\n")
    return entry_id


def list_pending(limit: int = 100) -> List[Dict[str, Any]]:
    """Return pending queue entries, oldest first."""
    path = _queue_path()
    if not path.exists():
        return []
    entries = []
    with _QUEUE_LOCK:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    e = json.loads(stripped)
                    if e.get("status") == "pending":
                        entries.append(e)
                except json.JSONDecodeError:
                    continue
    return entries[:limit]


def queue_stats() -> Dict[str, Any]:
    """Return counts of pending/processing entries."""
    path = _queue_path()
    completed_path = _completed_path()
    pending = 0
    failed = 0
    if path.exists():
        with _QUEUE_LOCK:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        e = json.loads(stripped)
                        s = e.get("status", "pending")
                        if s == "pending":
                            pending += 1
                        elif s == "failed":
                            failed += 1
                    except json.JSONDecodeError:
                        continue
    completed = 0
    if completed_path.exists():
        with _COMPLETED_LOCK:
            with completed_path.open("r", encoding="utf-8") as f:
                completed = sum(1 for line in f if line.strip())
    return {"pending": pending, "failed": failed, "completed": completed}


def _mark_completed(entry_id: str, result: Any) -> None:
    """Remove entry from queue and append to completed log."""
    path = _queue_path()
    completed_path = _completed_path()

    with _QUEUE_LOCK:
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        kept = []
        completed_entry = None
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                e = json.loads(stripped)
                if e.get("id") == entry_id:
                    e["status"] = "completed"
                    e["completed_at"] = int(time.time())
                    e["result"] = result
                    completed_entry = e
                else:
                    kept.append(stripped)
            except json.JSONDecodeError:
                kept.append(stripped)
        path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    if completed_entry:
        with _COMPLETED_LOCK:
            completed_path.parent.mkdir(parents=True, exist_ok=True)
            with completed_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(completed_entry, separators=(",", ":"), default=str) + "\n")


def _mark_failed(entry_id: str, error: str, max_attempts: int) -> None:
    """Increment attempt count; mark failed if max_attempts exceeded."""
    path = _queue_path()
    with _QUEUE_LOCK:
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        updated = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                e = json.loads(stripped)
                if e.get("id") == entry_id:
                    e["attempts"] = e.get("attempts", 0) + 1
                    e["last_attempt"] = int(time.time())
                    e["last_error"] = error
                    if e["attempts"] >= max_attempts:
                        e["status"] = "failed"
                updated.append(json.dumps(e, separators=(",", ":"), default=str))
            except json.JSONDecodeError:
                updated.append(stripped)
        path.write_text("\n".join(updated) + ("\n" if updated else ""), encoding="utf-8")


def process_one(entry: Dict[str, Any], max_attempts: int = 5) -> bool:
    """Attempt to process one queued entry. Returns True on success."""
    entry_id = entry["id"]
    domain = entry["domain"]
    spec = entry.get("spec") or {}

    try:
        from concordance_engine.mcp_server.tools import ALL_TOOLS
        tool_name = f"verify_{domain}"
        fn = ALL_TOOLS.get(tool_name)
        if fn is None:
            _mark_failed(entry_id, f"no tool: {tool_name}", max_attempts)
            return False
        result = fn(spec)
        from api.packet_store import get_packet_store
        get_packet_store().append(domain, spec, result)
        _mark_completed(entry_id, result)
        return True
    except Exception as exc:
        _mark_failed(entry_id, str(exc), max_attempts)
        return False


# ── Background retry thread ────────────────────────────────────────────

_RETRY_THREAD: Optional[threading.Thread] = None
_STOP_EVENT = threading.Event()


def start_retry_thread(interval_seconds: int = 30, max_attempts: int = 5) -> None:
    """Start the background retry thread (idempotent — safe to call multiple times)."""
    global _RETRY_THREAD
    if _RETRY_THREAD is not None and _RETRY_THREAD.is_alive():
        return

    def _run() -> None:
        while not _STOP_EVENT.wait(interval_seconds):
            try:
                pending = list_pending(limit=10)
                for entry in pending:
                    if _STOP_EVENT.is_set():
                        break
                    process_one(entry, max_attempts=max_attempts)
            except Exception:
                pass

    _RETRY_THREAD = threading.Thread(target=_run, daemon=True, name="offline-queue-retry")
    _RETRY_THREAD.start()


def stop_retry_thread() -> None:
    """Signal the retry thread to stop. Blocks until it exits."""
    _STOP_EVENT.set()
    if _RETRY_THREAD is not None:
        _RETRY_THREAD.join(timeout=5)
