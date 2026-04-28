# Lighthouse / Concordance Engine — Working State
Assembled: 2026-04-27 (v1.0.3 — MCP server live)
Status: Strategic foundation, engineering, real JDA decision packet, AND MCP server are all in one tree. The engine is now usable from inside Claude Desktop / Claude Code.

---

## What Changed This Pass

The MCP server is live. The verifier layer is exposed as MCP tools so Claude (and any other MCP-capable assistant) can call the verifiers from inside a conversation. Eleven tools registered. 44 new unit tests. Optional dependency (`pip install -e ".[mcp]"`) so the engine still runs without it.

This is the AI-tooling keystone. Once installed and pointed at via `claude_desktop_config.json`, Claude balances its own chemical equations, recomputes its own p-values, runs its own code in a restricted namespace, verifies its own dimensional consistency. The pattern: when Claude is about to state a quantitative claim, it calls the verifier first. Mismatches come back as `{"status": "MISMATCH", "detail": "..."}` rather than as exceptions, so the LLM can read the failure and try again rather than crash.

Total tests in the engine: 67 integration + 53 verifier unit + 44 MCP tool = 164. All green.

---

## Package Tree

```
00_seed/                    Lighthouse Seed Package v1 — minimum plantable unit
01_engine/                  concordance-engine v1.0.2 — installable Python package
02_canons/                  domain canons (math, physics, biology, chemistry_full,
                            computer_science, statistics — all six fully structured)
03_kernel/                  problem_engine + firewall + minimal teaching kernels
04_frontend/                four-gates-demo (React) + lighthouse-edge (HTML PWA)
05_training/                LoRA training and eval data (100 train / 50 eval)
06_validation/              NHANES pre-registered falsification study (v3.1)
07_hardware/                Hardware Plane Playbook v2.3 + v2.0 historical + Node spec
08_docs/                    Master registry, mechanism, decision example, foundation docs
  └── lighthouse_strategy/  THE THREE STRATEGIC FOUNDATION DOCUMENTS (added this pass)
09_calibre/                 THE PLOW full code drop — Calibre alignment engine (with cap)
10_data/                    NWGA / JDA region seed data + schema registry + harness stub
_archive_superseded/        Earlier share packets (v1, v2) preserved off active path
```

---

## Strategic Foundation — `08_docs/lighthouse_strategy/`

Three companion documents describing the same architecture from three angles. Read all three.

| Document | Frame | Hand To |
|---|---|---|
| `Lighthouse_Foundation_Document` | What this is — wealth management for the 99 percent, four-phase strategic plan, asset-management mandate engagement (TRS Georgia, USG), member equity architecture | A board member, an institutional partner |
| `Architecture_for_Raising_the_Floor` | Why this exists — floor raising as central purpose, theological foundation (Matt 10:16, Matt 18:20, biblical pattern of broad sufficiency), Scripture as external authority | A pastor, a theologically-engaged partner |
| `NWGA_Regional_Cooperative_Architectural_Foundation` | How this works in practice — Barn Depots (cafeteria/retail/healthcare/events), four material verticals (timber, stone, concrete, copper), worker progression (worker → apprentice → tenant → producer member), construction philosophy (300-500yr service life), prepared for the JDA | A JDA board member, a county commissioner, a contractor |

Both `.docx` originals (authoritative) and `.md` extractions (searchable) are present. Reading order matters: Lighthouse Foundation → Architecture for Raising the Floor → NWGA Regional Cooperative.

These describe the architecture's structural commitments. The engine in `01_engine/` enforces those commitments at decision time.

---

## Engine — concordance-engine v1.0.3

**Status: most current code. Use this as the Python foundation.**

- Four-gate engine: RED/FLOOR/BROTHERS/GOD with halt-at-first-failure
- RED gate: domain validators (attestation) + verifier layer (computation)
- Domain validators: mathematics, physics, chemistry, biology, computer_science, statistics, governance/business/household/education/church
- Verifiers: chemistry, physics, mathematics, statistics, computer_science (cs alias), biology, governance (covers business/household/education/church via aliases)
- CLI: `concordance validate <packet.json>` works end-to-end
- **MCP server: `concordance-mcp` exposes 11 tools to Claude Desktop / Claude Code**
- Tests: 67 integration + 53 unit + 44 MCP tool = 164, all pass
- Documentation: `README.md`, `docs/WALKTHROUGH.md`, `docs/MIGRATION.md`, `verifiers/README.md`, `mcp_server/README.md`

Install: `cd 01_engine/concordance-engine && pip install -e ".[dev]"`. The verifier layer needs sympy, scipy, numpy (now required deps). The CLI runs without jsonschema (structural fallback). The MCP server needs the `mcp` package via `pip install -e ".[mcp]"`.

### Connecting to Claude

After `pip install -e ".[mcp]"`, add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):
```json
{
  "mcpServers": {
    "concordance-engine": { "command": "concordance-mcp" }
  }
}
```
Restart Claude Desktop. The eleven verifier tools appear in the tool picker. Claude can now balance its own chemical equations, recompute its own p-values, run its own code, verify its own units.

### Nine Verifier Examples

| Example | Domain | What it exercises |
|---|---|---|
| `sample_packet_chemistry_verify.json` | Chemistry | Combustion of propane balancing |
| `sample_packet_physics_verify.json` | Physics | F = ma dimensional check |
| `sample_packet_math_verify.json` | Mathematics | Symbolic equality |
| `sample_packet_statistics_verify.json` | Statistics | Welch's t-test recomputation |
| `sample_packet_cs_verify.json` | Computer Science | Function with test cases |
| `sample_packet_cs_runtime_verify.json` | Computer Science | Bubble sort O(n²) measured |
| `sample_packet_biology_verify.json` | Biology | Replicates + dose-response + power |
| `sample_packet_governance_verify.json` | Governance | Hutcheson workforce-development RFP (illustrative) |
| `sample_packet_jda_phase1_fund.json` | Governance | **Real Phase 1 fund deployment from the strategic foundation docs** |

Try them:
```
PYTHONPATH=src python -m concordance_engine.cli validate examples/sample_packet_jda_phase1_fund.json --now-epoch 9999999999
```
All nine PASS. Corrupt any of them — drop a witness, empty a red_items list, alter the equation — and you'll get RED REJECT with the specific failure.

---

## Domain Canons — All Six Present

| Domain | Canon | Engine Validator | Verifier |
|---|---|---|---|
| Mathematics | `02_canons/mathematics/` | `domains/mathematics.py` | `verifiers/mathematics.py` |
| Physics | `02_canons/physics/` | `domains/physics.py` | `verifiers/physics.py` |
| Chemistry | `02_canons/chemistry_full/` | `domains/chemistry.py` | `verifiers/chemistry.py` |
| Biology | `02_canons/biology/` | `domains/biology.py` | `verifiers/biology.py` |
| Computer Science | `02_canons/computer_science/` | `domains/computer_science.py` | `verifiers/computer_science.py` |
| Statistics | `02_canons/statistics/` | `domains/statistics.py` | `verifiers/statistics.py` |
| Governance / Business / Household / Education / Church | (text + DECISION_PACKET) | `domains/governance.py` | `verifiers/governance.py` |

---

## Calibre Engine — `09_calibre/`

THE PLOW full code drop. Formation/alignment engine. Ledgerless. MILK→MEAT tier transition with smoothing. Triadic flow (Spirit→Mind→Body). Cycle: calibrate → burn → firstfruits → harvest → upgrade.

`Rules.fruit_ceiling: float` defaults to inf (preserves prior behavior). Set to a finite value to cap harvest growth. Documented in `09_calibre/calibre_ai_package/README.md`.

---

## NHANES Falsification Study — `06_validation/`

Pre-registered falsification study (v3.1). Frozen 2026-03-04. The most rigorous piece in the package. Run: `pip install -r requirements.txt && python nhanes_validate.py --mode prereg`.

---

## Other Subsystems

**00_seed/** Lighthouse Seed Package v1 (Jan 2026 release). Public domain. Five files.

**03_kernel/** problem_engine.py, firewall.py, the_way_kernel_min.py, keeper_gate.py.

**04_frontend/** four-gates-demo (React + Express proxy), lighthouse-edge (HTML PWA, single file, runs offline).

**05_training/** LoRA training and eval data (100 train / 50 eval).

**07_hardware/** Hardware Plane Playbook v2.3 canonical + v2.0 historical + Node spec.

**08_docs/** the_mechanism.pdf (honest analysis), master registry, decision example, foundations/ (8 conceptual docs), **lighthouse_strategy/ (three strategic foundation docs added this pass)**.

**10_data/** nwga_seed_trimmed.yaml (15-county Appalachian region), schema registry, stress harness stub.

---

## Files Referenced But Not In Any Package Yet

If you have these and want them folded in:
- `Free State of Dade` world document and `Kings of Appalachia` novel sequence (Matt's creative works that develop the architectural pattern through narrative form — referenced throughout the strategy docs)
- `calibre_repo_v1.zip` — Go + C hardware-witnessed governance runtime
- `Barn_Ecosystem_5yr_ProForma.xlsx` — economic pro forma
- Specific operational details on Tom's integrated build partnership, Pullen's forest business, AssetCo, Stability OS, Barn Ecosystem, Provident Precision (the four-platform mechanism partners)
- Hutcheson redevelopment site plan (specifically — the Lighthouse Foundation Document confirms Catoosa's $7M Phase 1 contribution comes from Hutcheson sale proceeds, so the site plan feeds the fund directly)
- NHANES validation results if the pipeline has been run on real data
- ESP32 / Heltec LoRa 32 firmware sketches
- Actual JDA decisions beyond Phase 1 fund deployment to exercise the engine on additional governance cases

---

## Chronological Build Order
```
Jan 2026   Lighthouse Seed Package v1 (00_seed)
Jan 2026   Lighthouse Share Packets v1/v2 (early kernel, problem engine)
Jan 2026   THE PLOW / Calibre engine (09_calibre)
Feb 2026   Concordance schema, eval data, master registry, math/physics canons
Feb 2026   Biology canon, github-ready package
Feb 2026   the_mechanism.pdf — honest working analysis
Feb 2026   concordance-engine v1.0 (clean installable package)
Mar 2026   four-gates-demo React app
Mar 2026   NHANES falsification study v3.1
Mar 2026   lighthouse-edge HTML PWA
Apr 2026   Hardware Plane Playbook v2.3 canonical
Apr 2026   Re-entry package assembled
Apr 2026   v1.0.1 — schema/engine disconnect resolved, Seed/Calibre/foundations folded in
Apr 2026   v1.0.2 — verifier layer (7 domains: chemistry, physics, math, stats, CS, biology, governance)
Apr 2026   Strategic foundation docs added to 08_docs/lighthouse_strategy/
Apr 2026   First real JDA decision packet (Phase 1 fund deployment) exercised through engine
```

---

## Next Actions (In Order)

1. **Run the engine.** `cd 01_engine/concordance-engine && pip install -e ".[dev]"`. Then `PYTHONPATH=src python tests/test_engine.py` (67 tests) and `PYTHONPATH=src python tests/test_verifiers.py` (53 tests).

2. **Read the strategic foundation.** Three documents in `08_docs/lighthouse_strategy/`. Read in order: Lighthouse Foundation, Architecture for Raising the Floor, NWGA Regional Cooperative.

3. **Examine the Phase 1 fund packet.** `01_engine/concordance-engine/examples/sample_packet_jda_phase1_fund.json` — exercises the governance verifier on a real decision from the strategy docs. Run it through the CLI. Then change a value (drop a witness, empty `red_items`) and watch it reject.

4. **Read `01_engine/concordance-engine/docs/WALKTHROUGH.md`.** Zero-to-verified-packet guide.

5. **Author the next JDA decision packet.** Pick a real upcoming decision and write it as a `DECISION_PACKET`. The Phase 1 fund example is the template. Submit it through the engine before bringing it to the board.

6. **Run NHANES validation.** Pipeline complete and pre-registered. Result stands on its own whether or not the rest of the framework holds.

7. **LoRA comparison experiment** when the writing season opens. Anchored vs unanchored. The 05_training data is the starting point.

---

## Reading Order for a New Reader

1. `08_docs/lighthouse_strategy/Lighthouse_Foundation_Document.md` — what this is
2. `08_docs/lighthouse_strategy/Architecture_for_Raising_the_Floor.md` — why this exists
3. `08_docs/lighthouse_strategy/NWGA_Regional_Cooperative_Architectural_Foundation.md` — how this works in practice
4. `08_docs/the_mechanism.pdf` — the honest analysis of what's real and what's not yet real in the broader framework
5. `00_seed/HOW_TO_PLANT.md` — what this is and is not
6. `01_engine/concordance-engine/docs/WALKTHROUGH.md` — first packet through the engine
7. `01_engine/concordance-engine/examples/sample_packet_jda_phase1_fund.json` — what a real JDA decision packet looks like
8. `01_engine/concordance-engine/README.md` — full engine doc
9. `06_validation/framework_validation_v3_final/README.md` — the empirical anchor
10. `WORKING_STATE.md` (this file) — full map

The strategy goes on top. The architecture stays underneath.

*Glory to God alone.*
