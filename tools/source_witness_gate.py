"""source_witness_gate.py — Deut 19:15 enforcement for card sources.

Every card claims a source. This gate verifies that source claim by
looking for >=2 INDEPENDENT corroborating witnesses (manuscript tradition,
critical edition, translation, republication, citation tradition, etc.).
Government sources cannot witness themselves: any card whose primary
source is .gov / .mil must have at least one non-government witness.

Output: each card gains a `witnesses[]` array and a `witness_status`:
  - "passed"           >=2 distinct independence_classes, non-gov rule satisfied
  - "single_witness"   exactly 1 witness (works for direct-canon, e.g. Bible verse)
  - "self_only"        only the source itself attests
  - "gov_only"         all witnesses are .gov/.mil — REJECTED for promotion
  - "inherited"        derived card; inherits from parent (engine_derived)
  - "insufficient"     not enough corroboration

Run:
  python tools/source_witness_gate.py --dry-run         # report only
  python tools/source_witness_gate.py --apply           # write to cards
  python tools/source_witness_gate.py --apply --tier external_aligned  # subset

Re-runnable: idempotent. Detects whether witnesses already attached and skips.
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parent.parent
CARDS_DIR = REPO / "data" / "cards"

sys.path.insert(0, str(REPO / "tools"))
from witness_registry import lookup_witnesses, WITNESS_REGISTRY  # noqa: E402


# Authority tiers that need different witness treatment
DIRECT_CANONICAL_TIERS = ("words_in_red", "scripture", "father", "catechism", "creed")
EXTERNAL_TIERS = ("external_aligned",)
DERIVED_TIERS = ("engine_derived",)
OPERATOR_TIERS = ("matt",)


def _is_gov_domain(url_or_label: str) -> bool:
    """Detect government-controlled sources (cannot witness themselves)."""
    s = (url_or_label or "").lower()
    if "nara" in s or "loc.gov" in s or "nasa" in s or ".mil" in s:
        return True
    try:
        if url_or_label.startswith("http"):
            dom = urlparse(url_or_label).netloc.lower()
            return dom.endswith(".gov") or dom.endswith(".mil")
    except Exception:
        pass
    return False


def evaluate_card(card: dict) -> dict:
    """Return witness evaluation: witnesses list + status + reason."""
    src = card.get("source") or {}
    tier = src.get("authority_tier") or "unset"
    label = src.get("label") or ""
    ref = src.get("ref") or ""
    url = src.get("url") or ""

    # Derived cards: inherit from connections (handled in audit pass 2)
    if tier in DERIVED_TIERS:
        return {
            "witnesses": [],
            "witness_status": "inherited_pending",
            "witness_status_reason": "engine_derived; will inherit from parent cards in pass 2",
        }

    # Operator-signed: operator_signature counts as one witness; needs at
    # least one external corroboration (scripture anchor or external citation)
    if tier in OPERATOR_TIERS:
        witnesses = [{"class": "operator_signature",
                       "label": "Operator signature — Matt Harris",
                       "ref": "operator"}]
        # Look up any matching canonical work; if found, add those witnesses
        registry_w = lookup_witnesses(label, ref, tier="creed")  # default to creed-tier corroboration
        witnesses.extend(registry_w)
        classes = {w["class"] for w in witnesses}
        status = "passed" if len(classes) >= 2 else "single_witness"
        reason = (f"operator + {len(witnesses)-1} registry witnesses, "
                  f"{len(classes)} distinct classes")
        return {"witnesses": witnesses, "witness_status": status,
                "witness_status_reason": reason}

    # Canonical / external: look up the registry (with tier-default fallback)
    if tier in DIRECT_CANONICAL_TIERS + EXTERNAL_TIERS:
        witnesses = lookup_witnesses(label, ref, tier=tier, shelf=card.get("shelf") or "")
        # Add the primary source itself only as a self-witness if no external
        if not witnesses and label:
            return {
                "witnesses": [{"class": "self", "label": label, "ref": ref, "url": url}],
                "witness_status": "self_only",
                "witness_status_reason": f"no registry entry matched {label[:60]!r}; only the source itself attests",
            }
        # Apply government rule
        has_gov = any(_is_gov_domain(w.get("url", "") + " " + w.get("label", "")) for w in witnesses)
        has_non_gov = any(not _is_gov_domain(w.get("url", "") + " " + w.get("label", "")) for w in witnesses)
        if has_gov and not has_non_gov:
            return {
                "witnesses": witnesses,
                "witness_status": "gov_only",
                "witness_status_reason": "all witnesses are government-controlled; need at least one non-gov source per Matt's rule",
            }
        # Count distinct independence classes
        classes = {w.get("class") for w in witnesses}
        if len(classes) >= 2:
            status = "passed"
            reason = f"{len(witnesses)} witnesses across {len(classes)} independence classes: {sorted(classes)}"
        elif len(classes) == 1:
            status = "single_witness"
            reason = f"only 1 independence class: {sorted(classes)}"
        else:
            status = "insufficient"
            reason = f"only {len(witnesses)} witness(es), no classes"
        return {"witnesses": witnesses, "witness_status": status,
                "witness_status_reason": reason}

    # Unknown tier — treat as insufficient
    return {
        "witnesses": [],
        "witness_status": "insufficient",
        "witness_status_reason": f"unknown authority_tier {tier!r}",
    }


def evaluate_derived_card(card: dict, all_cards_by_id: dict) -> dict:
    """A derived card (connection, search) inherits from its parents.
    If all parents are 'passed' or 'single_witness', the derived card inherits 'passed'.
    If any parent is 'gov_only' / 'insufficient', so is the derived card."""
    connections = card.get("connections") or []
    parent_ids = [c.get("to_card_id") for c in connections if isinstance(c, dict)]
    parent_ids += [c.get("from_card_id") for c in connections if isinstance(c, dict)]
    parent_ids = [p for p in parent_ids if p]
    if not parent_ids:
        return {
            "witnesses": [],
            "witness_status": "insufficient",
            "witness_status_reason": "derived card has no parent connections to inherit from",
        }
    parent_statuses = []
    inherited_classes = set()
    for pid in parent_ids:
        parent = all_cards_by_id.get(pid)
        if not parent:
            continue
        ps = parent.get("witness_status")
        if ps:
            parent_statuses.append(ps)
            for w in (parent.get("witnesses") or []):
                inherited_classes.add(w.get("class"))
    if not parent_statuses:
        return {"witnesses": [],
                "witness_status": "insufficient",
                "witness_status_reason": "no evaluated parents found"}
    if any(s in ("gov_only", "insufficient") for s in parent_statuses):
        return {"witnesses": [],
                "witness_status": "insufficient",
                "witness_status_reason": f"at least one parent has weak witness: {parent_statuses}"}
    if "passed" in parent_statuses and len(inherited_classes) >= 2:
        return {
            "witnesses": [{"class": "inherited", "label": f"inherited from {len(parent_ids)} parent cards",
                           "ref": ",".join(parent_ids[:5])}],
            "witness_status": "passed",
            "witness_status_reason": f"inherits from {len([s for s in parent_statuses if s=='passed'])} passed parents across {len(inherited_classes)} classes",
        }
    return {
        "witnesses": [{"class": "inherited", "label": f"inherited from {len(parent_ids)} parents"}],
        "witness_status": "single_witness",
        "witness_status_reason": f"inherits weak witness from parents: {Counter(parent_statuses).most_common()}",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Write witnesses+status to each card")
    p.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    p.add_argument("--tier", help="Limit to a single authority_tier (e.g. external_aligned)")
    p.add_argument("--reset", action="store_true", help="Re-evaluate even if witness_status already present")
    args = p.parse_args()

    if not (args.apply or args.dry_run):
        args.dry_run = True

    # Pass 1: evaluate non-derived cards
    all_cards = {}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        all_cards[c.get("id")] = (f, c)

    print(f"loaded {len(all_cards)} cards")
    print()

    status_count = Counter()
    tier_status = {}
    direct_evaluated = 0
    skipped_existing = 0

    for cid, (f, c) in all_cards.items():
        tier = (c.get("source") or {}).get("authority_tier") or "unset"
        if args.tier and tier != args.tier:
            continue
        if c.get("witness_status") and not args.reset:
            status_count[c["witness_status"]] += 1
            tier_status.setdefault(tier, Counter())[c["witness_status"]] += 1
            skipped_existing += 1
            continue
        if tier in ("engine_derived",):
            continue  # handled in pass 2
        result = evaluate_card(c)
        status_count[result["witness_status"]] += 1
        tier_status.setdefault(tier, Counter())[result["witness_status"]] += 1
        direct_evaluated += 1
        if args.apply:
            c["witnesses"] = result["witnesses"]
            c["witness_status"] = result["witness_status"]
            c["witness_status_reason"] = result["witness_status_reason"]
            f.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"=== Pass 1: direct evaluation ===")
    print(f"  evaluated: {direct_evaluated}")
    print(f"  skipped (already had status): {skipped_existing}")
    print()

    # Pass 2: derived cards inherit from parents
    derived_evaluated = 0
    if not args.tier or args.tier == "engine_derived":
        # Need to re-load cards to see pass-1 writes
        eval_by_id = {}
        for cid, (f, c) in all_cards.items():
            if args.apply:
                try:
                    c = json.loads(f.read_text(encoding="utf-8"))
                    all_cards[cid] = (f, c)
                except Exception:
                    pass
            eval_by_id[cid] = c

        for cid, (f, c) in all_cards.items():
            tier = (c.get("source") or {}).get("authority_tier") or "unset"
            if tier != "engine_derived":
                continue
            if c.get("witness_status") and not args.reset:
                status_count[c["witness_status"]] += 1
                tier_status.setdefault(tier, Counter())[c["witness_status"]] += 1
                continue
            result = evaluate_derived_card(c, eval_by_id)
            status_count[result["witness_status"]] += 1
            tier_status.setdefault(tier, Counter())[result["witness_status"]] += 1
            derived_evaluated += 1
            if args.apply:
                c["witnesses"] = result["witnesses"]
                c["witness_status"] = result["witness_status"]
                c["witness_status_reason"] = result["witness_status_reason"]
                f.write_text(json.dumps(c, indent=2, ensure_ascii=False), encoding="utf-8")

        print(f"=== Pass 2: derived inheritance ===")
        print(f"  evaluated: {derived_evaluated}")
        print()

    # Report
    print(f"=== witness_status distribution ===")
    for status, n in status_count.most_common():
        print(f"  {status:<20} {n:>5}")
    print()
    print(f"=== by tier ===")
    for tier, counts in sorted(tier_status.items()):
        print(f"  {tier}:")
        for s, n in counts.most_common():
            print(f"    {s:<20} {n:>5}")

    if args.dry_run:
        print()
        print("DRY-RUN — no files modified. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
