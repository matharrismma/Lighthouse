#!/usr/bin/env python3
"""seeds_to_almanac.py — put the operator's seeds into the VISUAL, honestly.

The brain/breath visual is the coordinate map, generated from data/almanac/
entries.jsonl by tools/coordinate_map.py. So a seed reaches the picture by
becoming an almanac entry. This emits one entry per operator seed and appends
it (idempotent — skips ids already present).

HONESTY, load-bearing:
  - verdict = "NONE"  -> the breath graph renders it as RESONANCE (faint), never
    as verified/concordant. An operator seed is an intuition, not an engine result.
  - bonds = []        -> NO edge to the source roots, so vine-validity (reach-to-
    source over concord bonds) CANNOT be inflated by adding seeds. They appear as
    new, unconnected frontier dots — which is exactly their status. As one survives
    the assay it earns real bonds and an upgraded verdict; until then it stays faint.
  - coord.family = "operator_seed" -> the seeds share one hue, so they read as a
    cluster by colour without any false claim of connection.

After appending, regenerate the visual:
    python tools/coordinate_map.py      # rebuilds coordinate_map.json (+ the html/stats)
    python tools/build_breath_graph.py  # rebuilds site/breath-graph.json (evidence-labelled)
    python tools/build_brain_graph.py   # rebuilds site/brain-graph.json

    python tools/seeds_to_almanac.py [--entries data/almanac/entries.jsonl]
"""
from __future__ import annotations
import argparse
import json
import os
import urllib.request

BASE = os.environ.get("NH_BASE", "https://narrowhighway.com")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXTRA_SEEDS = [
    {"id": "universal_gradient_manifold",
     "name": "Universal Gradient Manifold (UGM) — a heat-source-agnostic energy OS",
     "grade": "resonance", "domains": ["physics", "energy", "engineering"],
     "axes": ["metabolism", "conservation_balance", "physical_substance"],
     "claim": ("Reservoir stores a gradient, manifold routes it to work; the platform endures "
               "while fuels/engines swap. Resonates with our sovereignty + the Laplace gradient.")},
]


def _seed_entry(s):
    name = s.get("name") or s.get("id") or "Operator seed"
    grade = (s.get("grade") or "resonance").lower()
    sid = "seed_" + (s.get("id") or name).lower().replace(" ", "_")[:48]
    claim = (s.get("claim") or s.get("organizes") or "").strip()
    return {
        "id": sid,
        "kind": "seed",
        "title": name[:80],
        "situation": ("Operator's seed (Matt): " + claim)[:400],
        "category": "operator_seed",
        "domains": s.get("domains") or ["arrangement"],
        "axes": s.get("axes") or [],
        "verdict": "NONE",  # -> resonance (faint); an intuition, not an engine result
        "wisdom": ("Held at %s. Intuition proposes; the assay disposes. Not engine-verified — "
                   "shown faint, honestly, until it survives the test." % grade),
        "triggers": [],
        "bonds": [],  # NO chain to the source — cannot inflate vine-validity
        "coord": {"block": "two-trees", "family": "operator_seed", "level": "map"},
        "extra": {"origin": "operator_seed", "grade": grade, "placeholder_id": s.get("id")},
    }


def _fetch_placeholders():
    try:
        req = urllib.request.Request(BASE.rstrip("/") + "/placeholders",
                                     headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode("utf-8", "replace"))
        return d.get("placeholders") or d.get("items") or []
    except Exception as e:  # noqa: BLE001
        print("  (could not fetch placeholders: %s)" % e)
        return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entries", default=os.path.join(ROOT, "data/almanac/entries.jsonl"))
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    seeds = _fetch_placeholders() + EXTRA_SEEDS
    entries = [_seed_entry(s) for s in seeds]

    existing = set()
    if os.path.exists(args.entries):
        for line in open(args.entries, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    existing.add(json.loads(line).get("id"))
                except Exception:
                    pass
    new = [e for e in entries if e["id"] not in existing]
    print("seed entries: %d total, %d already present, %d to append"
          % (len(entries), len(entries) - len(new), len(new)))
    for e in new:
        print("  + %-46s [resonance]  %s" % (e["id"], e["title"][:46]))
    if args.dry or not new:
        print("(dry run / nothing new)" if args.dry else "nothing to append")
        return
    with open(args.entries, "a", encoding="utf-8") as f:
        for e in new:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("appended %d seed entries to %s — now run the 3 regen tools." % (len(new), args.entries))


if __name__ == "__main__":
    main()
