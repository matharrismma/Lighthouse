"""person_identity.py — the one identity the whole engine resolves a PERSON by.

The capability model (no passwords): possession of a high-entropy id IS the key,
exactly like the /keep token. Two kinds of person:

  * the OPERATOR — localhost / an allowlisted keep IP / a keep session cookie.
    Resolves to the node's user_identity. Wins whenever present.
  * a HOUSEHOLD — a remote visitor carrying a NHHousehold capability id
    (`hh_<16hex>`, 64-bit crypto-random) in an `X-Household-Id` header or `?hh=`.

`person_id(request)` returns whichever applies (operator first), or None when the
request carries no identity at all.

Why this module exists: the Shepherd is the per-user relationship, and a person
touches the engine through several surfaces — the funnel (cards keyed by person
id) and the four-gates walk (coach_journal, keyed by a separate client-side
`visitor_id`). To let the Shepherd's memory span BOTH, we keep a tiny identity
graph: a person id <-> walk visitor_id link. The walk endpoints record the link
(server-side, from the same person resolution); the funnel reads it to recall a
person's prior walks beside their cards. No client migration, no key change — all
existing walk data is preserved, the bridge is additive.

Storage: append-only JSONL at data/identity/walk_links.jsonl (the project's
ledger pattern). Reads dedupe. No PII — both ids are opaque.

Scribe keeps the door and the identity. The keeping is the substrate.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parent.parent
KEEP_ALLOWED = REPO / "data" / "keep_allowed_ips.txt"
KEEP_SESSIONS = REPO / "data" / "keep" / "sessions.json"
_LINKS_DIR = REPO / "data" / "identity"
_LINKS_FILE = _LINKS_DIR / "walk_links.jsonl"

# A household capability id: hh_ + 16 lowercase hex (8 bytes crypto-random).
_HH_RE = re.compile(r"^hh_[0-9a-f]{16}$")
# A walk visitor id (coach_journal): 8-32 lowercase hex. Same shape as there.
_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
# A person id is either the operator id (alnum, from user_identity) or an hh id.
_PERSON_RE = re.compile(r"^[A-Za-z0-9_\-]{4,64}$")


# ── Who is this person? ──────────────────────────────────────────────────────
def owner_id() -> str:
    """The operator/owner. Single-user node identity today."""
    try:
        from concordance_engine.user_identity import get_user_id
        return get_user_id()
    except Exception:
        return "operator"


def client_ip(request) -> str:
    try:
        return (request.headers.get("cf-connecting-ip")
                or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
                or (request.client.host if request.client else ""))
    except Exception:
        return ""


def is_owner(request) -> bool:
    """True if the requester is the owner/operator: localhost, an allowlisted
    /keep IP, or a valid /keep session cookie. (Single-user model.)"""
    ip = client_ip(request)
    if ip in ("127.0.0.1", "::1", "localhost", ""):
        return True
    try:
        if KEEP_ALLOWED.exists():
            for line in KEEP_ALLOWED.read_text(encoding="utf-8").splitlines():
                line = line.split("#", 1)[0].strip()
                if line and line == ip:
                    return True
    except Exception:
        pass
    try:
        cookie = request.cookies.get("nh_keep_session", "")
        if cookie and KEEP_SESSIONS.exists():
            sess = json.loads(KEEP_SESSIONS.read_text(encoding="utf-8"))
            e = sess.get(cookie)
            if e and int(e.get("expires_ts", 0)) > int(time.time()):
                return True
    except Exception:
        pass
    return False


def household_id(request) -> Optional[str]:
    """A valid household capability id from the request, or None."""
    try:
        h = (request.headers.get("x-household-id")
             or request.query_params.get("hh") or "").strip()
    except Exception:
        h = ""
    return h if _HH_RE.match(h) else None


def person_id(request) -> Optional[str]:
    """The requesting person. The OPERATOR (localhost / keep) wins when present so
    the operator always lands on their own shelf even if their browser also carries
    a household capability id; a genuine remote household user is never an owner, so
    they fall through to their household id. None = no identity (existence hidden)."""
    if is_owner(request):
        return owner_id()
    return household_id(request)


def valid_visitor_id(vid: str) -> bool:
    return isinstance(vid, str) and bool(_VISITOR_RE.match(vid.strip().lower()))


def valid_person_id(pid: str) -> bool:
    return isinstance(pid, str) and bool(_PERSON_RE.match(pid.strip()))


# ── The identity graph: person <-> walk visitor_id ───────────────────────────
def link(person: str, visitor_id: str) -> bool:
    """Record that `visitor_id` (a walk identity) belongs to `person`. Append-only,
    deduped — repeated calls with the same pair are no-ops. Lets the Shepherd find
    a person's walks across devices. Returns True if a NEW link was written."""
    if not person or not visitor_id:
        return False
    person = person.strip()
    visitor_id = visitor_id.strip().lower()
    if not valid_person_id(person) or not valid_visitor_id(visitor_id):
        return False
    # Don't link a person to themselves' own id space pointlessly: a household id
    # is not a visitor id (different shape), so no collision to guard.
    if (person, visitor_id) in _all_pairs():
        return False
    try:
        _LINKS_DIR.mkdir(parents=True, exist_ok=True)
        with _LINKS_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"person": person, "visitor_id": visitor_id,
                                 "ts": int(time.time())}, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _all_pairs() -> set:
    out = set()
    if not _LINKS_FILE.exists():
        return out
    try:
        with _LINKS_FILE.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                p, v = rec.get("person"), rec.get("visitor_id")
                if p and v:
                    out.add((p, v))
    except OSError:
        return out
    return out


def visitors_for(person: str, limit: int = 24) -> List[str]:
    """All walk visitor_ids linked to this person (most-recent-first by file order,
    bounded). The funnel uses this to gather a person's walks for recall."""
    if not person or not valid_person_id(person.strip()):
        return []
    person = person.strip()
    seen: List[str] = []
    for (p, v) in _all_pairs():
        if p == person and v not in seen:
            seen.append(v)
    return seen[:limit]
