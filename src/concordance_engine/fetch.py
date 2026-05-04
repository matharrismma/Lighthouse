"""fetch — pull updates to the audit chain from a remote engine.

Works offline. When the remote is reachable, fetches new sealed
precedents past the last-seen seq number into a local mirror.
When the remote is unreachable, no-op (graceful, not error).

The local audit chain (api/ledger.jsonl) is the engine's *own*
record — entries written here by this instance, hash-chained.
Fetched entries from a remote engine are *not* appended to that
chain (their hash chain is the remote's, not ours). They live in
a parallel fetched/ store, one file per remote, indexed by remote
URL hash.

Per the deployment-modes doctrine: the engine runs locally; remote
fetch is the Open-mode federation pattern. In Restricted/Lockdown
modes, this module simply isn't called — the engine continues with
its own chain alone.

Per "free use, alignment to execute": fetching is read-only on the
remote — pulling sealed precedents is reading the well, which is
free. Writing your own precedents to a remote is a separate flow
(seal locally, then push, with witnesses).

## Storage layout

```
<base_dir>/
  fetched/
    <remote_slug>.jsonl   # one entry per line, in remote-seq order
    <remote_slug>.state   # JSON: {url, last_seq, last_fetched_at}
```

`<remote_slug>` is the first 8 hex chars of sha256(url). Stable
across runs; collision-resistant for any reasonable number of
remotes a single instance would track.

## Read API

`list_fetched(remote_url=None)` returns the merged view across all
fetched remotes (or one specific remote). Useful for the dawn
surface and for CLI display.

## CLI surface

`concordance fetch` (default remote from env)
`concordance fetch --remote https://...` (one-off)
`concordance fetch --status` (per-remote last_seq + age)
`concordance fetch --list [--remote URL]` (show fetched entries)
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


DEFAULT_REMOTE = os.environ.get("CONCORDANCE_FETCH_REMOTE", "https://narrowhighway.com")
DEFAULT_PAGE_SIZE = 100
FETCH_TIMEOUT = 30.0


def _default_base_dir() -> Path:
    """Where fetched data lives. Override via CONCORDANCE_DATA_DIR
    (also used by other engine subsystems)."""
    if "CONCORDANCE_DATA_DIR" in os.environ:
        return Path(os.environ["CONCORDANCE_DATA_DIR"]) / "fetched"
    return Path.home() / ".concordance" / "fetched"


def _slug_for(url: str) -> str:
    """Stable 8-char hex slug for a remote URL. Used as filename prefix."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]


@dataclass
class FetchState:
    """Per-remote fetch bookkeeping."""
    url: str
    last_seq: int = 0
    last_fetched_at: float = 0.0
    last_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "last_seq": self.last_seq,
            "last_fetched_at": self.last_fetched_at,
            "last_status": self.last_status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "FetchState":
        return cls(
            url=str(d.get("url", "")),
            last_seq=int(d.get("last_seq", 0)),
            last_fetched_at=float(d.get("last_fetched_at", 0.0)),
            last_status=str(d.get("last_status", "")),
        )


@dataclass
class FetchResult:
    """Outcome of one fetch call."""
    remote_url: str
    fetched_count: int
    new_last_seq: int
    status: str  # "ok" | "offline" | "no_new" | "error: ..."
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "remote_url": self.remote_url,
            "fetched_count": self.fetched_count,
            "new_last_seq": self.new_last_seq,
            "status": self.status,
            "elapsed_seconds": self.elapsed_seconds,
        }


# ── State persistence ─────────────────────────────────────────────


def _state_path(base_dir: Path, slug: str) -> Path:
    return base_dir / f"{slug}.state"


def _data_path(base_dir: Path, slug: str) -> Path:
    return base_dir / f"{slug}.jsonl"


def _load_state(base_dir: Path, url: str) -> FetchState:
    slug = _slug_for(url)
    p = _state_path(base_dir, slug)
    if not p.exists():
        return FetchState(url=url)
    try:
        return FetchState.from_dict(json.loads(p.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return FetchState(url=url)


def _save_state(base_dir: Path, state: FetchState) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug_for(state.url)
    p = _state_path(base_dir, slug)
    p.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")


def _append_entries(base_dir: Path, url: str, entries: Iterable[Dict[str, Any]]) -> int:
    """Append entries to the fetched file in order. Returns count appended."""
    base_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug_for(url)
    p = _data_path(base_dir, slug)
    n = 0
    with p.open("a", encoding="utf-8") as f:
        for e in entries:
            line = json.dumps(e, separators=(",", ":"))
            f.write(line + "\n")
            n += 1
    return n


# ── Network layer ─────────────────────────────────────────────────


def _http_get_json(url: str, timeout: float = FETCH_TIMEOUT) -> Dict[str, Any]:
    """Fetch a JSON document. Raises urllib errors on network/HTTP failure."""
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "concordance-fetch/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ── Public API ────────────────────────────────────────────────────


def fetch_remote(
    *,
    remote_url: Optional[str] = None,
    base_dir: Optional[Path] = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_pages: int = 100,
) -> FetchResult:
    """Fetch new precedents from `remote_url` past the last-seen seq.

    Idempotent: only fetches entries with seq > state.last_seq.
    Offline-tolerant: if the remote is unreachable, returns
    `status="offline"` without raising.
    """
    url = (remote_url or DEFAULT_REMOTE).rstrip("/")
    base = base_dir or _default_base_dir()
    state = _load_state(base, url)

    started = time.time()
    fetched: List[Dict[str, Any]] = []
    cursor = state.last_seq
    pages_drawn = 0

    while pages_drawn < max_pages:
        endpoint = f"{url}/chain/since?seq={cursor}&limit={page_size}"
        try:
            data = _http_get_json(endpoint)
        except urllib.error.URLError as exc:
            # Network unreachable, DNS failure, timeout, etc. Graceful.
            status = f"offline: {exc.reason if hasattr(exc, 'reason') else exc}"
            state.last_status = status
            state.last_fetched_at = time.time()
            _save_state(base, state)
            return FetchResult(
                remote_url=url,
                fetched_count=len(fetched),
                new_last_seq=state.last_seq,
                status=status,
                elapsed_seconds=time.time() - started,
            )
        except urllib.error.HTTPError as exc:
            status = f"error: HTTP {exc.code}"
            state.last_status = status
            state.last_fetched_at = time.time()
            _save_state(base, state)
            return FetchResult(
                remote_url=url,
                fetched_count=len(fetched),
                new_last_seq=state.last_seq,
                status=status,
                elapsed_seconds=time.time() - started,
            )
        except (json.JSONDecodeError, ValueError) as exc:
            status = f"error: malformed response: {exc}"
            state.last_status = status
            state.last_fetched_at = time.time()
            _save_state(base, state)
            return FetchResult(
                remote_url=url,
                fetched_count=len(fetched),
                new_last_seq=state.last_seq,
                status=status,
                elapsed_seconds=time.time() - started,
            )

        entries = data.get("entries") or []
        if not entries:
            break

        # Tag each entry with the origin so downstream consumers can
        # tell our chain from a fetched one.
        for e in entries:
            e.setdefault("_origin", url)
            e.setdefault("_fetched_at", time.time())
            fetched.append(e)
            cursor = max(cursor, int(e.get("seq", 0)))

        pages_drawn += 1
        # If the server returned fewer than we asked, we're at the end.
        if len(entries) < page_size:
            break

    if fetched:
        _append_entries(base, url, fetched)

    state.last_seq = cursor
    state.last_fetched_at = time.time()
    state.last_status = "ok" if fetched else "no_new"
    _save_state(base, state)

    return FetchResult(
        remote_url=url,
        fetched_count=len(fetched),
        new_last_seq=cursor,
        status=state.last_status,
        elapsed_seconds=time.time() - started,
    )


def list_fetched(
    *,
    remote_url: Optional[str] = None,
    base_dir: Optional[Path] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Read fetched entries, newest first.

    If `remote_url` is given, restricted to that remote. Otherwise
    returns the merged view across all known remotes.
    """
    base = base_dir or _default_base_dir()
    if not base.exists():
        return []

    if remote_url:
        slug = _slug_for(remote_url.rstrip("/"))
        files = [_data_path(base, slug)]
    else:
        files = sorted(base.glob("*.jsonl"))

    out: List[Dict[str, Any]] = []
    for p in files:
        if not p.exists():
            continue
        try:
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue

    # Newest first by fetched_at, then seq.
    out.sort(key=lambda e: (e.get("_fetched_at") or 0, e.get("seq") or 0),
             reverse=True)
    if limit is not None:
        out = out[:limit]
    return out


def all_states(*, base_dir: Optional[Path] = None) -> List[FetchState]:
    """Read state files for every known remote. Used by --status."""
    base = base_dir or _default_base_dir()
    if not base.exists():
        return []
    out: List[FetchState] = []
    for p in sorted(base.glob("*.state")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            out.append(FetchState.from_dict(d))
        except (OSError, json.JSONDecodeError):
            continue
    return out


__all__ = [
    "DEFAULT_REMOTE",
    "FetchState",
    "FetchResult",
    "fetch_remote",
    "list_fetched",
    "all_states",
]
