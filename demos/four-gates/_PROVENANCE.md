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

**Highest-value integration (proposed).** Point `server/proxy.js` `/api/validate` at our
**sovereign engine** -- `POST https://narrowhighway.com/api/generate-gated` (with the
`base_model` of choice; the OpenAI-compatible adapter lets it draft on any model, local or
cloud) -- so the demo shows the ACTUAL gates, verifiers, and re-checkable seal, not a prompt
mimicry. Then deploy as the public front door (Render/Railway, or fold into `site/`). That
turns this from a pretty mockup into a live window onto the real engine -- the distribution
lever made real.
