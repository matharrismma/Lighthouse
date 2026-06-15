# Licensing

One principle, three parts. **You can use, copy, run, and replicate all of this
freely. You just can't enclose it** -- take what was given freely and lock it
away from everyone else.

## The structure

| Part | License | What it means |
|---|---|---|
| **Code** (`src/`, `api/`, `tools/`, etc.) | [GNU AGPL-3.0-or-later](LICENSE) | Use, modify, run, redistribute freely. If you run a *modified* version as a network service, you must publish your changes. |
| **Content we author** (the corpus `data/`, cards, the map, seals, docs) | [CC BY-SA 4.0](LICENSE-CONTENT) | Share and adapt freely, **with attribution**, keeping derivatives under the same license. |
| **Third-party data** (`lw/00_source/`) | each keeps its own | External sources (GeoNames, OEIS, WordNet, NCBI, USDA, openFDA, UCUM, ...) keep their upstream licenses and attribution. Our license never overrides theirs. See `NOTICE` and [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md). |

Anything in this repository not otherwise marked is **AGPL-3.0** (if code) or
**CC BY-SA 4.0** (if content), Copyright (c) 2026 Matthew R. Harris.

## Why these two (and not a permissive license)

The mission is to give freely and to *keep* it given -- so it can replicate
everywhere, be owned hand to hand, and never be lost or fenced off. AGPL and
CC BY-SA are both **share-alike**: they hand the work to everyone *and* guarantee
it stays handed to everyone. A permissive license (MIT/Apache/CC0) would also
give it away, but would let someone take a derivative and close it. We chose the
steward's posture: give it all away, and guard it so it can't be enclosed.

A key practical point: **AGPL does not cost adoption.** It only binds someone who
*forks and hosts the code themselves*. Anyone using the hosted API / MCP is
completely free and unaffected.

## Using it commercially

Commercial use is **free** as long as you honor the open licenses (keep your
modifications open under AGPL / CC BY-SA). A **commercial license** is needed only
if a company wants to use it *without* the share-alike terms -- e.g. inside a
closed product or a modified private service. In that case the contribution funds
the mission's giving. See [`COMMERCIAL.md`](COMMERCIAL.md).

## Existing sub-licenses

A few sub-directories carry their own, more-permissive license, retained from
earlier in the project:

- `lw/00_seed/` -- released to the **public domain** (the foundational seed,
  given with no claim).
- `lw/02_canons/` -- **MIT**.

These remain as marked. (If we later bring them under the share-alike umbrella
for full anti-enclosure protection, this file will say so.)

## Contributing

Because the code is offered under a commercial license as well as AGPL, the
project must be able to relicense contributions. Until a formal contributor
agreement is in place, please open an issue to discuss before sending code, so
provenance stays clean.
