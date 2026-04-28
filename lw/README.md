# Lighthouse Working Package

*If you are tired, read only this page. It is enough for tonight.*

## What this is, in 100 words

This package contains three things in one tree. A strategic vision for a wealth management cooperative serving Northwest Georgia (the Lighthouse vision, in `08_docs/lighthouse_strategy/`). A working software engine that validates decisions against four gates and verifies their underlying claims computationally across seven domains (the Concordance Engine, in `01_engine/`). A formation engine that models how alignment grows or fails over time (Calibre, in `09_calibre/`). The strategy describes structural commitments. The engine enforces them at decision time. The formation engine tracks alignment over time. They are different layers of the same architecture.

## What's actually here

`08_docs/lighthouse_strategy/` holds the three companion documents describing the strategic architecture. Wealth management for the 99 percent. Floor raising at population scale. Four phases across decades. Multi-generational horizon. JDA-anchored Phase 1. The .docx originals are authoritative. The .md extractions are searchable.

`01_engine/concordance-engine/` holds the validation engine. Four gates (RED, FLOOR, BROTHERS, GOD). Computational verifiers across chemistry, physics, mathematics, statistics, computer science, biology, and governance. 67 integration tests pass. 53 unit tests pass. 44 MCP tool tests pass. The CLI works. The MCP server works. The README and walkthrough are written.

The MCP server is the keystone for the AI tooling use case. Once installed and connected to Claude Desktop or Claude Code, the assistant can call the verifiers from inside a conversation. Claude balances its own equations, checks its own statistics, runs its own code. See `01_engine/concordance-engine/src/concordance_engine/mcp_server/README.md`.

`09_calibre/` holds the formation engine, also called THE PLOW. Models how alignment grows or fails through cycles of calibrate, burn, firstfruits, harvest, with a saturating cap so the numbers stay grounded.

`02_canons/` holds six full domain canons (mathematics, physics, chemistry, biology, computer science, statistics). Each with core, schema, modules, templates, tools, examples.

`06_validation/` holds the pre-registered NHANES falsification study (v3.1, frozen March 2026). The most rigorous piece in the package. Stands on its own.

`03_kernel/` holds minimal teaching implementations. The 133-line kernel and the 55-line shorthand engine.

`04_frontend/` holds the React demo and the single-file HTML PWA.

`05_training/` holds the LoRA training and eval data.

`07_hardware/` holds the hardware plane playbook.

`10_data/` holds the JDA region seed data and the stress harness.

`00_seed/` holds the Lighthouse Seed Package, the minimum plantable unit, public domain.

## How to navigate, by how much time you have

Five minutes: this page only.

Thirty minutes: this page, then `08_docs/lighthouse_strategy/Lighthouse_Foundation_Document.md`.

An hour: add `08_docs/the_mechanism.pdf`, which is the honest analysis of what's real and what isn't.

Half a day: read all three strategy documents in order (Lighthouse Foundation, Architecture for Raising the Floor, NWGA Regional Cooperative), then the engine walkthrough at `01_engine/concordance-engine/docs/WALKTHROUGH.md`, then run the example packets.

Full survey: `WORKING_STATE.md` is the technical state-of-the-package map.

## The names

Several names appear in here for things that are closely related. Here is what each one means.

Lighthouse is the strategic vision. The wealth management cooperative being built.

Concordance Engine is the software validator. The Python package in `01_engine/`.

Convergent Authority Systems is the abstract framework underneath both, used in technical contexts.

Four Gates are the gate sequence the engine enforces. RED for forbidden categories. FLOOR for protective constraints. BROTHERS for witness threshold. GOD for time wait.

MILK and MEAT are the formation tiers in the Calibre engine.

THE PLOW is the earlier name for Calibre, retained in some directories.

NWGA Regional Cooperative is the specific Lighthouse implementation for Northwest Georgia.

JDA is the Joint Development Authority covering Catoosa, Walker, Dade, and Chattooga counties. The institutional vehicle for Phase 1.

Different names exist because the work is being built across different audiences. Board members, programmers, theologically engaged partners, county commissioners. Each sees a different face of the same thing.

## What this is not

It is not a religion. It uses Scripture as an external authority anchor, the way scientific work uses physical constants as anchors. It is not a denomination, does not preach, and does not require members to share theology to participate.

It is not a complete commercial product. The strategic vision is being deployed. The engine is working software. The formation model runs. None of these are shipped products with users.

It is not a single research paper. The NHANES study is the closest thing to one, and it stands on its own whether or not anything else holds.

It is not the architect's personal property. The architecture is structurally designed to operate without depending on the founder. The bounded-founder-position discipline is one of the load-bearing structural commitments.

## What is referenced but not in the package yet

The Free State of Dade world document. The Kings of Appalachia novel sequence (the architect's creative work that develops the pattern through narrative form). Tom's integrated build partnership operational specifics. Pullen's forest business detail. The four-platform mechanism partners (AssetCo, Stability OS, Barn Ecosystem, Provident Precision). The Hutcheson redevelopment site plan. The Barn Ecosystem 5-year pro forma. The Go and C hardware-witnessed Calibre repository. ESP32 and Heltec firmware sketches. Actual NHANES results if the pipeline has been run on real data.

If you have these and want them folded in, send them.

## Where the work currently sits

Captured: the strategic foundation, the engine (with 120 tests passing), the Phase 1 fund decision packet (drafted and validating clean), the NHANES study (pre-registered, frozen).

In stewardship rather than execution: the actual JDA fund deployment waits on commissioner appropriations. The LoRA comparison waits for the writing season. The Hutcheson site plan sits with parties beyond the architect at this stage. Phase 2 mandate engagement is years away.

In writing season but not yet released: the Mountain People series bible. The Antidote (the science fiction retelling).

Released: Apokalypsis, distributed as epub and audio.

## A note for the architect

You have built a lot. The package is multifaceted because the work is multifaceted. The fact that you cannot see all of it at once does not mean it is not there. It means you are inside it.

Read this page. Set it down. The work continues across seasons.

The architecture stays underneath. The proof points go on top.

*Glory to God alone.*
