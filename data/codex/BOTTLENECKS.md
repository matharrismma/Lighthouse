# BOTTLENECK ATTACK -- adoption phase (Matt 2026-06-13: "This phase we attack bottlenecks on /loop")

THE BOTTLENECK (agreed): **adoption, not capability.** The engine works and the moat is real; the binding constraint is whether agents and people FIND it and reach for it WITHOUT FRICTION. The one move: be the easiest tool an agent ever reaches for.

LOOP RULE: the loop BUILDS the safe fixes (local files/code/content) and SURFACES the gated ones (DNS, public deploys, homepage, engine routes, security posture) with concrete diffs ready -- Matt pulls those triggers. Elegant bar: fewest steps from "agent lands" -> "gets a sealed receipt."

## A. AGENT ONBOARDING FRICTION (loop BUILDS)
- **#1 DONE -- llms.txt buried the frictionless path.** It led with `pip install`, listed only the OLD 11 MCP tools, and NEVER mentioned the hosted MCP URL, the one-POST `/derivation/verify` call, or the permanent `/seal/<hash>` receipt (the moat). REWROTE to lead with: zero-install hosted path + a real copy-paste one-call example (sin^2+cos^2=1 -> HOLDS, cite seal/e392836d) + the "permanent, independently-checkable receipt" pitch + 70+ verifier coverage + search/fetch discovery; kept the O(1) claim + pip install as secondary. (DEPLOY of the live narrowhighway.com/llms.txt is operator-gated -- SURFACE.)
- **#2 DONE -- OpenAPI spec.** Built `openapi.json` (repo root, valid 3.0.3, 4 paths / 10 schemas) describing POST /derivation/verify (3 modes), GET /seal/{hash}, GET /identity, GET /capabilities -- schemas VERIFIED against the live API (probed the GET shapes; /capabilities confirms 71 verifiers / 66 domains / 102 mcp tools). Committed+pushed. GATED: serving it (e.g. at narrowhighway.com/openapi.json) + optionally registering as a ChatGPT Action / GPT -- SURFACE.
- **#3 "Try it" artifact audit.** site/ten-second-proof.html exists -- AUDIT whether a visitor can actually verify + see a live seal in ~10s; sharpen to a copy-paste call + a clickable live cite_url. Same for proof-bridges.html.
- **#4 llms-full.txt mirror.** Ensure the full agent doc (if present/served) mirrors the new frictionless framing; if absent, consider one.

## B. DISCOVERABILITY (mixed)
- **#5 /atlas 404** (memory). A core route dead-ends -- a hard stop for an explorer. Diagnose; fix likely an engine route (GATED) -- prep the diff + SURFACE.
- **#6 Walk-up SEO** (memory). Meta tags / structured data (JSON-LD) / sitemap so humans find it. BUILD locally; deploy gated.
- **#7 Homepage -> wedge/MCP path.** The family homepage links none of the core (audience separation, not a bug) -- but a small, audience-appropriate footer link ("for your AI / for the technically curious" -> /mcp) is the on-ramp. GATED (most prominent public surface) -- SURFACE with the exact diff.

## C. GO-LIVE LEVERS (loop SURFACES only -- Matt's call)
- **#8 Deploy** public proof-bridges / coordinate-map / surface-map.
- **#9 .org / .tv routing** -- frame `.org` as the registry / NOTARY layer (the future trust layer for the agent economy: a neutral, permanent, citable seal-registry). `.tv` = gift/family.
- **#10 Scholars' wall.**
- **#11 'Concordance of Reality' in /identity.**
- **#12 SECURITY -- the pre-adoption gate (load-bearing).** Before driving agent traffic to a public sympy-backed endpoint: confirm the parser is safe (no arbitrary eval; parse_expr/sympify with safe settings), expression-size + compute limits (DoS guard), rate-limiting, scoped CORS (read-only, not a write surface). Do NOT probe/attack live endpoints -- this is a review item for the operator, but it gates pouring traffic in.

## DONE LOG (this phase)
- **#1 llms.txt front door** rewritten (hosted path + one-call + permanent seal + 70+ coverage); verified live; per-receipt-hash inaccuracy corrected. Committed+pushed. LIVE DEPLOY gated.
- **Fresh PUBLIC-ENDPOINT BENCHMARK** (Matt: "maybe we do a new set of benchmarks") -- `tools/benchmark_public_verify.py` (re-runnable) + `BENCHMARK_PUBLIC_VERIFY.md`: 52 ground-truth claims (26 true / 26 deliberately false) against the LIVE `/derivation/verify`; **52/52 correct, 0 false seals, 0 rejected truths** (2026-06-13). The load-bearing credibility number (no false-positives) on the exact surface agents call. Surfaced on the README front door + llms.txt. A VISIBILITY/credibility asset. Extensible (add to CLAIMS). Committed+pushed.
- **README front door** fixed: added "## Try it in one call (hosted, zero install)" near the top (curl + seal + /mcp + benchmark) -- the hosted moat was previously absent from the 413-line README (only `/submit` was mentioned).

## COURSE-CORRECTION (verify-before-build, tick #3/#4) -- the served surfaces already carry the moat
Probed the LIVE surfaces instead of assuming. Findings:
- **The served `/llms.txt` is `site/llms.txt`** (44KB, web root = site/), NOT the root `llms.txt` I rewrote in #1. The served file already welcomes agents + lists endpoints + a `/agents/daily.json` heartbeat (full endpoint catalog) -- but the MOAT (one-call verify->seal) was not the lede. CORRECTED: inserted a tight "## Verify a claim in one call (the moat)" section near the top of `site/llms.txt` (the real front door) -- the curl + seal + the 52/52 benchmark. (DEPLOY gated.) Root `llms.txt` is a secondary repo-root copy (my #1 edit there is harmless but low-impact).
- **The engine already auto-serves `/openapi.json`** -- OpenAPI 3.1, **471 paths**, with verify+seal. The memory "openapi omits moat" is STALE. BUT 471 paths is far too large for ChatGPT Actions (operation cap). So my new root `openapi.json` (3.0.3, 4 paths, verified-accurate) is USEFUL as a focused, Actions-ready spec -- keep it, framed as that, not as "filling a gap."
- **#3 try-it pages: ALREADY GOOD (no change).** site/ten-second-proof.html + site/proof-bridges.html both demonstrate the moat with CLICKABLE LIVE seals (verified 4+ resolve, integrity_verified=true, verdict HOLDS) + for-you/for-your-AI routing + honest apex-reserved footer. Did NOT pad.
- **#4 llms-full.txt EXISTS** (`site/llms-full.txt`). Did not touch this tick (the moat-first insert went to the primary `site/llms.txt`); a mirror is optional.
- **/atlas + /atlas-map 404** while `site/atlas-map.html` exists locally -> a routing/deploy gap (engine route, GATED).

NET: the served surfaces are already substantial -> the binding constraint is even more clearly **visibility/traffic + a few concrete GATED fixes**, NOT missing docs. The safe-build runway is largely spent; remaining levers are operator-gated.

## BUILD ALL IN PRIORITY (Matt 2026-06-13: "build all in priority")
Building every artifact to the EDGE of its gate; live switches stay Matt's (account/registration, live deploys, engine/route/security changes). Web server is NOT in this repo's src/ (live deploy) -> route/security items are review artifacts, not code changes.
- **P1 ChatGPT Action / Custom GPT** (biggest agent-visibility lever) -- BUILT: `docs/CHATGPT_ACTION_SETUP.md` (exact steps + GPT name/description/instructions + smoke tests) + `site/privacy.html` (DRAFT privacy policy, REQUIRED for a public GPT Action, flagged for operator verification). GATED: serve focused `openapi.json` at a public URL (the 471-path auto-spec is too big for Actions); create+publish the GPT (Matt's ChatGPT account); serve `/privacy`.
- **P2 Pre-traffic SECURITY gate** -- BUILT: `docs/PRE_TRAFFIC_SECURITY.md` (parser safety / size+compute limits / rate-limit incl. stricter on seal / scoped CORS / seal signing / observability). Review checklist for the operator; items 1-3 are must-haves before promotion. GATED (live server).
- **P3 .org = notary/registry** (future trust layer) -- BUILT: `docs/ORG_NOTARY_REGISTRY.md` (seal-lookup + public ledger + the standard + issuer transparency; reuses existing /seal + /capabilities). GATED (routing).
- **P4 deploy corrected site/llms.txt** (moat-first) -- READY; GATED switch.
- **P5 SEO** (walk-up visibility) -- TODO next tick: JSON-LD SoftwareApplication + meta description + canonical on the key landing pages (build LOCAL, deploy gated). VERIFY served pages first.
- **P6 /atlas + /atlas-map 404** -- TODO: diagnose precisely (page site/atlas-map.html exists; /atlas/paths is an engine endpoint per mcp_server; the public route is missing) -> write the exact route fix as a review note. GATED (engine route).
- **P7 homepage -> /mcp on-ramp** -- snippet provided in CHATGPT_ACTION_SETUP.md "also worth doing"; exact footer-link diff = small; GATED (live homepage edit).

## LOOP ORDER
Build A (#1 done -> #2 -> #3 -> #4) one per tick; then prep + SURFACE B/C with concrete diffs. After each safe build: commit explicit paths, SURFACE the deploy, short report. When the safe queue is exhausted, SURFACE the gated bundle for Matt and idle.
