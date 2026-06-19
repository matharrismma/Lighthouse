#!/usr/bin/env python3
"""seeds_to_cards.py — capture the operator's thrown-out terms as CARDS.

Matt drops terms faster than he can track ("hard for me to keep up, but all the
knowledge in cards we store"). The placeholders-to-truth store already catches his
conceptual seeds with an HONEST grade (coincidence < resonance < plausible <
candidate < confirmed). This bridges that store into the card corpus, so each seed
becomes a first-class card — findable, walkable, part of the 11k — without ever
laundering its status: the grade rides on the card's bands and body, and the
authority tier is `matt` (the operator's take, intuition-proposes), never `verified`.

It reads the LIVE placeholders (GET /placeholders) + any extra inline seeds (e.g.
UGM, which isn't a placeholder yet), and writes one card JSON per seed to --out.
Deterministic id (re-run = upsert, no dup). Cards land lifecycle=public with their
honest status visible. The card corpus is the second brain; this is how the seeds
land in it.

    python tools/seeds_to_cards.py --out data/cards            # write into the corpus
    python tools/seeds_to_cards.py --out /tmp/seedcards --dry   # inspect first

The visual (coordinate map) is a SEPARATE path — a seed reaches the picture by also
becoming an almanac entry; that regen runs where entries.json lives (the droplet).
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timezone

BASE = os.environ.get("NH_BASE", "https://narrowhighway.com")

# Seeds Matt has dropped that aren't placeholders yet — captured here so nothing is lost.
EXTRA_SEEDS = [
    {
        "id": "universal_gradient_manifold",
        "name": "Universal Gradient Manifold (UGM) — a heat-source-agnostic energy OS",
        "grade": "resonance",
        "claim": ("Matt's seed (Universal_Gradient_Manifold_Concept). The valuable asset in an "
                  "energy system is not the fuel or the engine but the RESERVOIR that stores a "
                  "gradient and the MANIFOLD that routes it to work: Source -> Gradient -> "
                  "Reservoir -> Manifold -> Converter -> Work. ATP shows a common interface beats "
                  "any single source. Honeycomb = the heat-transfer accelerator (power); the "
                  "firebrick/sand mass = the store (energy). Resonates with our own architecture: "
                  "the manifold-over-swappable-sources is sovereignty made physical; the gradient "
                  "is the Laplace/rate-of-descent; the common interface is the grid/axes."),
        "caveat": ("A hardware concept; the physics first-principles are sound (gradient harvest, "
                   "power-vs-energy split). The single-manifold universality is an architecture bet "
                   "(the gradients aren't freely interconvertible). Held at resonance until assayed."),
    },
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _card_id(name):
    h = hashlib.sha256(("concept_seed::" + name).encode("utf-8")).hexdigest()[:12]
    return "card_n_" + h


def _seed_to_card(seed):
    name = seed.get("name") or seed.get("id") or "Untitled seed"
    grade = (seed.get("grade") or "resonance").lower()
    claim = seed.get("claim") or seed.get("organizes") or ""
    caveat = seed.get("caveat") or ""
    body = claim.strip()
    body += ("\n\nHONEST STATUS: %s — intuition proposes, the assay disposes; this is the "
             "operator's seed, not a verified result." % grade)
    if caveat:
        body += "\n\nCaveat: " + caveat.strip()
    body = body[:3900]
    cid = _card_id(name)
    now = _now()
    return {
        "id": cid,
        "kind": "note",
        "title": name[:200],
        "body": body,
        "source": {
            "label": "Operator's seed (Matt) — honest grade: %s" % grade,
            "url": "/placeholders",
            "ref": seed.get("id") or "",
            "authority_tier": "matt",
        },
        "shelf": "concepts",
        "box": grade,
        "bands": [grade, "operator_seed", "concept", seed.get("kind") or "arrangement_principle"],
        "connections": [],
        "author": "matt",
        "created_at": now,
        "updated_at": now,
        "visibility": "public",
        "lifecycle_stage": "public",
        "volatility": "stable",
        "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0,
                    "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
        "retracted": False,
        "extra": {"origin": "placeholder_or_seed", "grade": grade,
                  "refutable": seed.get("refutable", True), "placeholder_id": seed.get("id")},
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
    ap.add_argument("--out", default="data/cards", help="output dir for card JSONs")
    ap.add_argument("--dry", action="store_true", help="print, don't write")
    args = ap.parse_args()

    seeds = _fetch_placeholders() + EXTRA_SEEDS
    print("seeds to capture: %d (%d placeholders + %d inline)"
          % (len(seeds), len(seeds) - len(EXTRA_SEEDS), len(EXTRA_SEEDS)))
    if not args.dry:
        os.makedirs(args.out, exist_ok=True)
    wrote = 0
    for s in seeds:
        card = _seed_to_card(s)
        if args.dry:
            print("  %s  [%s]  %s" % (card["id"], card["box"], card["title"][:60]))
            continue
        path = os.path.join(args.out, card["id"] + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(card, f, indent=2, ensure_ascii=False)
        wrote += 1
    print("wrote %d seed-cards to %s (shelf=concepts; honest grade on each)"
          % (wrote, args.out) if not args.dry else "dry run — nothing written")
    print("NOTE: cards grow the corpus. To reach the VISUAL, a seed must also become an "
          "almanac entry (entries.json -> coordinate_map.py); that regen runs on the droplet.")


if __name__ == "__main__":
    main()
