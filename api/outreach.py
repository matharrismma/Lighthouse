"""outreach.py — Partnership outreach tracker (LOOP 10).

The operator drafts outbound emails from `outreach/letter_*.md` templates, sends
them by hand, then logs each contact + status change here. The dashboard at
`/outreach.html` reads these endpoints to show the current state of every
conversation.

State machine for each target:
    prospect -> contacted -> in-discussion -> declined | signed

No mass-mail; every entry is one named person at one named target. The operator
is the only one who logs entries (Phase 1 is unauthenticated for local dev; the
file lives under `data/outreach/` and is never exposed for write through any
public form).

Storage:
    data/outreach/targets.json      registry of every target (one row per org)
    data/outreach/log.jsonl         append-only history (one row per email/call/reply)

Endpoints:
    GET  /outreach/targets
    POST /outreach/target           create or upsert a target
    POST /outreach/log              append a log entry (sent, replied, etc.)
    GET  /outreach/log              read recent log entries
    POST /outreach/status           update status of a target
    GET  /outreach/summary          dashboard summary (counts per status, per archetype)
    GET  /outreach/templates        list of letter templates available in outreach/
"""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Body, Query
    from pydantic import BaseModel
except Exception:
    APIRouter = None
    BaseModel = object  # type: ignore


# ---- Request schemas (module-scope so FastAPI introspects them as bodies) ----

if APIRouter is not None:
    class TargetIn(BaseModel):
        name: str
        archetype: str
        contact_person: Optional[str] = None
        contact_email: Optional[str] = None
        contact_path: Optional[str] = None
        why_this_target: Optional[str] = None
        ask: Optional[str] = None
        notes: Optional[str] = None
        tier: Optional[int] = 1

    class StatusIn(BaseModel):
        slug: str
        status: str
        note: Optional[str] = None

    class EventIn(BaseModel):
        slug: str
        kind: str
        body: Optional[str] = None
        related_template: Optional[str] = None

REPO = Path(__file__).resolve().parent.parent
OUTREACH_DIR = REPO / "data" / "outreach"
TARGETS_PATH = OUTREACH_DIR / "targets.json"
LOG_PATH = OUTREACH_DIR / "log.jsonl"
TEMPLATES_DIR = REPO / "outreach"

VALID_STATUSES = ("prospect", "contacted", "in-discussion", "declined", "signed", "paused")
VALID_ARCHETYPES = ("publisher", "curriculum", "ministry", "performer", "church", "other")
VALID_EVENT_KINDS = (
    "note",          # operator memo
    "email-sent",    # outbound
    "email-reply",   # inbound
    "call",          # phone / video
    "status-change", # status moved
    "follow-up-due", # reminder
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir():
    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)


def _load_targets() -> dict:
    _ensure_dir()
    if not TARGETS_PATH.exists():
        return {"schema_version": 1, "targets": []}
    try:
        return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "targets": []}


def _save_targets(j: dict):
    _ensure_dir()
    TARGETS_PATH.write_text(json.dumps(j, indent=2), encoding="utf-8")


def _slug(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown"


def _read_log_lines(limit: int = 500) -> list[dict]:
    """Read the JSONL log (newest entries last in file). Returns newest-first."""
    _ensure_dir()
    if not LOG_PATH.exists():
        return []
    out = []
    try:
        # Read all lines then slice. log is small in practice.
        with LOG_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return []
    out.reverse()
    return out[:limit]


def _append_log(entry: dict):
    _ensure_dir()
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _validate_archetype(a: str) -> str:
    if a not in VALID_ARCHETYPES:
        raise HTTPException(400, f"Invalid archetype. Must be one of: {', '.join(VALID_ARCHETYPES)}")
    return a


def _validate_status(s: str) -> str:
    if s not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}")
    return s


def _validate_kind(k: str) -> str:
    if k not in VALID_EVENT_KINDS:
        raise HTTPException(400, f"Invalid event kind. Must be one of: {', '.join(VALID_EVENT_KINDS)}")
    return k


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/outreach/targets")
    def list_targets(status: Optional[str] = Query(None),
                     archetype: Optional[str] = Query(None)):
        j = _load_targets()
        targets = j.get("targets", [])
        if status:
            targets = [t for t in targets if t.get("status") == status]
        if archetype:
            targets = [t for t in targets if t.get("archetype") == archetype]
        return {
            "schema_version": j.get("schema_version", 1),
            "count": len(targets),
            "targets": targets,
        }

    @router.post("/outreach/target")
    def upsert_target(payload: TargetIn):
        _validate_archetype(payload.archetype)
        slug = _slug(payload.name)
        j = _load_targets()
        targets = j.get("targets", [])
        existing = next((t for t in targets if t.get("slug") == slug), None)
        now = _now()
        if existing:
            existing.update({
                "name": payload.name,
                "archetype": payload.archetype,
                "contact_person": payload.contact_person or existing.get("contact_person"),
                "contact_email": payload.contact_email or existing.get("contact_email"),
                "contact_path": payload.contact_path or existing.get("contact_path"),
                "why_this_target": payload.why_this_target or existing.get("why_this_target"),
                "ask": payload.ask or existing.get("ask"),
                "notes": payload.notes if payload.notes is not None else existing.get("notes"),
                "tier": payload.tier or existing.get("tier", 1),
                "updated_at": now,
            })
            action = "updated"
        else:
            existing = {
                "slug": slug,
                "name": payload.name,
                "archetype": payload.archetype,
                "contact_person": payload.contact_person,
                "contact_email": payload.contact_email,
                "contact_path": payload.contact_path,
                "why_this_target": payload.why_this_target,
                "ask": payload.ask,
                "notes": payload.notes,
                "tier": payload.tier or 1,
                "status": "prospect",
                "created_at": now,
                "updated_at": now,
            }
            targets.append(existing)
            action = "created"
        j["targets"] = targets
        _save_targets(j)
        _append_log({
            "ts": now,
            "slug": slug,
            "kind": "note",
            "body": f"Target {action}: {payload.name}",
        })
        return {"status": action, "slug": slug, "target": existing}

    @router.post("/outreach/status")
    def change_status(payload: StatusIn):
        _validate_status(payload.status)
        j = _load_targets()
        targets = j.get("targets", [])
        t = next((x for x in targets if x.get("slug") == payload.slug), None)
        if not t:
            raise HTTPException(404, f"No target with slug '{payload.slug}'.")
        prev = t.get("status", "prospect")
        if prev == payload.status:
            return {"status": "noop", "slug": payload.slug, "current": prev}
        now = _now()
        t["status"] = payload.status
        t["updated_at"] = now
        if payload.status == "signed":
            t["signed_at"] = now
        elif payload.status == "contacted" and not t.get("first_contacted_at"):
            t["first_contacted_at"] = now
        _save_targets(j)
        _append_log({
            "ts": now,
            "slug": payload.slug,
            "kind": "status-change",
            "body": f"{prev} -> {payload.status}" + (f": {payload.note}" if payload.note else ""),
        })
        return {"status": "ok", "slug": payload.slug, "from": prev, "to": payload.status}

    @router.post("/outreach/log")
    def log_event(payload: EventIn):
        _validate_kind(payload.kind)
        # Ensure target exists for any kind other than note (allow free-floating notes)
        j = _load_targets()
        targets = j.get("targets", [])
        t = next((x for x in targets if x.get("slug") == payload.slug), None)
        if not t and payload.kind != "note":
            raise HTTPException(404, f"No target with slug '{payload.slug}'. Create the target first.")
        now = _now()
        entry = {
            "ts": now,
            "slug": payload.slug,
            "kind": payload.kind,
            "body": (payload.body or "")[:4000],
            "related_template": payload.related_template,
        }
        _append_log(entry)
        # Auto-bump status to 'contacted' on first email-sent
        if t and payload.kind == "email-sent" and t.get("status") == "prospect":
            t["status"] = "contacted"
            t["first_contacted_at"] = now
            t["updated_at"] = now
            _save_targets(j)
        # Auto-bump to 'in-discussion' on first email-reply
        if t and payload.kind == "email-reply" and t.get("status") == "contacted":
            t["status"] = "in-discussion"
            t["updated_at"] = now
            _save_targets(j)
        return {"status": "logged", "entry": entry}

    @router.get("/outreach/log")
    def read_log(limit: int = Query(100, ge=1, le=1000),
                 slug: Optional[str] = Query(None)):
        entries = _read_log_lines(limit=1000)
        if slug:
            entries = [e for e in entries if e.get("slug") == slug]
        return {"count": len(entries[:limit]), "entries": entries[:limit]}

    @router.get("/outreach/summary")
    def summary():
        j = _load_targets()
        targets = j.get("targets", [])
        by_status = {}
        by_archetype = {}
        for t in targets:
            s = t.get("status", "prospect")
            by_status[s] = by_status.get(s, 0) + 1
            a = t.get("archetype", "other")
            by_archetype[a] = by_archetype.get(a, 0) + 1
        # Recent activity
        recent = _read_log_lines(limit=20)
        signed = [t for t in targets if t.get("status") == "signed"]
        in_disc = [t for t in targets if t.get("status") == "in-discussion"]
        return {
            "total_targets": len(targets),
            "by_status": by_status,
            "by_archetype": by_archetype,
            "signed": signed,
            "in_discussion": in_disc,
            "recent_events": recent,
        }

    @router.get("/outreach/templates")
    def list_templates():
        if not TEMPLATES_DIR.exists():
            return {"templates": []}
        out = []
        for f in sorted(TEMPLATES_DIR.glob("letter_*.md")):
            try:
                text = f.read_text(encoding="utf-8")
                # First H1 heading
                first_line = next((ln for ln in text.splitlines() if ln.startswith("#")), f.stem)
                heading = first_line.lstrip("#").strip()
                # First italic "Use when" line (if present)
                use_when = ""
                m = re.search(r"^\*\*Use when\*\*:\s*(.+)$", text, re.MULTILINE)
                if m:
                    use_when = m.group(1).strip().rstrip(".")
                out.append({
                    "file": f.name,
                    "heading": heading,
                    "use_when": use_when,
                    "size_bytes": f.stat().st_size,
                })
            except Exception:
                continue
        return {"templates": out, "dir": "outreach/"}

    return router
