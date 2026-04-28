"""
Evidence Ledger -- append-only JSONL with SHA-256 hash chain.

Every call to append() writes one line to ledger.jsonl. Each entry
carries a hash of itself chained to the previous entry's hash, making
tampering detectable: if any prior entry is altered, every subsequent
entry_hash will be wrong.

The ledger never deletes. It never mutates. It only grows.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

GENESIS_HASH = "0" * 64  # hash of nothing -- the beginning


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _packet_hash(packet: Dict[str, Any]) -> str:
    return _sha256(_canonical(packet))


def _entry_hash(prev_hash: str, packet_hash: str, overall: str, timestamp_epoch: int) -> str:
    raw = f"{prev_hash}|{packet_hash}|{overall}|{timestamp_epoch}"
    return _sha256(raw)


@dataclass
class LedgerEntry:
    seq: int
    timestamp_iso: str
    timestamp_epoch: int
    packet_id: str
    domain: str
    overall: str
    gate_summary: Dict[str, str]
    top_reasons: List[str]
    packet_hash: str
    prev_hash: str
    entry_hash: str


class Ledger:
    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._last_hash: str = GENESIS_HASH
        self._seq: int = 0
        self._load_tail()

    def _load_tail(self) -> None:
        if not self._path.exists():
            return
        last_line = ""
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if last_line:
            try:
                entry = json.loads(last_line)
                self._last_hash = entry.get("entry_hash", GENESIS_HASH)
                self._seq = entry.get("seq", 0)
            except json.JSONDecodeError:
                pass

    def append(self, packet, overall, gate_results):
        now = int(time.time())
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        packet_id = str(packet.get("id") or packet.get("domain") or "unknown")
        domain = str(packet.get("domain") or "unknown")
        gate_summary = {}
        top_reasons = []
        for gr in gate_results:
            gate_summary[gr.gate] = gr.status
            if gr.status in ("REJECT", "QUARANTINE") and gr.reasons:
                top_reasons.extend(gr.reasons[:2])
        p_hash = _packet_hash(packet)
        with self._lock:
            self._seq += 1
            seq = self._seq
            prev = self._last_hash
            e_hash = _entry_hash(prev, p_hash, overall, now)
            entry = LedgerEntry(seq=seq, timestamp_iso=iso, timestamp_epoch=now,
                packet_id=packet_id, domain=domain, overall=overall,
                gate_summary=gate_summary, top_reasons=top_reasons[:5],
                packet_hash=p_hash, prev_hash=prev, entry_hash=e_hash)
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")
            self._last_hash = e_hash
        return entry

    def recent(self, n=50, offset=0):
        if not self._path.exists():
            return []
        lines = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    lines.append(stripped)
        lines.reverse()
        selected = lines[offset: offset + n]
        results = []
        for line in selected:
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return results

    def get_by_id(self, packet_id):
        if not self._path.exists():
            return []
        results = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                    if entry.get("packet_id") == packet_id:
                        results.append(entry)
                except json.JSONDecodeError:
                    continue
        return results

    def verify_chain(self):
        if not self._path.exists():
            return {"valid": True, "entries_checked": 0, "first_broken_seq": None}
        prev = GENESIS_HASH
        count = 0
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                except json.JSONDecodeError:
                    return {"valid": False, "entries_checked": count, "first_broken_seq": count + 1}
                count += 1
                expected = _entry_hash(prev, entry["packet_hash"], entry["overall"], entry["timestamp_epoch"])
                if entry["entry_hash"] != expected:
                    return {"valid": False, "entries_checked": count, "first_broken_seq": entry.get("seq")}
                prev = entry["entry_hash"]
        return {"valid": True, "entries_checked": count, "first_broken_seq": None}


_ledger = None


def get_ledger():
    global _ledger
    if _ledger is None:
        ledger_path = Path(os.environ.get("LEDGER_PATH", "ledger.jsonl"))
        _ledger = Ledger(ledger_path)
    return _ledger
