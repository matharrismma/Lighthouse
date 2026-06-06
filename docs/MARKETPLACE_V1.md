# Christian Marketplace — v1 spec

*Make it easy to do business with others. Know there is some trust. Free.*

Companion to [HORIZONS.md](HORIZONS.md) and the marketplace plan. Decisions
locked: **free** — no membership, no fee, no cut of any trade (2026-06-06).
The product is **trust**; trust is what makes doing business cheap.

## The one-sentence shape

A **trusted directory** where a Christian can list a good or a service, and
another can find it and **see that the seller and the listing are vouched** —
then the two transact *directly*, off-platform. We connect and we vouch. We
hold no money, take no cut, run no escrow. (Truth collapses markup; trust
collapses transaction cost.)

## Build on what exists — REUSE, don't fork

| Need | Reuse | New work |
|------|-------|----------|
| Storage + lifecycle | `cards.py` — a listing **is a card**, `kind="listing"`, marketplace fields in `extra`; quarantine→public lifecycle + `/cards/{id}/promote` already exist | add `"listing"` to `VALID_KINDS`; `shelf="marketplace"` |
| Submit → review → publish | `user_content.py` pattern (intake → quarantine → operator approve/reject; vote "uses trust score") | a thin `/market/*` router mirroring it |
| Listing/seller vouching | `witnesses.py` doctrine (≥2 independent witnesses, Deut 19:15) | a **community vouch** (people vouching for a seller/trade) vs the current source-witness — same rule, new mechanism |
| Content gate | `floor.py` `stand_on_floor()` — RED disqualifiers catch scams/prohibited goods; alignment catches non-family content | call it on submit |
| Render | `card_ssr.py` (FTC-style disclosure already designed for products) | a listing card template |
| Thumbs / flag | the feedback loop (`/feedback/card`, every flag read) | wire listings + sellers in |
| Moderators at scale | `community.py` | per-region moderator role (later in v1) |

The only genuinely new surfaces are small: the `/market/*` router, a
**seller profile**, the **community-vouch** mechanism, and the **Marketplace
deck** UI. Everything else is integration.

## Data shape — a listing is a card

```
kind: "listing"
title: "Cast iron skillet, 12in, restored"
body: <description>
author: <seller handle>
source_authority_tier: "user_household"
shelf: "marketplace"
box: "goods" | "services" | "local"
extra: {
  seller_id: <stable id>,
  category: "goods" | "services" | "local",
  price: 35 | null,            # null = "contact for price"
  price_unit: "flat" | "hr" | "day",
  region: "75701" | "Tyler, TX",
  photos: [<url>, ...],
  condition: "new" | "good" | "fair",   # goods only
  contact: { method: "in_platform" | "phone" | "email", public: <opt-in value> },
  status: "active" | "pending" | "sold" | "expired"
}
witness_status: <from the vouch gate>     # self_only → vouched
```

`shelf="marketplace"` segregates listings from the knowledge substrate — they
**must not** enter walks/retrieval as sources. Commerce is not the floor.

## Trust — two layers, honest about cold-start

1. **Listing/transaction trust (the witness gate).** ≥2 independent community
   members vouch: *"I dealt with this seller / it was as described."* Stored as
   the card's witness chain. Vouchers must themselves carry standing (trust-gate
   the vouch, or sybils farm it). This is the Deut 19:15 rule applied to people.
2. **Seller (person) trust.** A profile assembled from signals — member-since,
   # listings, # vouched trades, flags upheld — surfaced as an **honest badge**
   (`new` · `known` · `trusted` · `vouched`), not a gameable star number.
   *Cold-start truth:* at launch nobody has history, so every seller reads
   `new` and the platform seeds operator-vetted listings first ("our plumber,
   our barber"). The badge never lies about how little is known yet.

> Note: `trust_index.py` is *verification-convergence* trust (many nodes confirm
> the same deterministic result), not person reputation. Seller trust is a small
> new assembly over existing signals — don't conflate the two.

## Flow

1. Seller submits → `POST /market/listings` → lands in **quarantine**.
2. `stand_on_floor()` runs: RED disqualifiers (scam, prohibited goods,
   exploitation) + alignment (family/Christian/clean). Fail → never publishes.
3. Operator approves (seed phase) **or** community vouches promote it
   (steady phase). Reuses the card promote path.
4. Published to the **Marketplace deck**. Buyers browse, see the seller badge
   + vouches, and **contact directly**. We step out of the transaction.
5. Thumbs/flag feed the loop; every flag is read; operator/moderator has final
   say. No paywall policing — trust gates, never a wall.

## Endpoints (mirror existing patterns)

```
POST /market/listings              submit → quarantine (floor + align gate)
GET  /market/listings              browse; filter category / region / status
GET  /market/listings/{id}         detail + seller badge + vouches
POST /market/listings/{id}/vouch   community witness (trust-gated)
POST /market/listings/{id}/promote operator (reuse cards lifecycle)
POST /market/listings/{id}/retract seller or operator
GET  /market/seller/{id}           profile: badge, history, listings, vouches
POST /feedback/card                reuse — thumbs / flag a listing
```

## Interface — a deck of cards

A **Marketplace** deck (decks-and-cards model). Sub-decks: **Goods · Services ·
Local**. Listing cards filterable by category + region. Detail view leads with
the **seller badge + vouches** (trust first, price second). A plain
submit-a-listing form. Mobile-native.

## Costco lessons kept (without the fee)

- **Curation = trust:** the witness gate is the SKU-reduction — not everything
  gets in; "if it's here, it's vouched."
- **House-brand floor:** where the local market is thin, seed engine/operator
  listings so the deck is never empty.
- **On the member's side:** we take no cut, so we have no incentive to inflate
  anything. Aligned by construction.

## Out of v1 (deliberately)

Payments · escrow · crypto wallet · the cross-platform aggregator · per-region
FAST channels · membership/Patron tier · numeric star ratings. All downstream;
none needed to "make it easy to do business, with trust."

## Risks to build around

- **PII / safety:** never expose a seller's email/phone in a URL or to an
  unauthenticated scrape. v1 = seller's *opt-in* public contact only, or an
  in-platform relay (relay deferred). Never auto-contact on a buyer's behalf.
- **Sybil vouching:** trust-gate who may vouch; one household, one vouch.
- **Operator-load ceiling:** seed-curate first; add per-region moderators
  (`community.py`) before opening community submission widely.
- **Don't become the policeman:** trust gates and read-every-flag, not a rake
  to fund enforcement. The moment we'd need to charge to police it, stop and
  rethink.

## Build order (smallest first)

- **M1:** `listing` kind + `/market` POST/GET/detail + minimal Marketplace deck;
  operator-seeded listings; floor gate on submit.
- **M2:** seller profile + honest badge + community vouch (trust-gated).
- **M3:** feedback wired to listings; per-region moderators; expiry/fading.

*Free. No cut. Trust is the only currency.*

## Implemented (v1 — 2026-06-06)

Built and verified end-to-end (floor gate, two-witness auto-publish, seller
badges, operator/moderator queue):

- **Backend:** `api/market.py` (router mounted in `app.py`). Endpoints under
  `/market/*` exactly as specced. Floor-gated at submit via
  `floor.stand_on_floor(text, domain="commerce", kind="listing")` — verified
  that coercive language trips RED and is rejected.
- **Store refinement:** a listing is NOT written into `data/cards/` after all —
  it lives in its own `data/market/listings/` + `data/market/sellers/`, keeping
  the card *shape and lifecycle* but staying entirely out of the knowledge
  substrate / walks / retrieval. Cleaner and safer than `kind="listing"` in the
  shared card pool; same conceptual model.
- **Trust:** listing witness gate (≥2 independent vouches → auto-`active`,
  self-vouch and duplicate-vouch blocked); seller badge
  `new → known → trusted → vouched` (+ `caution` on upheld flags), assembled
  from real signals, never a number.
- **Frontend:** `site/marketplace.html` — a deck (All · Goods · Services ·
  Local), search + region filter, listing detail with seller badge + vouches +
  opt-in contact, a submit form, and seller profiles. Wired into the shell nav
  ("Market") and the family-life footer.
- **By ZIP code (added 2026-06-06):** location is the spine. Listings carry a
  normalized `zip` + `country` (2-letter, default US) + optional `area_code`.
  Browse `scope` = exact ZIP · nearby (ZIP3 prefix ≈ a region) · country ·
  everywhere. The deck has a sticky location selector — ZIP input, country
  code, scope chips, recent-ZIP chips, and a "jump to a place with listings"
  menu (`GET /market/zips`). ZIP/scope persist per visitor.
- **Free:** no billing, tiers, payments, or escrow anywhere. Trust is the only
  currency.

Deferred (per scope): uploads (URLs for now), per-region moderator UI,
in-platform contact relay, SSR listing pages for crawlers.
