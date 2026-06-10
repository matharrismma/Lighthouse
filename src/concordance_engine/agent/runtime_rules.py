"""Runtime-loaded NL dispatch rules.

The hard-coded rules in dispatch.py ship with the engine. THIS module
adds runtime rules — patterns the operator promotes from the
misalignment review queue. Every promotion increases routing accuracy:
the next time a similar claim arrives, the engine routes it correctly
without an oracle call.

Storage: data/agent/runtime_rules.jsonl
Format (one JSON object per line):
  {
    "rule_id":      "rt-<short-hash>",
    "pattern":      "<regex string>",     # case-insensitive
    "domain":       "<verifier domain>",  # e.g. "chemistry"
    "spec_template":{<key>: <value-or-_capture:N>}, # optional
    "created_at":   <unix-epoch>,
    "source_misalignment_id": "<id>",
    "notes":        "<operator note>"
  }

Design constraint: still deterministic. No ML. No network. Loads from
disk on first call and caches by mtime — so the operator can promote
a misalignment and the very next /agent call honors the new rule
without a restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_DATA_DIR = Path(
    os.environ.get("CONCORDANCE_DATA_DIR", "data")
) / "agent"
_RULES_FILE = _DATA_DIR / "runtime_rules.jsonl"

_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {"mtime": 0.0, "rules": []}


def _short_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


def _compile_rule(rec: Dict[str, Any]) -> Optional[Tuple[str, "re.Pattern[str]", str, Dict[str, Any], str]]:
    """Return (rule_id, compiled_pattern, domain, spec_template, raw_pattern)
    or None if the rule is malformed."""
    rid = (rec.get("rule_id") or "").strip()
    pat = (rec.get("pattern") or "").strip()
    dom = (rec.get("domain") or "").strip()
    if not rid or not pat or not dom:
        return None
    try:
        compiled = re.compile(pat, re.IGNORECASE)
    except re.error:
        return None
    spec_template = rec.get("spec_template") or {}
    if not isinstance(spec_template, dict):
        spec_template = {}
    return (rid, compiled, dom, spec_template, pat)


def load_rules() -> List[Tuple[str, "re.Pattern[str]", str, Dict[str, Any], str]]:
    """Return the current set of runtime rules, mtime-cached."""
    if not _RULES_FILE.exists():
        return []
    try:
        mtime = _RULES_FILE.stat().st_mtime
    except OSError:
        return []
    with _LOCK:
        if _CACHE["rules"] and mtime <= _CACHE["mtime"]:
            return _CACHE["rules"]
        compiled: List[Tuple[str, "re.Pattern[str]", str, Dict[str, Any], str]] = []
        try:
            for line in _RULES_FILE.read_text("utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                c = _compile_rule(rec)
                if c is not None:
                    compiled.append(c)
        except OSError:
            return []
        _CACHE["mtime"] = mtime
        _CACHE["rules"] = compiled
        return compiled


def _expand_spec(template: Dict[str, Any], match: "re.Match[str]", text: str) -> Dict[str, Any]:
    """Resolve `_capture:N` references in the spec template against a match."""
    out: Dict[str, Any] = {}
    for k, v in template.items():
        if isinstance(v, str) and v.startswith("_capture:"):
            try:
                idx = int(v.split(":", 1)[1])
                out[k] = match.group(idx)
            except (ValueError, IndexError):
                continue
        elif isinstance(v, str) and v == "_text":
            out[k] = text
        else:
            out[k] = v
    return out


def try_dispatch(text: str) -> Optional[Dict[str, Any]]:
    """Try every runtime rule against `text`. Return a dict with
    {rule_id, domain, spec} on first match, or None if no rule fits."""
    if not text or not text.strip():
        return None
    for rid, pattern, domain, spec_tpl, _raw in load_rules():
        m = pattern.search(text)
        if m is not None:
            spec = _expand_spec(spec_tpl, m, text)
            return {"rule_id": rid, "domain": domain, "spec": spec}
    return None


def add_rule(
    *,
    pattern: str,
    domain: str,
    spec_template: Optional[Dict[str, Any]] = None,
    source_misalignment_id: str = "",
    notes: str = "",
) -> Dict[str, Any]:
    """Append a new runtime rule. Returns the record. Validates regex."""
    pat = (pattern or "").strip()
    dom = (domain or "").strip()
    if not pat:
        raise ValueError("pattern is required")
    if not dom:
        raise ValueError("domain is required")
    # Sanity-compile so we never write a broken rule
    try:
        re.compile(pat, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"pattern is not a valid regex: {exc}")

    now = int(time.time())
    rec = {
        "rule_id": "rt-" + _short_hash(pat + "|" + dom + "|" + str(now)),
        "pattern": pat,
        "domain": dom,
        "spec_template": spec_template or {},
        "created_at": now,
        "created_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "source_misalignment_id": (source_misalignment_id or "").strip(),
        "notes": (notes or "").strip()[:500],
    }
    with _LOCK:
        _RULES_FILE.parent.mkdir(parents=True, exist_ok=True)
        with _RULES_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # Invalidate cache so the next try_dispatch reflects the addition
        _CACHE["mtime"] = 0.0
        _CACHE["rules"] = []
    return rec


def list_runtime_rules() -> List[Dict[str, Any]]:
    """Read the JSONL file fresh and return rule records for inspection."""
    if not _RULES_FILE.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in _RULES_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out
