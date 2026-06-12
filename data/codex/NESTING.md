# The Nesting — two trees, one ground

**Matt 2026-06-12:** "I need you to look at all of the cards. We need everything to nest into a system. It is still disjointed." ... and then: *"It may always be two trees. That's how it started."*

**The correction (2026-06-12).** The goal was never to merge everything into ONE tree. The garden had **two trees from the start** — the Tree of Life and the Tree of the Knowledge of Good and Evil (Genesis 2:9) — in *one* garden, *one* ground, *one* Gardener. Two trees is the original design, not a defect. So this document does NOT fuse the codex and the map of reality into one tree; it names the single **ground** both are planted in. It does not replace [STRUCTURE.md](STRUCTURE.md) (the codex's three layers) or [AUTHORITY_SPINE.md](AUTHORITY_SPINE.md) (the four authority tiers) — it gives both trees, and the verified map of reality, one rooted ground: **Christ, in whom all things consist.**

## Why it felt disjointed (the diagnosis, 2026-06-12)

A survey of all 11,085 cards in `data/cards/` + ~1,300 almanac rows found:
- **Two trees, but no shared ground in the data.** The *codex* (Scripture, Easton's dictionary, patristics, classics — the `connections`/`dictionary`/`classics`/`codex`/`patristics` shelves, ~9,000 cards) and the *map of reality* (`connection_reality_is_mappable` + the cluster capstones, in the almanac) had **no common root node**. Two trees is right; *unrooted* trees is the defect.
- **32% orphans.** 3,623 cards have **zero** connections; average degree 1.61. A third of the body floats free.

The fix is not to graft the trees together — it is to name the **ground** every card descends from, so nothing is rootless. (Orphans: fixed 2026-06-12, 3,623 -> 0, reversible manifest `nesting_orphan_links_2026-06-12.json`.)

## The one ground

> **The ground — Christ, the logos.**
> *"In him all things consist / hold together"* (Colossians 1:17). *"All things were made by him"* (John 1:3).

The ceiling of the [authority spine](AUTHORITY_SPINE.md) — the Words in Red — is also the **ground of the whole system**. Everything is interpreted *through* Him and is rooted *in* Him. Two trees grow from this one ground — the two books, Scripture and Creation (*"The heavens declare the glory of God"*, Psalm 19:1; Romans 1:20). They are not merged; they are co-rooted.

```
THE GROUND — Christ, the logos (Col 1:17; John 1:3)
|
+== TREE I — THE BODY  (special revelation: the Word, the chosen texts)
|     Tier 1  Words in Red            [the ground, made text]
|     Tier 2  The Bible (66 books)    [shelves: codex, dictionary(Easton->scripture)]
|     Tier 3  Disciples + Didache + Fathers   [shelves: patristics, classics]
|     Tier 4  Matt's writing — lens, not authority   [serials: KOA, Apokalypsis, Molasses]
|     Indexes: scripture / person / place / theme   (codex Layer 3)
|
+== TREE II — THE MAP OF REALITY  (general revelation: the Works of God)
      Crown:  connection_reality_is_mappable  ("same structure recurs; we map, never author")
      Cluster capstones (each crowns a domain):
        number_theory / geometry / geoscience(earth) / music / chemistry /
        statistics / computer-science / genetics / relativity / the body / tools
        + law-family capstones (decay, conservation, inverse-square, transport, logarithm, harmonics, calculus)
      -> families (the periodic-map coord: family x level x domain x block)
      -> connection / located cards
      -> sayings (the Almanac — the human face)
```

## Two trees, one ground (not one tree)

The two trees stay two — the Word and the Works, special and general revelation — but they share **one ground**: creation is consistently mappable *because* it was made through the logos and holds together in him (John 1:3; Col 1:17). Tree II is not a rival to Tree I; it is the works confirming the Word. We do not graft them into a single trunk; we confess the **ground** they are both planted in.

**The lifecycle bookends (Matt 2026-06-12).** The system has a boot and an end, and John frames both:
- **Genesis = the boot.** Creation is the system coming online — light, the ordering, the modules; and the two trees are *planted* (Gen 2:9).
- **Revelation = the other end.** The consummation, where the **Tree of Life is restored** (Rev 22:2, its leaves for the healing of the nations) and the curse on the ground is lifted.
- **John bookends the run.** *"In the beginning was the Word"* (John 1:1) at the boot; the Revelation (John's) at the end. The logos opens the system and seals it.

The single keystone that names this ground explicitly — `connection_reality_is_mappable` rooted into Col 1:17 / John 1, and the redemptive-epochs arc — is **reserved for Phase 3 (the Jesus focus)**, authored with the most care. It is not a graft that makes the trees one; it is the confession of the ground that already holds them both.

## The nesting rule (every card gets a home)

Every card must resolve to a path: **root -> branch -> (tier | capstone) -> box/family -> card.** Resolve in this order:
1. **shelf -> branch/tier.** `codex`/`dictionary` -> Branch I Tier 2; `patristics`/`classics` -> Tier 3; serials -> Tier 4; almanac science -> Branch II under its cluster capstone; `recipes`/`maker`/`hearth` -> the Maker/Hearth practical leaf of Branch I (applied, under Tier 2-4 wisdom).
2. **box -> family.** The `box` (e.g. `dictionary_cites_matthew`) is the sub-cluster; the `bands` (cites, concept, person, place, proof_text...) are the cross-links.
3. **capstone -> domain.** Each almanac connection card nests under its cluster capstone via `coord.family`; each capstone nests under `reality_is_mappable`.
4. **orphans.** A card with zero `connections` is nested by giving it at least one edge: to its box-siblings (sequence prev/next), to the scripture/person/place it names (band -> index), or to its cluster capstone. **No card may remain at zero.**

## The work to make the data match this spec

1. **Connect the 3,623 orphans** — a systematic, rule-based pass (box-siblings, band->index edges, capstone parent). Deterministic, witness-gated, reversible. Reduces zero-degree to 0%.
2. **Set the parent/crown edges** for Branch II — each connection card -> its capstone; each capstone -> `reality_is_mappable`.
3. **Phase 3 keystone** — author the Col 1:17 / John 1 join that roots Branch II into Tier 1 (the Words in Red). The final nest.
4. **Rebuild the codex indexes** (`python -m api.codex`) so the navigational surfaces reflect the one tree, and re-seal the signed artifact.

When these four are done, every card descends from the one root, and nothing floats free.
