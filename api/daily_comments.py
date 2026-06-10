"""Comments on the daily devotion.

Per-day append-only JSONL at data/daily_comments/<iso_date>.jsonl.
A comment carries visitor_id (opaque), optional display name, body,
timestamp. Operator can hide via tombstone.

Comments are public — anyone can read; visitor_id needed to write.
Pillar reference (mind/body/spirit/parable/protocol/almanac/devotional/sermon)
is optional so a commenter can target one part of the daily anchor.
"""
from __future__ import annotations
import json
import re
import time
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

_DIR = Path(__file__).parent.parent / "data" / "daily_comments"

_VISITOR_RE = re.compile(r"^[a-f0-9]{8,32}$")
_DATE_RE    = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NAME_RE    = re.compile(r"^[A-Za-z0-9 _\-\.']{0,80}$")
_PILLAR_KINDS = {
    "", "mind", "body", "spirit",
    "parable", "protocol", "almanac", "devotional", "sermon",
}

MAX_BODY_LEN = 2000
MAX_COMMENTS_PER_DAY = 500


def _valid_visitor_id(vid: str) -> bool:
    return bool(_VISITOR_RE.match((vid or "").strip().lower()))


def _valid_date(d: str) -> bool:
    return bool(_DATE_RE.match((d or "").strip()))


def _file_for(iso_date: str) -> Path:
    _DIR.mkdir(parents=True, exist_ok=True)
    return _DIR / f"{iso_date}.jsonl"


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def add_comment(
    *,
    iso_date: str,
    visitor_id: str,
    body: str,
    display_name: str = "",
    pillar: str = "",
    lang: str = "en",
    body_original: Optional[str] = None,
    mt_provider: Optional[str] = None,
) -> Dict[str, Any]:
    if not _valid_date(iso_date):
        raise ValueError("invalid iso_date (YYYY-MM-DD)")
    if not _valid_visitor_id(visitor_id):
        raise ValueError("invalid visitor_id")
    body = (body or "").strip()[:MAX_BODY_LEN]
    if not body:
        raise ValueError("body required")
    display_name = (display_name or "").strip()
    if display_name and not _NAME_RE.match(display_name):
        raise ValueError("display_name must be plain letters/digits/space/-_.'")
    pillar = (pillar or "").strip().lower()
    if pillar not in _PILLAR_KINDS:
        pillar = ""

    existing = list_for_day(iso_date)
    if len(existing) >= MAX_COMMENTS_PER_DAY:
        raise ValueError("daily comment cap reached")

    now = int(time.time())
    record = {
        "id": "dcm-" + _short_hash(f"{iso_date}|{visitor_id}|{body}|{now}"),
        "iso_date": iso_date,
        "logged_at": now,
        "logged_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "visitor_id": visitor_id.strip().lower(),
        "display_name": display_name,
        "pillar": pillar,
        "body": body,
        "hidden": False,
        "lang": (lang or "en").strip().lower() or "en",
    }
    if body_original:
        record["body_original"] = body_original[:MAX_BODY_LEN]
    if mt_provider:
        record["mt_provider"] = mt_provider
    path = _file_for(iso_date)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def list_for_day(iso_date: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Newest first. Hidden comments filtered out."""
    if not _valid_date(iso_date):
        return []
    path = _file_for(iso_date)
    if not path.exists():
        return []
    # Last-write-wins by id, so hidden-tombstones supersede.
    latest: Dict[str, Dict[str, Any]] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            rid = rec.get("id")
            if not rid:
                continue
            prev = latest.get(rid)
            if not prev or rec.get("logged_at", 0) >= prev.get("logged_at", 0):
                latest[rid] = rec
    except OSError:
        return []
    items = [r for r in latest.values() if not r.get("hidden")]
    items.sort(key=lambda r: r.get("logged_at", 0), reverse=True)
    return items[:limit]


def hide_comment(*, iso_date: str, comment_id: str) -> bool:
    """Operator action: tombstone a comment by appending hidden=True version."""
    items = list_for_day(iso_date, limit=10000)
    target = next((r for r in items if r.get("id") == comment_id), None)
    if not target:
        return False
    tomb = dict(target)
    tomb["hidden"] = True
    tomb["logged_at"] = int(time.time())
    tomb["logged_at_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path = _file_for(iso_date)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(tomb, ensure_ascii=False) + "\n")
    return True


def public_view(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Anonymize. No visitor_id leaked; display_name optional."""
    return {
        "id": rec.get("id"),
        "logged_at_iso": rec.get("logged_at_iso"),
        "display_name": rec.get("display_name") or "anon",
        "pillar": rec.get("pillar") or "",
        "body": rec.get("body") or "",
    }
