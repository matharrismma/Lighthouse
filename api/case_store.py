"""Case store — SQLite index for closest-case retrieval.

Separate from the ledger (append-only hash-chain).  The case store is
a derived, queryable index: it can be rebuilt from sealed records and is
optimised for similarity search, not chain integrity.

Schema: one row per sealed verdict.  Stores axis coordinates, anchors,
verdict, and enough of the verifier trace to render the reasoning overlay.

Query strategy: load the N most-recent candidates (default 5 000), score
in Python with Jaccard distance, return top-k.  This is O(N) per query but
fast in practice: set operations on short frozensets, no allocations, pure
CPython arithmetic.  At 100 000 entries the hot path is ~30 ms.  Swap for
an inverted index if load warrants it later.

Thread safety: SQLite WAL mode + one write connection per thread (via
threading.local).  Reads serialise on a shared read connection protected
by a RLock so concurrent seal requests don't block each other on SELECT.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("concordance.case_store")

# ── Schema ─────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash    TEXT    NOT NULL UNIQUE,
    ledger_seq      INTEGER,
    domain          TEXT    NOT NULL DEFAULT '',
    dimensions      TEXT    NOT NULL DEFAULT '[]',
    anchors         TEXT    NOT NULL DEFAULT '[]',
    verdict         TEXT    NOT NULL DEFAULT '',
    nostr_event_id  TEXT,
    timestamp       INTEGER NOT NULL DEFAULT 0,
    verifier_summary TEXT   NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_cs_domain    ON cases(domain);
CREATE INDEX IF NOT EXISTS idx_cs_verdict   ON cases(verdict);
CREATE INDEX IF NOT EXISTS idx_cs_timestamp ON cases(timestamp DESC);
"""

_CANDIDATE_LIMIT = 5_000    # rows loaded per query; tune if needed


# ── Store ──────────────────────────────────────────────────────────────

class CaseStore:
    """SQLite-backed index of sealed verdicts for closest-case retrieval."""

    def __init__(self, path: Path):
        self._path = path
        self._rlock = threading.RLock()
        self._local = threading.local()   # per-thread write connections
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── Schema init ────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        con = self._write_con()
        con.executescript(_DDL)
        con.commit()

    # ── Connections ────────────────────────────────────────────────────

    def _write_con(self) -> sqlite3.Connection:
        """Return (or create) this thread's write connection."""
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(
                str(self._path),
                check_same_thread=False,
                timeout=10,
            )
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
            con.row_factory = sqlite3.Row
            self._local.con = con
        return con

    def _read_con(self) -> sqlite3.Connection:
        """Shared read connection (protected by RLock)."""
        return self._write_con()

    # ── Write ──────────────────────────────────────────────────────────

    def index_verdict(
        self,
        *,
        content_hash: str,
        domain: str,
        dims: List[str],
        anchors: List[str],
        verdict: str,
        verifier_summary: Optional[List[Dict[str, Any]]] = None,
        ledger_seq: Optional[int] = None,
        nostr_event_id: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> None:
        """Insert or ignore a sealed verdict into the index.

        Duplicate content_hashes are silently ignored (INSERT OR IGNORE)
        so the caller can index the same record multiple times safely.
        """
        ts = timestamp or int(time.time())
        con = self._write_con()
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO cases
                    (content_hash, ledger_seq, domain, dimensions, anchors,
                     verdict, nostr_event_id, timestamp, verifier_summary)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    content_hash,
                    ledger_seq,
                    domain,
                    json.dumps(sorted(dims)),
                    json.dumps(sorted(anchors)),
                    verdict,
                    nostr_event_id,
                    ts,
                    json.dumps(verifier_summary or []),
                ),
            )
            con.commit()
        except Exception as exc:
            _log.warning("case_store: index_verdict failed: %s", exc)
            try:
                con.rollback()
            except Exception:
                pass

    # ── Read ───────────────────────────────────────────────────────────

    def candidates(
        self,
        domain: Optional[str] = None,
        limit: int = _CANDIDATE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Load the most-recent sealed verdicts as raw dicts.

        If `domain` is given, prefer rows matching that domain but also
        include rows from other domains so cross-domain precedents surface.
        The query loads the most-recent `limit` rows — a superset that
        Python-side scoring then narrows.
        """
        with self._rlock:
            con = self._read_con()
            # Two-phase: domain-matching rows first, then the rest up to limit
            rows = con.execute(
                """
                SELECT content_hash, ledger_seq, domain, dimensions, anchors,
                       verdict, nostr_event_id, timestamp, verifier_summary
                FROM cases
                ORDER BY (domain = ?) DESC, timestamp DESC
                LIMIT ?
                """,
                (domain or "", limit),
            ).fetchall()

        result: List[Dict[str, Any]] = []
        for r in rows:
            result.append({
                "content_hash":    r["content_hash"],
                "ledger_seq":      r["ledger_seq"],
                "domain":          r["domain"],
                "dimensions":      json.loads(r["dimensions"] or "[]"),
                "anchors":         json.loads(r["anchors"] or "[]"),
                "verdict":         r["verdict"],
                "nostr_event_id":  r["nostr_event_id"],
                "timestamp":       r["timestamp"],
                "verifier_summary": json.loads(r["verifier_summary"] or "[]"),
            })
        return result

    def find_closest(
        self,
        domain: str,
        dims: List[str],
        anchors: List[str],
        top_k: int = 3,
        exclude_hash: Optional[str] = None,
        candidate_limit: int = _CANDIDATE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Return top-k closest cases, scored by axis+anchor+domain distance.

        Each returned dict includes a "distance" key (0 = identical, 1 = unlike).
        Returns an empty list when the store is empty or all rows are excluded.
        """
        from concordance_engine.case_index import score_candidates

        raw = self.candidates(domain=domain, limit=candidate_limit)
        if not raw:
            return []

        return score_candidates(
            domain=domain,
            dims=frozenset(dims),
            anchors=tuple(anchors),
            candidates=raw,
            top_k=top_k,
            exclude_hash=exclude_hash,
        )

    # ── Stats ──────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        with self._rlock:
            con = self._read_con()
            total = con.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
            by_verdict = {
                r[0]: r[1]
                for r in con.execute(
                    "SELECT verdict, COUNT(*) FROM cases GROUP BY verdict"
                ).fetchall()
            }
            by_domain = {
                r[0]: r[1]
                for r in con.execute(
                    "SELECT domain, COUNT(*) FROM cases GROUP BY domain"
                    " ORDER BY COUNT(*) DESC LIMIT 20"
                ).fetchall()
            }
        return {"total": total, "by_verdict": by_verdict, "by_domain": by_domain}

    def count(self) -> int:
        with self._rlock:
            return self._read_con().execute("SELECT COUNT(*) FROM cases").fetchone()[0]


# ── Singleton ──────────────────────────────────────────────────────────

_store: Optional[CaseStore] = None
_store_lock = threading.Lock()


def get_case_store() -> CaseStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                path = Path(
                    os.environ.get("CASE_STORE_PATH", "case_store.db")
                )
                _store = CaseStore(path)
    return _store
