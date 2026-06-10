"""migrate_substrate.py — Substrate → first-class cards (LOOP 14).

Walks the read-only substrate adapter in api/cards.py and persists every
adapter-surfaced card to data/cards/ as a real on-disk card. Idempotent —
safe to re-run; existing cards are not overwritten unless --force is passed.

Then authors a starter set of CANONICAL CONNECTION CARDS — the ones that
wire the doctrinal substrate together so walks can land on the path, not
just the destination. Connections drawn:

  Westminster Shorter Q1  ↔  Romans 11:36, 1 Cor 10:31  (proof_text)
  Westminster Shorter Q4  ↔  Apostles' Creed             (illuminates)
  Athanasian Creed        ↔  Nicene Creed                (parallels)
  Apostles' Creed         ↔  Westminster Q22             (illuminates)
  Nicene Creed            ↔  Westminster Q6              (illuminates)
  Chalcedonian Definition ↔  Westminster Q21,22          (illuminates)
  Westminster Q33 (justify)↔ Romans                      (proof_text)
  Westminster Q35 (sanct)  ↔ Romans                      (proof_text)
  Doxology (hymn)          ↔ Westminster Q1              (sings)

These are foundational seed connections, authored by the operator (matt) once.
After this script, the graph has the canonical edges visible at /card.html.

Usage:
  python tools/migrate_substrate.py             # safe; skip existing
  python tools/migrate_substrate.py --force     # overwrite existing on-disk cards
  python tools/migrate_substrate.py --dry-run   # report what would change
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

CARDS_DIR = REPO / "data" / "cards"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _exists(card_id: str) -> bool:
    return (CARDS_DIR / f"{card_id}.json").exists()


def _save(card: dict, force: bool, dry_run: bool) -> str:
    """Returns one of: created, skipped_exists, overwritten, would_create."""
    p = CARDS_DIR / f"{card['id']}.json"
    if p.exists() and not force:
        return "skipped_exists"
    if dry_run:
        return "would_create" if not p.exists() else "would_overwrite"
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return "created" if not p.exists() else "overwritten"


def migrate_adapter_cards(force: bool, dry_run: bool) -> dict:
    """Walk the adapter and persist every card."""
    from api.cards import _all_cards_unified  # type: ignore
    # Use the loader directly so we get adapter cards even with no live cards
    from api.cards import _adapter_load, _ADAPTER_CACHE  # type: ignore
    _adapter_load()
    adapter_cards = _ADAPTER_CACHE["cards"]
    counts = {"created": 0, "skipped_exists": 0, "overwritten": 0, "would_create": 0, "would_overwrite": 0}
    for card_id, card in adapter_cards.items():
        # Ensure source_hash + updated_at present
        card.setdefault("updated_at", _now())
        try:
            from api.cards import _compute_source_hash  # type: ignore
            card.setdefault("source_hash", _compute_source_hash(card))
        except Exception:
            pass
        outcome = _save(card, force, dry_run)
        counts[outcome] = counts.get(outcome, 0) + 1
    return {"total": len(adapter_cards), "counts": counts}


def author_canonical_connections(force: bool, dry_run: bool) -> dict:
    """Author the foundational connection cards. Looks up card IDs by walking
    the existing substrate, then writes connection cards via api.cards."""
    from api.cards import _make_card_id, _compute_source_hash, _all_cards_unified, VALID_RELATIONSHIPS  # type: ignore
    all_cards = _all_cards_unified()

    def find_by(predicate) -> str | None:
        for c in all_cards.values():
            if predicate(c):
                return c["id"]
        return None

    def by_title_contains(needle: str) -> str | None:
        return find_by(lambda c: needle.lower() in (c.get("title") or "").lower())

    def wsc_q(n: int) -> str | None:
        return by_title_contains(f"Westminster Shorter Q{n}")

    # Build a list of canonical connections — operator-authored, foundational
    canonical = [
        # Catechism Q&As ↔ their scriptural anchors (proof_text)
        (wsc_q(1), by_title_contains("Romans"),
         "proof_text", "Westminster Q1: 'glorify God and enjoy him forever.' Romans 11:36 — 'For of him, through him, and to him are all things, to whom be glory forever.'"),
        (wsc_q(33), by_title_contains("Romans"),
         "proof_text", "Westminster Q33 on justification — Romans is the primary text."),
        (wsc_q(35), by_title_contains("Romans"),
         "proof_text", "Westminster Q35 on sanctification — Romans 6 and 8."),
        (wsc_q(21), by_title_contains("Hebrews"),
         "proof_text", "Westminster Q21 on Christ as Redeemer — Hebrews bears it."),
        (wsc_q(85), by_title_contains("John"),
         "proof_text", "Westminster Q85 on what God requires of us — John bears repentance and faith."),

        # Creeds ↔ Creeds (parallels)
        (by_title_contains("Athanasian Creed"), by_title_contains("Nicene Creed"),
         "parallels", "Athanasius and Nicaea defend the same Christological substance. Read them together."),
        (by_title_contains("Apostles"), by_title_contains("Nicene Creed"),
         "parallels", "Apostles' Creed is the seed; Nicene is the answer to Arius. Same faith, different precision."),

        # Creeds ↔ catechism (illuminates)
        (by_title_contains("Apostles"), wsc_q(22),
         "illuminates", "Apostles' Creed names what the catechism unpacks. Both bear the Person and work of Christ."),
        (by_title_contains("Nicene Creed"), wsc_q(6),
         "illuminates", "Nicene Creed on Trinity — Westminster Q6 puts it as 'three persons in the Godhead.'"),
        (by_title_contains("Chalcedonian"), wsc_q(21),
         "illuminates", "Chalcedon on two natures — Westminster Q21 confesses the same."),
        (by_title_contains("Chalcedonian"), wsc_q(22),
         "illuminates", "Chalcedon's two-natures Christology stands behind Westminster Q22 on Christ's humiliation."),

        # Hymns ↔ catechism (illuminates — hymns sing what doctrine teaches)
        (by_title_contains("Doxology"), wsc_q(1),
         "illuminates", "'Praise God from whom all blessings flow' is Q1 set to music. Singing is teaching."),
        (by_title_contains("Holy, Holy, Holy"), by_title_contains("Nicene Creed"),
         "illuminates", "Heber's hymn confesses the Trinity exactly as Nicaea did. The saints sing the creed."),

        # Hymns ↔ scripture (illuminates)
        (by_title_contains("Amazing Grace"), by_title_contains("Ephesians"),
         "illuminates", "Newton's hymn names grace; Ephesians 2 names what grace did."),
    ]

    counts = {"created": 0, "skipped_exists": 0, "missing_target": 0, "would_create": 0}
    for left, right, rel, explanation in canonical:
        if not left or not right:
            counts["missing_target"] += 1
            continue
        if rel not in VALID_RELATIONSHIPS:
            continue
        seed = f"conn::{left}::{right}::{rel}"
        cid = _make_card_id("connection", seed)
        if _exists(cid):
            counts["skipped_exists"] += 1
            continue
        # Author the connection card
        left_title = (all_cards.get(left) or {}).get("title", left)
        right_title = (all_cards.get(right) or {}).get("title", right)
        conn_card = {
            "id": cid,
            "kind": "connection",
            "title": f"{left_title[:50]} ↔ {right_title[:50]}",
            "body": explanation,
            "source": {
                "label": "Operator-authored canonical connection",
                "url": "",
                "ref": "",
                "authority_tier": "matt",
            },
            "shelf": "connections",
            "box": rel,
            "bands": [rel, "canonical"],
            "connections": [
                {"to_card_id": left, "relationship": "see_also"},
                {"to_card_id": right, "relationship": "see_also"},
            ],
            "author": "matt",
            "created_at": _now(),
            "updated_at": _now(),
            "visibility": "public",
            "lifecycle_stage": "public",
            "volatility": "permanent",
            "metrics": {"paperclips_count": 0, "helpful_count": 0, "not_helpful_count": 0, "cite_count": 0, "walks_through_count": 0, "flagged_count": 0},
            "extra": {
                "left_card_id": left,
                "right_card_id": right,
                "relationship_kind": rel,
                "explanation": explanation,
                "bidirectional": True,
            },
        }
        conn_card["source_hash"] = _compute_source_hash(conn_card)

        # Also update the connected cards to surface this connection on their back
        if not dry_run:
            outcome = _save(conn_card, force, False)
            if outcome in ("created", "overwritten"):
                counts["created"] += 1
                # Update left card's connections array
                for end_id, other_id in [(left, right), (right, left)]:
                    p = CARDS_DIR / f"{end_id}.json"
                    if p.exists():
                        try:
                            other = json.loads(p.read_text(encoding="utf-8"))
                        except Exception:
                            continue
                        conns = other.get("connections") or []
                        if not any(x.get("to_card_id") == other_id for x in conns):
                            conns.append({"to_card_id": other_id, "relationship": rel, "via_connection_card_id": cid})
                            other["connections"] = conns
                            other["updated_at"] = _now()
                            p.write_text(json.dumps(other, indent=2), encoding="utf-8")
        else:
            counts["would_create"] += 1
    return {"total_attempted": len(canonical), "counts": counts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing on-disk cards")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change; don't write")
    parser.add_argument("--skip-connections", action="store_true", help="Migrate cards only, no canonical connections")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else ("FORCE" if args.force else "SAFE")
    print(f"=== Substrate migration — {mode} ===")

    print("\n[1/2] Persisting adapter cards to data/cards/...")
    r1 = migrate_adapter_cards(args.force, args.dry_run)
    print(f"  Total in adapter: {r1['total']}")
    for k, v in r1["counts"].items():
        if v:
            print(f"  {k}: {v}")

    if not args.skip_connections:
        print("\n[2/2] Authoring canonical connection cards...")
        r2 = author_canonical_connections(args.force, args.dry_run)
        print(f"  Total connections attempted: {r2['total_attempted']}")
        for k, v in r2["counts"].items():
            if v:
                print(f"  {k}: {v}")

    print("\n=== Migration complete ===")
    print(f"Cards now on disk: {len(list(CARDS_DIR.glob('*.json'))) if CARDS_DIR.exists() else 0}")


if __name__ == "__main__":
    main()
