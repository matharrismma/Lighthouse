# .org = the notary / registry: the trust layer for the agent economy

A framing proposal (Matt's call to execute). The three surfaces already have distinct jobs:
**.com** = the app/engine (verify, seal, MCP, the maps); **.tv** = the gift/family face;
**.org** = the **authority / registry** layer. This doc proposes what `.org` is *for*.

## The thesis

As AI agents do more consequential work, the unanswered question becomes: *"did this actually
hold?"* The Concordance Engine already mints the answer -- a permanent, content-addressed,
**signed** receipt at `/seal/<hash>` (the record carries `issuer_public_key` and
`integrity_verified`). That receipt is exactly what a **notary** or a **registry** issues: a neutral,
durable, independently-checkable stamp that a claim was verified.

`.org` is the natural home for that role -- the institutional, neutral, durable face -- the way a
DOI registry, a certificate authority, or Underwriters Laboratories is an `.org`-shaped thing, not
a product. The engine *produces* seals; `.org` is where they are *registered, browsed, and
trusted*.

## What .org would offer (concrete)

1. **Seal lookup / verification** -- a clean public page: paste a `cite_url` or hash, see the
   verdict, the signature check, and the derivation trail. "Is this seal real?" answered for anyone,
   no account, no trust in the answerer. (The data already exists at `/seal/<hash>`; this is the
   human/registry front for it.)
2. **The public ledger** -- a browsable, searchable index of sealed derivations (the verified
   corpus as a registry, not just a card store). Filter by domain; cite by permanent ref.
3. **The standard** -- the spec for what a seal means, how the signature is checked, and how an
   independent party can verify one *without* the service (the verification method + public key).
   This is what makes it a standard rather than a product feature.
4. **Issuer transparency** -- the public key(s), the engine version, the verifier domains and their
   methods (already summarized at `/capabilities`).

## Why this is the moat compounding

The seal is only valuable if it is **neutral and permanent**. A registry framing (`.org`) signals
exactly that: not "our product's badge" but "the place verified claims are recorded." Every seal
minted, every verifier added, widens the registry -- and a registry's value grows with its
coverage and its independence. This is the verification floor turning into infrastructure: the
notary the agent economy can cite.

## Honest boundaries

- This is a **framing + a set of pages**, not a claim that the registry is yet adopted or trusted at
  scale -- adoption is the work (visibility, the ChatGPT Action, traffic).
- The seal proves a *derivation* holds against fixed standards; it does not bless the *importance* or
  the *real-world use* of a claim. The notary records that the math is sound, nothing more -- which
  is precisely its trustworthy modesty.
- The engine remains a conduit, not the author. The registry indexes the concord; it does not own
  the truth it records. Apex (Col 1:17) reserved.

## To execute (OPERATOR)

Route `.org` to a registry view (seal lookup + ledger + the standard doc), reusing the existing
`/seal/<hash>` data and `/capabilities`. No new verification logic -- it is a trust-facing
presentation of what the engine already produces.
