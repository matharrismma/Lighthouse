"""
Community participation primitives — contributors, badges, activity log.

Posture: keep, do not decide. The engine records what survived; the
community system here records what each contributor's work looked like
as it moved through the gates. Badges are not gamification; they are
attestations of demonstrated alignment, the same way the ledger is
an attestation of demonstrated correctness.

Design constraints:
- Append-only storage (matches the rest of the engine's substrate).
- No email, no password — the handle is a public pseudonym, the
  optional Ed25519 user pubkey is the cryptographic anchor.
- Read-only endpoints are unlimited; write endpoints are rate-limited
  by the existing token-bucket gate.
- Earning is structural. You earn `witness:first-witness` by giving a
  witness signal, not by claiming it.
"""
from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).parent.parent
_DATA_DIR = _REPO_ROOT / "data"
_CONTRIB_DIR = _DATA_DIR / "contributors"
_CONTRIB_INDEX = _CONTRIB_DIR / "index.jsonl"
_ACTIVITY_DIR = _DATA_DIR / "activity"

_CONTRIB_DIR.mkdir(parents=True, exist_ok=True)
_ACTIVITY_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()

# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
_HANDLE_RE = re.compile(r"^[a-z][a-z0-9_-]{2,31}$")
_DISPLAY_RE = re.compile(r"^[\w \-.,'—]{1,64}$")  # generous but bounded


def is_valid_handle(handle: str) -> bool:
    return bool(handle) and bool(_HANDLE_RE.match(handle))


# --------------------------------------------------------------------------
# Tier ladder
# --------------------------------------------------------------------------
TIERS: List[Dict[str, Any]] = [
    {
        "id": "visitor",
        "rank": 0,
        "label": "Visitor",
        "summary": "Has claimed a handle but has not yet entered wisdom into "
                   "the engine. May read, may run polymathic, may see the "
                   "dashboard — but cannot serve as witness for others.",
    },
    {
        "id": "brother",
        "rank": 1,
        "label": "Brother",
        "summary": "Has entered wisdom into the engine — proposed, attributed "
                   "a polymathic run, attested for another, or confessed. A "
                   "brother can serve as a witness for others (the BROTHERS "
                   "gate requires brothers, not visitors). "
                   "Mt 18:16; Dt 19:15.",
    },
    {
        "id": "contributor",
        "rank": 2,
        "label": "Contributor",
        "summary": "A brother whose wisdom has been accepted into the "
                   "Almanac's canon by the curator. Their drafts carry weight "
                   "in the curation queue.",
    },
    {
        "id": "curator",
        "rank": 3,
        "label": "Curator",
        "summary": "Appointed by the operator. Reviews and accepts drafts, "
                   "shapes the Almanac canon. Holds the keys to the keeping.",
    },
]
TIER_BY_ID = {t["id"]: t for t in TIERS}


def has_entered_wisdom(stats: Dict[str, Any]) -> bool:
    """True if the contributor has contributed any wisdom to the engine.

    Per the canon: entering wisdom into the engine makes you a brother.
    Any one of the following counts:
      - submitted an almanac proposal (proposals_submitted >= 1)
      - ran an attributed polymathic (polymathic_runs >= 1)
      - witnessed another's submission (witnesses_given >= 1)
      - confessed an error on a prior packet (confessions >= 1)

    Mere registration of a handle does not count — claiming a name is
    not the same as testifying."""
    return (
        int(stats.get("proposals_submitted", 0)) >= 1
        or int(stats.get("polymathic_runs", 0)) >= 1
        or int(stats.get("witnesses_given", 0)) >= 1
        or int(stats.get("confessions", 0)) >= 1
    )


def tier_for_stats(stats: Dict[str, Any], curator: bool = False) -> str:
    """Promote-only ladder. Once a contributor reaches a tier, they stay.

    Per Lighthouse Canon: a brother is one who has entered wisdom into
    the engine. A brother can serve as a witness. Visitors with handles
    who haven't entered wisdom yet remain visitors until they do.
    """
    if curator:
        return "curator"
    if int(stats.get("proposals_accepted", 0)) >= 1:
        return "contributor"
    if has_entered_wisdom(stats):
        return "brother"
    return "visitor"


# --------------------------------------------------------------------------
# Badge catalog
# --------------------------------------------------------------------------
BADGES: List[Dict[str, Any]] = [
    {
        "id": "visitor:registered",
        "label": "Visitor",
        "summary": "Picked up a handle. Has not yet entered wisdom into the "
                   "engine. A name claimed, not a testimony given.",
        "tier_unlock": "visitor",
    },
    {
        "id": "brother:first-wisdom",
        "label": "Brother",
        "summary": "Entered wisdom into the engine for the first time — "
                   "proposed, attributed a polymathic run, witnessed for "
                   "another, or confessed. Per the canon: this is what "
                   "makes a brother. Mt 18:16; Dt 19:15.",
        "tier_unlock": "brother",
    },
    {
        "id": "witness:first-witness",
        "label": "First Signal",
        "summary": "Gave their first witness signal on another brother's "
                   "submission. The witness function (not a tier) — brothers "
                   "performing the work of attestation.",
    },
    {
        "id": "witness:three-fold",
        "label": "Three-fold",
        "summary": "Witnessed for three different brothers. Reliable in the "
                   "BROTHERS-gate function.",
    },
    {
        "id": "contributor:first-proposal",
        "label": "First Draft",
        "summary": "Submitted their first almanac proposal. The engine ran "
                   "the math; the curator decides if it joins the canon.",
    },
    {
        "id": "contributor:first-accepted",
        "label": "Contributor",
        "summary": "First proposal accepted into the almanac. Their voice is "
                   "in the book.",
        "tier_unlock": "contributor",
    },
    {
        "id": "contributor:five-accepted",
        "label": "Five-Fold",
        "summary": "Five accepted entries. Their pattern is recognizable in "
                   "the almanac's voice.",
    },
    {
        "id": "polymathic:first-run",
        "label": "First Polymathic",
        "summary": "Ran their first polymathic check across multiple domains.",
    },
    {
        "id": "polymathic:concordant",
        "label": "Concordant",
        "summary": "Ran a polymathic that came back CONCORDANT — every fired "
                   "domain agreed.",
    },
    {
        "id": "pioneer:early",
        "label": "Pioneer",
        "summary": "Registered while the dashboard was still finding its feet. "
                   "Joined before contributor #50.",
    },
    {
        "id": "curator:appointed",
        "label": "Curator",
        "summary": "Appointed by the operator. Holds the keys to the almanac.",
        "tier_unlock": "curator",
    },
]
BADGE_BY_ID = {b["id"]: b for b in BADGES}


def awardable_badges(stats: Dict[str, Any], curator: bool, joined_seq: int) -> List[str]:
    """Return badge ids this contributor qualifies for, given current stats.
    Idempotent: callers should diff against already-earned badges."""
    earned: List[str] = ["visitor:registered"]  # everyone with a handle
    if has_entered_wisdom(stats):
        earned.append("brother:first-wisdom")
    if int(stats.get("witnesses_given", 0)) >= 1:
        earned.append("witness:first-witness")
    if int(stats.get("witnesses_given", 0)) >= 3:
        earned.append("witness:three-fold")
    if int(stats.get("proposals_submitted", 0)) >= 1:
        earned.append("contributor:first-proposal")
    if int(stats.get("proposals_accepted", 0)) >= 1:
        earned.append("contributor:first-accepted")
    if int(stats.get("proposals_accepted", 0)) >= 5:
        earned.append("contributor:five-accepted")
    if int(stats.get("polymathic_runs", 0)) >= 1:
        earned.append("polymathic:first-run")
    if int(stats.get("polymathic_concordant", 0)) >= 1:
        earned.append("polymathic:concordant")
    if joined_seq <= 50:
        earned.append("pioneer:early")
    if curator:
        earned.append("curator:appointed")
    return earned


# --------------------------------------------------------------------------
# Contributor storage
# --------------------------------------------------------------------------
def _contrib_path(handle: str) -> Path:
    if not is_valid_handle(handle):
        raise ValueError(f"invalid handle: {handle!r}")
    return _CONTRIB_DIR / f"{handle}.json"


def _empty_stats() -> Dict[str, Any]:
    return {
        "proposals_submitted": 0,
        "proposals_accepted": 0,
        "witnesses_given": 0,
        "witnesses_received": 0,
        "polymathic_runs": 0,
        "polymathic_concordant": 0,
        "confessions": 0,
    }


def load_contributor(handle: str) -> Optional[Dict[str, Any]]:
    """Return the full contributor record or None."""
    if not is_valid_handle(handle):
        return None
    path = _contrib_path(handle)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _save_contributor(record: Dict[str, Any]) -> None:
    path = _contrib_path(record["handle"])
    path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _next_join_seq() -> int:
    if not _CONTRIB_INDEX.exists():
        return 1
    n = 0
    for line in _CONTRIB_INDEX.read_text("utf-8", errors="replace").splitlines():
        if line.strip():
            n += 1
    return n + 1


def register_contributor(
    handle: str,
    display_name: str = "",
    bio: str = "",
    user_pubkey: str = "",
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """Create a contributor record. Returns (ok, message, record)."""
    if not is_valid_handle(handle):
        return False, "handle must be 3-32 chars, lowercase letters, digits, underscore, hyphen, starting with a letter", None
    display_name = (display_name or "").strip()[:64]
    if display_name and not _DISPLAY_RE.match(display_name):
        return False, "display_name has invalid characters", None
    bio = (bio or "").strip()[:280]

    with _lock:
        existing = load_contributor(handle)
        if existing is not None:
            return False, f"handle {handle!r} is already taken", None

        seq = _next_join_seq()
        now = int(time.time())
        record = {
            "handle": handle,
            "join_seq": seq,
            "joined_at": now,
            "joined_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            "display_name": display_name or handle,
            "bio": bio,
            "user_pubkey": (user_pubkey or "").strip()[:120],
            "tier": "visitor",
            "stats": _empty_stats(),
            "badges": [
                {"id": "visitor:registered", "earned_at": now}
            ],
            "curator": False,
        }

        _save_contributor(record)
        with open(_CONTRIB_INDEX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "handle": handle, "joined_at": now, "join_seq": seq,
            }, ensure_ascii=False) + "\n")

    log_activity({
        "kind": "register",
        "handle": handle,
        "display_name": record["display_name"],
        "join_seq": seq,
    })
    # Pioneer badge check (covers contributors who registered while
    # below the threshold; reapplied on first stats touch).
    _refresh_badges(record)
    return True, "registered", record


def _refresh_badges(record: Dict[str, Any]) -> Dict[str, Any]:
    """Apply badge rules; new badges get an earned_at timestamp."""
    earned_ids = {b["id"] for b in record.get("badges", [])}
    qualifying = awardable_badges(
        record.get("stats", {}),
        record.get("curator", False),
        record.get("join_seq", 9_999_999),
    )
    new_now = int(time.time())
    new_added: List[str] = []
    for bid in qualifying:
        if bid not in earned_ids:
            record["badges"].append({"id": bid, "earned_at": new_now})
            new_added.append(bid)
    record["tier"] = tier_for_stats(record.get("stats", {}), record.get("curator", False))
    if new_added:
        _save_contributor(record)
        for bid in new_added:
            log_activity({
                "kind": "badge",
                "handle": record["handle"],
                "badge_id": bid,
                "tier": record["tier"],
            })
    return record


def bump_stat(handle: str, stat: str, by: int = 1) -> Optional[Dict[str, Any]]:
    """Increment a stat counter and re-evaluate badges."""
    if not is_valid_handle(handle):
        return None
    with _lock:
        record = load_contributor(handle)
        if record is None:
            return None
        record.setdefault("stats", _empty_stats())
        record["stats"][stat] = int(record["stats"].get(stat, 0)) + int(by)
        _save_contributor(record)
    return _refresh_badges(record)


def list_contributors(
    sort: str = "rank",
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Return contributor public profiles sorted by the given key.

    sort:
      'rank'      — by tier rank desc, then total badges desc
      'recent'    — most recently joined first
      'witnesses' — most witness signals given
      'proposals' — most proposals accepted
      'polymathic'— most polymathic runs
    """
    out: List[Dict[str, Any]] = []
    if not _CONTRIB_DIR.exists():
        return out
    for f in _CONTRIB_DIR.glob("*.json"):
        try:
            r = json.loads(f.read_text("utf-8"))
        except Exception:
            continue
        out.append(public_profile(r))
    if sort == "recent":
        out.sort(key=lambda r: r.get("joined_at", 0), reverse=True)
    elif sort == "witnesses":
        out.sort(key=lambda r: r["stats"].get("witnesses_given", 0), reverse=True)
    elif sort == "proposals":
        out.sort(key=lambda r: r["stats"].get("proposals_accepted", 0), reverse=True)
    elif sort == "polymathic":
        out.sort(key=lambda r: r["stats"].get("polymathic_runs", 0), reverse=True)
    else:  # rank
        out.sort(key=lambda r: (
            -TIER_BY_ID.get(r.get("tier", "visitor"), {"rank": 0})["rank"],
            -len(r.get("badges", [])),
            -r["stats"].get("proposals_accepted", 0),
            -r["stats"].get("witnesses_given", 0),
        ))
    return out[offset:offset + limit]


def public_profile(record: Dict[str, Any]) -> Dict[str, Any]:
    """Strip non-public fields. user_pubkey kept (it's a public key)."""
    return {
        "handle": record.get("handle"),
        "display_name": record.get("display_name") or record.get("handle"),
        "bio": record.get("bio", ""),
        "tier": record.get("tier", "visitor"),
        "tier_label": TIER_BY_ID.get(record.get("tier", "visitor"), {}).get("label", "Visitor"),
        "join_seq": record.get("join_seq", 0),
        "joined_at": record.get("joined_at", 0),
        "joined_iso": record.get("joined_iso", ""),
        "user_pubkey": record.get("user_pubkey", ""),
        "curator": record.get("curator", False),
        "stats": record.get("stats", _empty_stats()),
        "badges": record.get("badges", []),
        "badge_count": len(record.get("badges", [])),
    }


# --------------------------------------------------------------------------
# Activity log
# --------------------------------------------------------------------------
def log_activity(event: Dict[str, Any]) -> None:
    """Append a single event to today's activity file. Never raises."""
    try:
        now = int(time.time())
        event = dict(event)
        event.setdefault("ts", now)
        event.setdefault("ts_iso", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)))
        day = time.strftime("%Y%m%d", time.gmtime(event["ts"]))
        path = _ACTIVITY_DIR / f"events-{day}.jsonl"
        with _lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_activity(days: int = 7, limit: int = 100) -> List[Dict[str, Any]]:
    """Read up to `days` of activity, newest first."""
    out: List[Dict[str, Any]] = []
    now = time.time()
    for d in range(days):
        day = time.strftime("%Y%m%d", time.gmtime(now - d * 86400))
        path = _ACTIVITY_DIR / f"events-{day}.jsonl"
        if not path.exists():
            continue
        try:
            for line in path.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
    out.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return out[:limit]


def total_contributors() -> int:
    """Total registered contributors. Cheap — just counts jsonl lines."""
    if not _CONTRIB_INDEX.exists():
        return 0
    return sum(1 for line in _CONTRIB_INDEX.read_text("utf-8", errors="replace").splitlines() if line.strip())


# --------------------------------------------------------------------------
# Witness signals — a contributor signaling that another's proposal looks sound
# --------------------------------------------------------------------------
def record_witness(
    witness_handle: str,
    proposal_id: str,
    proposal_author: str = "",
    note: str = "",
) -> Tuple[bool, str]:
    """Record a witness signal. Updates witness_given for the witness and
    witnesses_received for the author. Both must be valid handles.

    Per Lighthouse Canon: only a brother can serve as a witness — meaning
    the witness handle must have already entered wisdom into the engine
    (proposed, attributed a polymathic, witnessed before, or confessed).
    A bare-handle visitor cannot witness for others; first they must
    testify themselves. Mt 18:16; Dt 19:15."""
    if not is_valid_handle(witness_handle):
        return False, "witness handle invalid"
    if witness_handle == proposal_author:
        return False, "cannot witness your own proposal"
    rec = load_contributor(witness_handle)
    if rec is None:
        return False, "witness must be registered first"

    # BROTHERS-gate gating: visitors-with-handles cannot witness. Only
    # brothers (those who have entered wisdom) can. This grounds the
    # gate in Dt 19:15 / Mt 18:16 — two or three witnesses, each of
    # whom has demonstrated alignment themselves.
    witness_stats = rec.get("stats", {}) or {}
    if not has_entered_wisdom(witness_stats):
        return False, (
            "witness must be a brother (must have entered wisdom into the "
            "engine first — propose, run polymathic, witness, or confess). "
            "See /canon for the rule."
        )

    bump_stat(witness_handle, "witnesses_given", 1)
    if proposal_author and is_valid_handle(proposal_author):
        if load_contributor(proposal_author) is not None:
            bump_stat(proposal_author, "witnesses_received", 1)
    log_activity({
        "kind": "witness",
        "handle": witness_handle,
        "target_handle": proposal_author,
        "proposal_id": proposal_id,
        "note": (note or "")[:200],
    })
    return True, "recorded"
