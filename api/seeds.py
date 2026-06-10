"""
seeds.py — Search once, seed the keeping, reference forever.

When a search query misses the keeping entirely, the engine does the
work of synthesis ONE TIME — calling the Apothecary, keyword search,
and Walk — then stores the result as a seed. Every future search for
the same (or similar) query hits the seed directly.

Seeds live in data/seeds/seeds.jsonl. They are included in the packet
index just like almanac entries, protocols, etc.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_SEEDS_DIR = _REPO / "data" / "seeds"
_SEEDS_FILE = _SEEDS_DIR / "seeds.jsonl"


def _seed_id(query: str) -> str:
    """Stable ID from normalized query text."""
    norm = " ".join(query.lower().split())
    h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:12]
    return f"seed-{h}"


def _ensure_dir():
    _SEEDS_DIR.mkdir(parents=True, exist_ok=True)


def load_seeds() -> List[Dict[str, Any]]:
    """Load all seeds from the JSONL file."""
    if not _SEEDS_FILE.exists():
        return []
    seeds = []
    try:
        with open(_SEEDS_FILE, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    seeds.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return seeds


def find_seed(query: str) -> Optional[Dict[str, Any]]:
    """Check if a seed already exists for this query."""
    sid = _seed_id(query)
    for s in load_seeds():
        if s.get("id") == sid:
            return s
    return None


def store_seed(seed: Dict[str, Any]) -> Dict[str, Any]:
    """Append a seed record to the JSONL file. Returns the seed."""
    _ensure_dir()
    with open(_SEEDS_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(seed, ensure_ascii=False) + "\n")
    return seed


def craft_seed(
    query: str,
    compound: Optional[Dict[str, Any]] = None,
    search_hits: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Build a seed packet from synthesis results.

    The seed is a normal packet with kind='seed'. It gets picked up
    by the packet index on the next search, so every future query
    for the same topic finds it immediately.
    """
    now = int(time.time())
    sid = _seed_id(query)

    # Build summary from compound ingredients
    summary_parts = []
    if compound:
        for slot in ("scripture", "protocol", "mind", "almanac", "training",
                     "fieldkit", "body", "parable", "philosopher", "father"):
            ing = compound.get(slot)
            if ing and isinstance(ing, dict):
                title = ing.get("title") or ing.get("name") or ing.get("id") or slot
                summary_parts.append(f"{slot}: {title}")
    if search_hits:
        for h in search_hits[:3]:
            t = h.get("title") or h.get("id") or ""
            v = (h.get("verdict") or "").upper()
            if t:
                summary_parts.append(f"{v} {t}" if v else t)

    summary = "; ".join(summary_parts)[:280] if summary_parts else query[:280]

    # Collect domains from compound ingredients
    domains = set()
    if compound:
        for slot_val in compound.values():
            if isinstance(slot_val, dict):
                for d in (slot_val.get("domains") or []):
                    domains.add(d)
    if search_hits:
        for h in search_hits[:3]:
            for d in (h.get("domains") or []):
                domains.add(d)

    seed = {
        "kind": "seed",
        "id": sid,
        "query": query,
        "title": query[:200],
        "verdict": None,
        "domains": sorted(domains)[:8],
        "axes": [],
        "summary": summary,
        "compound": compound,
        "related_hits": [
            {"id": h.get("id"), "title": h.get("title"), "verdict": h.get("verdict"),
             "kind": h.get("kind"), "permalink": h.get("permalink")}
            for h in (search_hits or [])[:5]
        ],
        "permalink": f"/?q={query}",
        "api_path": f"/seed/{sid}",
        "weight": 0.85,
        "timestamp": now,
        "seeded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }
    return seed


def normalize_for_index(seed: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a seed record to the standard packet dict for the index."""
    return {
        "kind": seed.get("kind", "seed"),
        "id": seed.get("id", ""),
        "title": seed.get("title", ""),
        "verdict": seed.get("verdict"),
        "domains": seed.get("domains", []),
        "axes": seed.get("axes", []),
        "summary": seed.get("summary", ""),
        "permalink": seed.get("permalink", ""),
        "api_path": seed.get("api_path", ""),
        "weight": seed.get("weight", 0.85),
        "timestamp": seed.get("timestamp", 0),
    }
