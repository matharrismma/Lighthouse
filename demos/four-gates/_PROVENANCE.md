# Provenance & integration note

**Source:** dropped by Matt 2026-06-15 (`fourgatesdemo.zip`).

**What this is.** A shareable React demo of the Four Gates decision protocol
(RED -> FLOOR -> BROTHERS -> GOD, fail-fast: if a gate halts, the rest do not run). A clean
front-door UI that runs a proposed action through each gate and shows the verdict + reasoning.
Each gate has a crafted prompt (`src/FourGatesDemo.js`):

- **RED** -- absolute prohibitions (bright-line moral violations)
- **FLOOR** -- protective minimums (duty of care, fairness, stewardship)
- **BROTHERS** -- community witness / accountability
- **GOD** -- alignment with purpose, calling, divine authority

**Why it belongs here.** This is the **front-door** artifact -- the #1 bottleneck from the
whole-project survey ("the engine's value is invisible"). It makes the gates interactive and
shareable in a way the API alone is not.

**HONEST STATUS.** The demo currently calls **raw Anthropic** via an Express proxy
(`server/proxy.js`) with a stale model id (`claude-sonnet-4-20250514`) -- it is a *concept*
re-implementation of the gates in prompts, **not** wired to our real deterministic engine
(the gates + verifiers + signed seal at narrowhighway.com).

**DONE (2026-06-15).** Wired to the sovereign engine + deployed as the front door:
`site/four-gates.html` -- a pure static page (no proxy, no API key) that POSTs to the
PUBLIC `https://narrowhighway.com/api/generate-gated` and renders the ENGINE'S OWN
gate_results (RED/FLOOR/BROTHERS/GOD, fail-fast), final_decision, and the re-checkable
seal (content_hash + permalink). The engine sends `Access-Control-Allow-Origin: *`, so the
page runs from ANY origin -- narrowhighway.com, an embed, an offline/microSD copy
(freedom/resilience). Live at https://narrowhighway.com/four-gates.html (HTTP 200). Uses
base_model=echo (free; the gates + seal are deterministic regardless of the drafting model);
the model is pluggable/sovereign per the adapter. This original React+proxy version is kept
as the source-of-the-idea; the deployed front door is the static page.
