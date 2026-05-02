"""Tests for the api/ledger.py append-only chain + helper queries.

Exercises a fresh ledger in a temp file, appends a few entries, and
verifies: chain integrity, get_by_seq lookup, get_by_packet_hash lookup,
iter_filtered semantics (AND filters), and stats aggregation.

Run: PYTHONPATH=src python tests/test_ledger.py
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure the api/ package is importable
_REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO))

from api.ledger import Ledger, GENESIS_HASH


PASS = 0
FAIL = 0


def expect(name, actual, expected):
    global PASS, FAIL
    ok = actual == expected
    icon = "✓" if ok else "✗"
    if ok:
        PASS += 1
    else:
        FAIL += 1
    print(f"  {icon} {name}: got {actual!r}, expected {expected!r}")


class _GR:
    """Minimal GateResult-like for ledger.append (which only reads .gate,
    .status, .reasons)."""
    def __init__(self, gate, status, reasons=None):
        self.gate = gate
        self.status = status
        self.reasons = reasons or []


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test_ledger.jsonl"
        ledger = Ledger(path)

        print("Empty ledger:")
        expect("recent on empty returns []", ledger.recent(), [])
        expect("get_by_seq on empty returns None", ledger.get_by_seq(1), None)
        expect("get_by_packet_hash on empty returns []",
               ledger.get_by_packet_hash("deadbeef"), [])
        expect("verify_chain on empty is valid",
               ledger.verify_chain()["valid"], True)
        expect("stats on empty is total=0",
               ledger.stats()["total"], 0)

        print("\nAppend three entries:")
        e1 = ledger.append(
            {"domain": "governance", "id": "demo-1"},
            "PASS",
            [_GR("RED", "PASS"), _GR("FLOOR", "PASS"),
             _GR("BROTHERS", "PASS"), _GR("GOD", "PASS")],
        )
        expect("entry 1 seq=1", e1.seq, 1)
        expect("entry 1 prev_hash=GENESIS", e1.prev_hash, GENESIS_HASH)

        e2 = ledger.append(
            {"domain": "chemistry", "id": "demo-2"},
            "REJECT",
            [_GR("RED", "REJECT", ["unbalanced equation"])],
        )
        expect("entry 2 seq=2", e2.seq, 2)
        expect("entry 2 prev_hash=e1.entry_hash",
               e2.prev_hash, e1.entry_hash)

        e3 = ledger.append(
            {"domain": "governance", "id": "demo-3"},
            "QUARANTINE",
            [_GR("RED", "PASS"), _GR("FLOOR", "PASS"),
             _GR("BROTHERS", "QUARANTINE", ["witnesses 1/3"])],
        )
        expect("entry 3 seq=3", e3.seq, 3)
        expect("entry 3 prev_hash=e2.entry_hash",
               e3.prev_hash, e2.entry_hash)

        print("\nverify_chain:")
        chain = ledger.verify_chain()
        expect("chain valid", chain["valid"], True)
        expect("entries_checked=3", chain["entries_checked"], 3)
        expect("first_broken_seq=None", chain["first_broken_seq"], None)

        print("\nget_by_seq:")
        e = ledger.get_by_seq(2)
        expect("get_by_seq(2) returns dict", isinstance(e, dict), True)
        if isinstance(e, dict):
            expect("get_by_seq(2).seq=2", e.get("seq"), 2)
            expect("get_by_seq(2).overall=REJECT",
                   e.get("overall"), "REJECT")
        expect("get_by_seq(99) returns None",
               ledger.get_by_seq(99), None)

        print("\nget_by_packet_hash:")
        by_hash = ledger.get_by_packet_hash(e1.packet_hash)
        expect("by-hash returns list", isinstance(by_hash, list), True)
        expect("by-hash returns 1 entry for e1.hash", len(by_hash), 1)
        expect("by-hash bogus returns []",
               ledger.get_by_packet_hash("0" * 64), [])

        print("\niter_filtered (AND semantics):")
        # No filter — yields all entries newest first
        all_entries = list(ledger.iter_filtered())
        expect("no-filter yields 3", len(all_entries), 3)
        expect("newest first: first is seq=3",
               all_entries[0]["seq"], 3)

        gov = list(ledger.iter_filtered(domain="governance"))
        expect("domain=governance → 2", len(gov), 2)

        rejects = list(ledger.iter_filtered(overall="REJECT"))
        expect("overall=REJECT → 1", len(rejects), 1)
        if rejects:
            expect("REJECT entry is seq=2",
                   rejects[0]["seq"], 2)

        # Combined AND filter
        gov_pass = list(ledger.iter_filtered(domain="governance",
                                             overall="PASS"))
        expect("governance + PASS → 1", len(gov_pass), 1)

        # Limit
        limited = list(ledger.iter_filtered(limit=1))
        expect("limit=1 → 1 entry", len(limited), 1)

        # Time range — filter that matches all
        now = int(time.time())
        recent_all = list(ledger.iter_filtered(since_epoch=now - 3600,
                                               until_epoch=now + 3600))
        expect("recent time range yields 3", len(recent_all), 3)

        # Time range — filter that matches none
        none = list(ledger.iter_filtered(since_epoch=now + 1000,
                                         until_epoch=now + 2000))
        expect("future time range yields 0", len(none), 0)

        print("\nstats:")
        s = ledger.stats()
        expect("stats.total=3", s["total"], 3)
        expect("stats.by_overall has REJECT=1",
               s["by_overall"].get("REJECT"), 1)
        expect("stats.by_overall has QUARANTINE=1",
               s["by_overall"].get("QUARANTINE"), 1)
        expect("stats.by_overall has PASS=1",
               s["by_overall"].get("PASS"), 1)
        expect("stats.by_domain has governance=2",
               s["by_domain"].get("governance"), 2)
        expect("stats.by_domain has chemistry=1",
               s["by_domain"].get("chemistry"), 1)


    print(f"\n  {PASS} passed, {FAIL} failed")
    sys.exit(0 if FAIL == 0 else 1)
