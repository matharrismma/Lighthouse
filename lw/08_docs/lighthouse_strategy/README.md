# Lighthouse Strategy — Foundation Documents

Three companion documents describing the same architecture from three angles. Read together, not separately. Each emphasizes a different framing of the same underlying structure.

## The Three Documents

### `Lighthouse_Foundation_Document` — What This Is
Frames the architecture as **wealth management for the 99 percent**. Same tools as commercial asset managers (BlackRock-class operations) at scale, opposite purpose: serving member family wealth and broader community substance rather than corporate shareholder return. Covers the four-phase strategic plan from foundation cell launch (years 1–7) through multi-generational deployment (year 25+), the asset-management mandate engagement strategy (TRS Georgia, University System of Georgia), and the member equity architecture with floor protection, accumulation through participation, and borrowing against balance.

This is the doc to hand to a board member, a potential institutional partner, or anyone who wants to know what category of thing Lighthouse is.

### `Architecture_for_Raising_the_Floor` — Why This Exists
Frames the architecture around the **central purpose: raise the floor**. Every member family operates from an economic baseline that cannot be drawn below regardless of circumstance. The floor rises as the architecture's substance grows across decades. Population-wide economic security combined with population-wide economic capacity rather than concentration in elite minority. Develops the theological foundation more thoroughly than the Lighthouse Foundation Document — the biblical pattern of broad sufficiency (Jubilee, Sabbath economics, gleaning provisions), Matthew 10:16 (wise as serpents, harmless as doves), Matthew 18:20 (cross-denominational connective infrastructure), and Scripture as external authority replacing self-referential consensus.

This is the doc to hand to a pastor, a theologically-engaged partner, or anyone asking why the framework holds.

### `NWGA_Regional_Cooperative_Architectural_Foundation` — How This Works in Practice
The most operationally detailed of the three. Prepared for the **Joint Development Authority** specifically. Covers the Barn Depots (cafeteria + retail floor + wholesale pickup + events space + beverage program + healthcare with doctor/dentist/vet), the four material verticals (timber, stone, concrete, copper) through Tom's integrated build partnership, the worker progression structure (worker → apprentice → tenant farmer → producer cooperative member), the producer cooperative member program package ($4K-$7K monthly draws, comprehensive benefits, $1M transition insurance, primary customer commitment), construction philosophy (300-500 year service life, poured concrete, stone veneer, slate roofs, copper rain handling), housing infrastructure, logistics (rail, sea, Marion County terminal), and the regional industrial heritage thesis.

This is the doc to hand to a JDA board member, a county commissioner, or a contractor evaluating whether to participate.

## How They Relate to the Engineering

These documents describe the architecture's **structural commitments**. The Concordance Engine in `01_engine/` and the verifier layer enforce those commitments at decision time. When a JDA proposal comes through, the engine's `DECISION_PACKET` verifier checks whether it has all the required parts (RED items declared, FLOOR items declared, witnesses, scope, way path) and the engine's gate sequence checks whether it can proceed (RED/FLOOR pass, BROTHERS witness threshold, GOD wait window). The structural commitments these documents describe are what the verifier is looking for.

See `examples/sample_packet_jda_phase1_fund.json` in `01_engine/concordance-engine/examples/` for an example DECISION_PACKET based on the Phase 1 fund mechanism described in these documents.

## What's Not in These Docs (But Referenced)

- The `Free State of Dade` world document (Matt's creative work)
- The `Kings of Appalachia` novel sequence (Matt's creative work)
- `AssetCo`, `Stability OS`, `Barn Ecosystem`, `Provident Precision` (the four-platform mechanism partners)
- `Pullen's forest business operations` (institutional fabric mentioned without detail)
- `Tom's integrated build partnership` (operational detail referenced but not fully specified)
- `Hutcheson Hospital site` redevelopment plan (specific site plan)
- `Barn Ecosystem 5-yr ProForma` (the financial projection)

The Lighthouse Foundation Document mentions Catoosa contributing $7M from Hutcheson Hospital sale proceeds — so the Hutcheson site work feeds the Phase 1 fund directly.

## Reading Order

1. `Lighthouse_Foundation_Document` first — the highest-level frame
2. `Architecture_for_Raising_the_Floor` second — the theological and purpose grounding
3. `NWGA_Regional_Cooperative_Architectural_Foundation` third — the operational blueprint

The .docx originals are authoritative. The .md extractions are searchable companions.

*Glory to God alone.*
