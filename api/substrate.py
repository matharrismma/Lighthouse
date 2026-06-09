"""substrate.py — the one low-level JSONL reader for the content substrate.

Before this module, walk.py (`_load_protocols` / `_load_almanac`) and
apothecary.py (`_read_jsonl`) each carried their own copy of the same
line-reading loop. They differed only cosmetically:

  - apothecary used `read_text(errors="replace")` and skipped only blank lines;
  - walk used `open(encoding="utf-8")` (strict) and also skipped `#`-comment
    lines.

Those differences are output-equivalent on clean data: a `#`-prefixed line is
never valid JSON, so `json.loads` raises and the line is skipped either way; and
clean UTF-8 files never exercise `errors="replace"`. This module keeps the
ROBUST UNION of both behaviours — replace undecodable bytes AND skip blank /
`#`-comment / unparseable lines — so every caller gets byte-identical results
plus the safer decode (a stray non-UTF-8 byte can no longer crash the strict
reader walk used).

CACHING stays with the callers by design: walk caches each file by its own
mtime; apothecary caches the whole kind->list dict by the latest mtime across
its sources; packets_index has its own layered cache. This module is the raw
read only — no caching, no globbing, no kind logic. One file in, one list out.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Read one JSONL file into a list of records (whatever `json.loads` yields
    per line, normally dicts). Returns [] for a missing file or any OSError.

    Skips blank lines and `#`-comment lines; silently drops lines that fail to
    parse. Undecodable bytes are replaced rather than fatal. This is exactly the
    union of the two prior private loaders, so it is a drop-in for both."""
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
