"""wallet_payout_queue.py — Operator helper for creator payouts.

Walks data/user_submissions/ and data/wallet/transparency_log.json, computes
which creators are owed payouts based on:
  - Approved submissions (they're in the rotation)
  - Total incoming since their content was approved
  - Creator-payouts allocation (40% per operator.json by default)
  - Already-completed payouts (deducted from what's owed)

Phase 1 is INFORMATIONAL only. The operator reviews the queue, decides who
to pay this week, and runs the payouts manually from their own wallet
(then records the txid via POST /wallet/record-payout).

Phase 2: deterministic per-share computation tied to channel-segment plays.

Usage:
  python tools/wallet_payout_queue.py
  python tools/wallet_payout_queue.py --json    # machine-readable
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parent.parent
SUB_DIR = REPO / "data" / "user_submissions"
WALLET_DIR = REPO / "data" / "wallet"
OPERATOR_PATH = WALLET_DIR / "operator.json"
LOG_PATH = WALLET_DIR / "transparency_log.json"


def load_json(p: Path, default):
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    args = ap.parse_args()

    op = load_json(OPERATOR_PATH, {})
    log = load_json(LOG_PATH, {"entries": []})
    alloc = op.get("allocation", {})
    creator_share_pct = alloc.get("creator_payouts_pct", 40) / 100.0

    # Total received
    entries = log.get("entries", [])
    total_in = sum((e.get("amount_usd") or 0) for e in entries if e.get("direction") == "in")
    total_out = sum((e.get("amount_usd") or 0) for e in entries if e.get("direction") == "out")

    # Approved creators (anyone with at least one approved submission)
    creators = defaultdict(lambda: {"submissions": 0, "wallet": None, "name": None, "email": None, "kinds": []})
    if SUB_DIR.exists():
        for f in SUB_DIR.glob("*.json"):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if rec.get("status") != "approved":
                continue
            cname = rec.get("creator_name", "").strip() or "(anonymous)"
            c = creators[cname]
            c["submissions"] += 1
            if not c["wallet"] and rec.get("wallet_address"):
                c["wallet"] = rec["wallet_address"]
            c["email"] = rec.get("creator_email") or c["email"]
            c["name"] = cname
            c["kinds"].append(rec.get("kind") or rec.get("source_type", "?"))

    # Already-paid totals per creator (from outgoing entries)
    paid = defaultdict(float)
    for e in entries:
        if e.get("direction") != "out":
            continue
        cid = e.get("creator_id")
        if cid:
            paid[cid] += (e.get("amount_usd") or 0)

    # Owed: equal split of (creator pool − already paid) across approved creators
    creator_pool = total_in * creator_share_pct
    paid_total = sum(paid.values())
    pool_remaining = max(0.0, creator_pool - paid_total)
    n = len([c for c in creators.values() if c["wallet"]])  # only payable
    fair_share = (pool_remaining / n) if n > 0 else 0.0

    rows = []
    for cname, c in sorted(creators.items()):
        already = paid.get(cname, 0.0)
        suggested = round(fair_share, 2) if c["wallet"] else 0.0
        rows.append({
            "creator": cname,
            "submissions": c["submissions"],
            "kinds": list(set(c["kinds"])),
            "wallet": c["wallet"] or None,
            "already_paid_usd": round(already, 2),
            "suggested_payout_usd": suggested,
            "payable": bool(c["wallet"]),
        })

    summary = {
        "operator_address_published": bool(op.get("evm_address")),
        "total_in_logged_usd": round(total_in, 2),
        "total_out_logged_usd": round(total_out, 2),
        "creator_share_pct": int(creator_share_pct * 100),
        "creator_pool_usd": round(creator_pool, 2),
        "already_paid_usd": round(paid_total, 2),
        "pool_remaining_usd": round(pool_remaining, 2),
        "approved_creators": len(creators),
        "payable_creators": n,
        "fair_share_usd": round(fair_share, 2),
        "creators": rows,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
        return

    print(f"=== Wallet Payout Queue ===")
    print(f"  operator address published: {summary['operator_address_published']}")
    print(f"  logged in (USD):     ${summary['total_in_logged_usd']:.2f}")
    print(f"  logged out (USD):    ${summary['total_out_logged_usd']:.2f}")
    print(f"  creator share:       {summary['creator_share_pct']}%")
    print(f"  creator pool (USD):  ${summary['creator_pool_usd']:.2f}")
    print(f"  already paid:        ${summary['already_paid_usd']:.2f}")
    print(f"  pool remaining:      ${summary['pool_remaining_usd']:.2f}")
    print(f"  approved creators:   {summary['approved_creators']}")
    print(f"  payable creators:    {summary['payable_creators']}  (have wallet)")
    print(f"  fair share each:     ${summary['fair_share_usd']:.2f}\n")
    if not rows:
        print("  No approved creators yet. Approve user submissions at /channels/admin.html.")
        return
    print(f"  {'CREATOR':<30} {'SUBS':>4} {'PAID':>8} {'OWED':>8}  WALLET")
    for r in rows:
        wallet_short = (r["wallet"][:8] + "…" + r["wallet"][-4:]) if r["wallet"] else "—"
        print(f"  {r['creator'][:30]:<30} {r['submissions']:>4} ${r['already_paid_usd']:>6.2f} ${r['suggested_payout_usd']:>6.2f}  {wallet_short}")
    print(f"\nTo execute a payout: send from operator wallet to the creator's address,")
    print(f"then POST the txid to /wallet/record-payout for the transparency ledger.")


if __name__ == "__main__":
    main()
