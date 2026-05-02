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

    def get_by_seq(self, seq):
        """Look up a single ledger entry by its sequence number. Returns the
        entry dict, or None if not found. Used by /confess to verify the
        referenced packet exists, and by /dispatch for direct seq lookups."""
        if not self._path.exists():
            return None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entry = json.loads(stripped)
                    if entry.get("seq") == seq:
                        return entry
                except json.JSONDecodeError:
                    continue
        return None

    def get_by_packet_hash(self, packet_hash):
        """Return every entry whose packet_hash matches. A confession on a
        packet would share the original's packet_hash via the link field
        (`confesses_packet_hash`), not via this; use get_by_seq when you
        want a specific entry."""
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
                    if entry.get("packet_hash") == packet_hash:
                        results.append(entry)
                except json.JSONDecodeError:
                    continue
        return results

    def iter_filtered(self, *, domain=None, overall=None, since_epoch=None,
                      until_epoch=None, packet_id=None, limit=None):
        """Yield ledger entries (newest first) that match every supplied
        filter. None for a filter means "any value." Used by /dispatch.

        Filters:
            domain        — exact domain string (e.g. "governance")
            overall       — exact verdict string (e.g. "PASS", "REJECT",
                            "QUARANTINE", "CONFESSION")
            since_epoch   — entries with timestamp_epoch >= since_epoch
            until_epoch   — entries with timestamp_epoch <= until_epoch
            packet_id     — exact packet_id string
            limit         — stop after yielding `limit` matches (None = all)
        """
        if not self._path.exists():
            return
        # Read all into memory; ledger is small. For large ledgers this
        # would want streaming + reverse-line-walk, but JSONL append-only
        # at expected scale (thousands of entries) reads fast enough.
        entries = []
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    entries.append(json.loads(stripped))
                except json.JSONDecodeError:
                    continue
        entries.reverse()  # newest first
        yielded = 0
        for e in entries:
            if domain is not None and e.get("domain") != domain:
                continue
            if overall is not None and e.get("overall") != overall:
                continue
            if packet_id is not None and e.get("packet_id") != packet_id:
                continue
            ts = int(e.get("timestamp_epoch") or 0)
            if since_epoch is not None and ts < since_epoch:
                continue
            if until_epoch is not None and ts > until_epoch:
                continue
            yield e
            yielded += 1
            if limit is not None and yielded >= limit:
                return

    def stats(self):
        """Aggregate counts across the ledger: total entries, breakdown by
        overall verdict and by domain, latest entry's timestamp. Used by
        /stats and /about."""
        if not self._path.exists():
            return {
                "total": 0,
                "by_overall": {},
                "by_domain": {},
                "latest_timestamp_epoch": None,
                "latest_timestamp_iso": None,
            }
        by_overall = {}
        by_domain = {}
        total = 0
        latest_ts = 0
        latest_iso = None
        with self._path.open("r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    e = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                total += 1
                ov = e.get("overall", "UNKNOWN")
                dm = e.get("domain", "unknown")
                by_overall[ov] = by_overall.get(ov, 0) + 1
                by_domain[dm] = by_domain.get(dm, 0) + 1
                ts = int(e.get("timestamp_epoch") or 0)
                if ts > latest_ts:
                    latest_ts = ts
                    latest_iso = e.get("timestamp_iso")
        return {
            "total": total,
            "by_overall": by_overall,
            "by_domain": by_domain,
            "latest_timestamp_epoch": latest_ts or None,
            "latest_timestamp_iso": latest_iso,
        }

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
