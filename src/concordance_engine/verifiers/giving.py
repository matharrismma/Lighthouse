"""Giving verifier -- conservation of a value-transfer (giving) chain.

The verification floor applied to GIVING: prove every unit of value given is
accounted for all the way to the END USER -- no silent leakage, no skim. It is
the same conservation law the engine already applies to atoms (a balanced
equation) and momentum (a closed system) and a balance sheet, now applied to
money: what goes IN must come out as fees + what is DELIVERED. Nothing
disappears between the books and the face it was meant for.

Deterministic; no external data -- it verifies a PROVIDED, structured giving
chain. This is "never trust, always verify" for charity: the giver gets a
result they can re-check without trusting any middleman.

Spec (giving.conservation):
  {
    "source": 1000.00,                  # what the donor gave (top of the chain)
    "links": [                           # each hop's cut/fee along the chain
       {"name": "platform",      "fee": 30.0},
       {"name": "charity",       "fee": 120.0},
       {"name": "field_partner", "fee": 50.0}
    ],
    "delivered": 800.00,                 # what reached the end user
    "claimed_delivered_fraction": 0.80,  # OPTIONAL: a claimed efficiency to check
    "tolerance": 0.01,                   # OPTIONAL: default 0.01 (one penny)
    "currency": "USD"                    # OPTIONAL: label only
  }

CONFIRMED iff  source == sum(fees) + delivered  (within tolerance) AND, if a
claimed efficiency is given, delivered/source matches it. On a shortfall it
reports the UNACCOUNTED amount (the leak); on an overage it flags an impossible
chain (more delivered than was given). Always reports delivered_fraction (what
reached the end user) and overhead_fraction.
"""
from __future__ import annotations

from typing import Any, Dict

from .base import VerifierResult, na, confirm, mismatch, error


def _num(x: Any):
    try:
        if x is None:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def verify(spec: Dict[str, Any]) -> VerifierResult:
    name = "giving.conservation"
    if not isinstance(spec, dict):
        return na(name, "spec must be an object with 'source', 'delivered', and optional 'links'")

    source = _num(spec.get("source"))
    delivered = _num(spec.get("delivered"))
    if source is None or delivered is None:
        return na(name, "provide numeric 'source' (given) and 'delivered' (reached the end user)")

    tol = _num(spec.get("tolerance"))
    if tol is None or tol < 0:
        tol = 0.01

    if source < 0 or delivered < 0:
        return mismatch(name, "amounts cannot be negative", {"source": source, "delivered": delivered})

    links = spec.get("links") or []
    if not isinstance(links, list):
        return na(name, "'links' must be a list of {name, fee} hops")

    fees_total = 0.0
    fee_breakdown = []
    for ln in links:
        ln = ln or {}
        f = _num(ln.get("fee", 0))
        if f is None:
            return na(name, f"non-numeric fee at link '{ln.get('name', '?')}'")
        if f < 0:
            return mismatch(name, f"negative fee ({f}) at link '{ln.get('name', '?')}'",
                            {"link": ln.get("name", "?"), "fee": f})
        fees_total += f
        fee_breakdown.append({"name": str(ln.get("name", "link")), "fee": round(f, 4)})

    accounted = fees_total + delivered
    gap = source - accounted
    delivered_fraction = (delivered / source) if source else 0.0
    overhead_fraction = (fees_total / source) if source else 0.0

    data: Dict[str, Any] = {
        "source": round(source, 4),
        "fees_total": round(fees_total, 4),
        "delivered": round(delivered, 4),
        "unaccounted": round(gap, 4),
        "delivered_fraction": round(delivered_fraction, 4),
        "overhead_fraction": round(overhead_fraction, 4),
        "links": fee_breakdown,
    }
    cur = spec.get("currency")
    if cur:
        data["currency"] = str(cur)[:8]

    # over-accounted: the chain claims to deliver more than was given (impossible)
    if gap < -tol:
        return mismatch(
            name,
            f"over-accounted by {-gap:.2f}: fees {fees_total:.2f} + delivered {delivered:.2f} "
            f"= {accounted:.2f} exceeds source {source:.2f} -- the chain claims to deliver more "
            f"than was given.",
            data)

    # shortfall: dollars vanished between the books and the end user
    if gap > tol:
        return mismatch(
            name,
            f"{gap:.2f} UNACCOUNTED: source {source:.2f} - fees {fees_total:.2f} = "
            f"{source - fees_total:.2f}, but only {delivered:.2f} delivered. {gap:.2f} leaked or "
            f"went unrecorded between the books and the end user.",
            data)

    # books close. Optionally check a claimed efficiency.
    claimed = _num(spec.get("claimed_delivered_fraction"))
    if claimed is not None:
        if abs(delivered_fraction - claimed) > max(tol, 0.005):
            return mismatch(
                name,
                f"books close, but the claimed efficiency is wrong: claimed "
                f"{claimed * 100:.1f}% reaches the end user, actual is "
                f"{delivered_fraction * 100:.1f}%.",
                data)

    return confirm(
        name,
        f"books close: {source:.2f} = fees {fees_total:.2f} + delivered {delivered:.2f}; "
        f"{delivered_fraction * 100:.1f}% reached the end user "
        f"({overhead_fraction * 100:.1f}% overhead across {len(fee_breakdown)} hop"
        f"{'' if len(fee_breakdown) == 1 else 's'}).",
        data)
