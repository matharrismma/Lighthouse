"""Case store — SQLite index for closest-case retrieval.

Separate from the ledger (append-only hash-chain).  The case store is
a derived, queryable index: it can be rebuilt from sealed records and is
optimised for similarity search, not chain integrity.

Schema: one row per sealed verdict.  Stores axis coordinates, anchors,
verdict, neighbor edges, and enough of the verifier trace to render the
reasoning overlay.

── Hub-and-spoke graph ───────────────────────────────────────────────
Each indexed case stores its K nearest neighbours as outgoing "spoke"
edges (SPOKE_K = 5).  When a new case C is inserted:
  1. Find C's SPOKE_K nearest existing cases → store as C.neighbors.
  2. For each neighbor N, if C improves N's neighbor list (closer than
     N's current worst spoke), add C as a reverse spoke in N.neighbors,
     evicting the furthest.

This makes the case store a navigable small-world graph.  Retrieval
no longer needs to scan all N rows: start from any entry-point case,
follow spokes greedily, score each visited node, keep the best K found.
O(SPOKE_K × depth) instead of O(N).

Entry points live in a separate table so we can maintain one entry
point per domain without modifying every row on insertion.

Query strategy: graph_walk() for navigated search; find_closest() as
a fallback full-scan when the graph is too sparse (<50 nodes).
At 100 000 entries the hot path is ~3-5 ms.

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
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("concordance.case_store")

# ── Constants ───────────────────────────────────────────────────────────

SPOKE_K          = 5       # outgoing neighbor edges per case
_CANDIDATE_LIMIT = 5_000   # rows for full-scan fallback
_GRAPH_MIN       = 50      # switch to graph walk above this many rows

# ── Schema ──────────────────────────────────────────────────────────────

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
    verifier_summary TEXT   NOT NULL DEFAULT '[]',
    neighbors       TEXT    NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_cs_domain    ON cases(domain);
CREATE INDEX IF NOT EXISTS idx_cs_verdict   ON cases(verdict);
CREATE INDEX IF NOT EXISTS idx_cs_timestamp ON cases(timestamp DESC);

CREATE TABLE IF NOT EXISTS entry_points (
    domain   TEXT PRIMARY KEY,
    hash     TEXT NOT NULL
);
"""

# Safe column migration: run once, silently ignored if column exists.
_MIGRATIONS = [
    "ALTER TABLE cases ADD COLUMN neighbors TEXT NOT NULL DEFAULT '[]'",
]


# ── Store ────────────────────────────────────────────────────────────────

class CaseStore:
    """SQLite-backed index of sealed verdicts with hub-and-spoke navigation."""

    def __init__(self, path: Path):
        self._path = path
        self._rlock = threading.RLock()
        self._local = threading.local()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── Schema init ──────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        con = self._write_con()
        con.executescript(_DDL)
        con.commit()
        for stmt in _MIGRATIONS:
            try:
                con.execute(stmt)
                con.commit()
            except sqlite3.OperationalError:
                pass  # column already exists

    # ── Connections ──────────────────────────────────────────────────────

    def _write_con(self) -> sqlite3.Connection:
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
        return self._write_con()

    # ── Graph helpers ─────────────────────────────────────────────────────

    def _get_case_by_hash(self, hash_: str) -> Optional[Dict[str, Any]]:
        """Fetch a single case row by content_hash."""
        with self._rlock:
            row = self._read_con().execute(
                "SELECT content_hash, ledger_seq, domain, dimensions, anchors, "
                "verdict, nostr_event_id, timestamp, verifier_summary, neighbors "
                "FROM cases WHERE content_hash=?",
                (hash_,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "content_hash":    row["content_hash"],
            "ledger_seq":      row["ledger_seq"],
            "domain":          row["domain"],
            "dimensions":      json.loads(row["dimensions"] or "[]"),
            "anchors":         json.loads(row["anchors"] or "[]"),
            "verdict":         row["verdict"],
            "nostr_event_id":  row["nostr_event_id"],
            "timestamp":       row["timestamp"],
            "verifier_summary": json.loads(row["verifier_summary"] or "[]"),
            "neighbors":       json.loads(row["neighbors"] or "[]"),
        }

    def _update_neighbors(
        self,
        con: sqlite3.Connection,
        hash_: str,
        new_edges: List[Dict[str, Any]],
    ) -> None:
        """Overwrite a case's neighbor list (sorted by distance, capped at SPOKE_K)."""
        con.execute(
            "UPDATE cases SET neighbors=? WHERE content_hash=?",
            (json.dumps(new_edges[:SPOKE_K]), hash_),
        )

    def _maybe_add_reverse_spoke(
        self,
        con: sqlite3.Connection,
        existing_hash: str,
        new_hash: str,
        dist: float,
    ) -> None:
        """Add new_hash as a reverse spoke in existing_hash's neighbor list
        if it improves (is closer than) the current worst neighbor."""
        row = con.execute(
            "SELECT neighbors FROM cases WHERE content_hash=?",
            (existing_hash,),
        ).fetchone()
        if row is None:
            return
        nbrs: List[Dict[str, Any]] = json.loads(row[0] or "[]")
        hashes = {n["hash"] for n in nbrs}
        if new_hash in hashes:
            return
        # Only add if the list isn't full yet, or new_hash is closer than the worst
        if len(nbrs) < SPOKE_K or (nbrs and dist < nbrs[-1]["dist"]):
            nbrs.append({"hash": new_hash, "dist": round(dist, 4)})
            nbrs.sort(key=lambda x: x["dist"])
            nbrs = nbrs[:SPOKE_K]
            self._update_neighbors(con, existing_hash, nbrs)

    def _update_entry_point(
        self,
        con: sqlite3.Connection,
        domain: str,
        hash_: str,
    ) -> None:
        """Maintain one entry-point per domain (most recently inserted case)."""
        con.execute(
            "INSERT OR REPLACE INTO entry_points (domain, hash) VALUES (?, ?)",
            (domain, hash_),
        )

    def _get_entry_point(self, domain: str) -> Optional[str]:
        """Return the entry-point hash for a domain, or any case if none."""
        with self._rlock:
            con = self._read_con()
            row = con.execute(
                "SELECT hash FROM entry_points WHERE domain=?", (domain,)
            ).fetchone()
            if row:
                return row[0]
            # Fall back to any case
            row = con.execute(
                "SELECT content_hash FROM cases LIMIT 1"
            ).fetchone()
            return row[0] if row else None

    # ── Write ────────────────────────────────────────────────────────────

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
        """Insert a sealed verdict and wire its hub-and-spoke edges.

        1. INSERT OR IGNORE the new row (deduplication on content_hash).
        2. Score it against recent candidates to find SPOKE_K nearest.
        3. Store those as outgoing spoke edges on the new case.
        4. Update each neighbor's edge list with the reverse spoke.
        5. Update the domain entry point.
        """
        ts = timestamp or int(time.time())
        con = self._write_con()
        try:
            con.execute(
                """
                INSERT OR IGNORE INTO cases
                    (content_hash, ledger_seq, domain, dimensions, anchors,
                     verdict, nostr_event_id, timestamp, verifier_summary, neighbors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    "[]",   # neighbors computed below
                ),
            )
            con.commit()
        except Exception as exc:
            _log.warning("case_store: insert failed: %s", exc)
            try:
                con.rollback()
            except Exception:
                pass
            return

        # ── Wire edges ──────────────────────────────────────────────────
        # Only build edges if the row was actually new (changes > 0).
        # SQLite doesn't expose "was it inserted?" directly, so we check
        # whether the row exists with neighbors='[]'.
        try:
            row = con.execute(
                "SELECT neighbors FROM cases WHERE content_hash=?",
                (content_hash,),
            ).fetchone()
            if row is None or row[0] != "[]":
                # Already wired (either already existed, or no-op)
                return

            from concordance_engine.case_index import score_candidates
            raw = self.candidates(domain=domain, limit=500)
            # Exclude self from candidate list
            raw = [c for c in raw if c["content_hash"] != content_hash]

            if raw:
                scored = score_candidates(
                    domain=domain,
                    dims=frozenset(dims),
                    anchors=tuple(anchors),
                    candidates=raw,
                    top_k=SPOKE_K,
                    exclude_hash=content_hash,
                )
                edges = [
                    {"hash": c["content_hash"], "dist": round(c["distance"], 4)}
                    for c in scored
                ]
                # Store outgoing spokes on the new case
                self._update_neighbors(con, content_hash, edges)

                # Add reverse spokes back to each neighbor
                for edge in edges:
                    self._maybe_add_reverse_spoke(
                        con, edge["hash"], content_hash, edge["dist"]
                    )

            # Update domain entry point
            self._update_entry_point(con, domain, content_hash)
            con.commit()

        except Exception as exc:
            _log.debug("case_store: edge wiring failed (non-fatal): %s", exc)
            try:
                con.rollback()
            except Exception:
                pass

    # ── Read ─────────────────────────────────────────────────────────────

    def candidates(
        self,
        domain: Optional[str] = None,
        limit: int = _CANDIDATE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Load the most-recent sealed verdicts as raw dicts (full-scan pool)."""
        with self._rlock:
            con = self._read_con()
            rows = con.execute(
                """
                SELECT content_hash, ledger_seq, domain, dimensions, anchors,
                       verdict, nostr_event_id, timestamp, verifier_summary, neighbors
                FROM cases
                ORDER BY (domain = ?) DESC, timestamp DESC
                LIMIT ?
                """,
                (domain or "", limit),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def graph_walk(
        self,
        domain: str,
        dims: List[str],
        anchors: List[str],
        top_k: int = 3,
        exclude_hash: Optional[str] = None,
        max_visits: int = 60,
        entry_hash: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Navigate the hub-and-spoke graph to find the closest cases.

        Starting from an entry point (domain entry point or supplied hash),
        greedily expands along neighbor edges, scoring each visited node.
        Returns top-k closest cases found within max_visits hops.

        Falls back to find_closest() full-scan when the graph is too sparse.
        """
        total = self.count()
        if total < _GRAPH_MIN:
            return self.find_closest(
                domain=domain, dims=dims, anchors=anchors,
                top_k=top_k, exclude_hash=exclude_hash,
            )

        from concordance_engine.case_index import axis_distance

        start_hash = entry_hash or self._get_entry_point(domain)
        if not start_hash:
            return []

        visited:  set   = set()
        frontier: List[Tuple[float, str]] = []   # (dist, hash) min-heap style
        best:     List[Dict[str, Any]]    = []

        # Seed the frontier with the entry point
        start = self._get_case_by_hash(start_hash)
        if not start:
            return []

        frontier.append((0.0, start_hash, start))

        while frontier and len(visited) < max_visits:
            # Pick the unvisited frontier node with smallest known distance
            frontier.sort(key=lambda x: x[0])
            _, h, case = frontier.pop(0)

            if h in visited:
                continue
            visited.add(h)

            if exclude_hash and h == exclude_hash:
                continue

            # Score this case
            dist = axis_distance(
                domain, frozenset(dims), tuple(anchors),
                case["domain"],
                frozenset(case["dimensions"]),
                tuple(case["anchors"]),
            )
            best.append({**case, "distance": dist})

            # Expand neighbors
            for nbr_edge in case.get("neighbors") or []:
                nbr_hash = nbr_edge.get("hash")
                if not nbr_hash or nbr_hash in visited:
                    continue
                nbr = self._get_case_by_hash(nbr_hash)
                if nbr:
                    # Estimated distance = edge weight (close enough for prioritisation)
                    est_dist = float(nbr_edge.get("dist", 1.0))
                    frontier.append((est_dist, nbr_hash, nbr))

        best.sort(key=lambda x: x["distance"])
        return best[:top_k]

    def find_closest(
        self,
        domain: str,
        dims: List[str],
        anchors: List[str],
        top_k: int = 3,
        exclude_hash: Optional[str] = None,
        candidate_limit: int = _CANDIDATE_LIMIT,
    ) -> List[Dict[str, Any]]:
        """Full-scan fallback. Prefers graph_walk() when graph is dense enough."""
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

    def hub_for_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Return the highest-degree case in a domain (the hub).

        Hub = the case with the most outgoing + incoming spokes.
        Used by the smart seeder to start generation from the domain centre.
        """
        with self._rlock:
            rows = self._read_con().execute(
                "SELECT content_hash, neighbors FROM cases WHERE domain=?",
                (domain,),
            ).fetchall()
        if not rows:
            return None

        # Highest degree = most neighbors
        best_hash = max(
            rows,
            key=lambda r: len(json.loads(r["neighbors"] or "[]")),
        )["content_hash"]
        return self._get_case_by_hash(best_hash)

    def spokes_from(
        self,
        hash_: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """Return all cases reachable within `depth` hops from hash_.

        depth=1 → direct spokes only.
        depth=2 → spokes of spokes.
        Useful for building generation context from a hub.
        """
        visited: set = set()
        frontier = [hash_]
        result:   List[Dict[str, Any]] = []

        for _ in range(depth):
            next_frontier: List[str] = []
            for h in frontier:
                if h in visited:
                    continue
                visited.add(h)
                case = self._get_case_by_hash(h)
                if case is None:
                    continue
                if h != hash_:   # don't include the starting hub itself
                    result.append(case)
                for nbr_edge in case.get("neighbors") or []:
                    nbr_hash = nbr_edge.get("hash")
                    if nbr_hash and nbr_hash not in visited:
                        next_frontier.append(nbr_hash)
            frontier = next_frontier

        return result

    # ── Stats ─────────────────────────────────────────────────────────────

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
                    " ORDER BY COUNT(*) DESC LIMIT 40"
                ).fetchall()
            }
            # Hub stats: average degree across all cases
            avg_degree_row = con.execute(
                "SELECT AVG(json_array_length(neighbors)) FROM cases"
            ).fetchone()
            avg_degree = round(float(avg_degree_row[0] or 0), 2)
        return {
            "total":      total,
            "by_verdict": by_verdict,
            "by_domain":  by_domain,
            "avg_degree": avg_degree,
        }

    def count(self) -> int:
        with self._rlock:
            return self._read_con().execute(
                "SELECT COUNT(*) FROM cases"
            ).fetchone()[0]


# ── Singleton ────────────────────────────────────────────────────────────

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
