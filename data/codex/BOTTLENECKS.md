# BOTTLENECK ATTACK -- adoption phase (Matt 2026-06-13: "This phase we attack bottlenecks on /loop")

THE BOTTLENECK (agreed): **adoption, not capability.** The engine works and the moat is real; the binding constraint is whether agents and people FIND it and reach for it WITHOUT FRICTION. The one move: be the easiest tool an agent ever reaches for.

LOOP RULE: the loop BUILDS the safe fixes (local files/code/content) and SURFACES the gated ones (DNS, public deploys, homepage, engine routes, security posture) with concrete diffs ready -- Matt pulls those triggers. Elegant bar: fewest steps from "agent lands" -> "gets a sealed receipt."

## A. AGENT ONBOARDING FRICTION (loop BUILDS)
- **#1 DONE -- llms.txt buried the frictionless path.** It led with `pip install`, listed only the OLD 11 MCP tools, and NEVER mentioned the hosted MCP URL, the one-POST `/derivation/verify` call, or the permanent `/seal/<hash>` receipt (the moat). REWROTE to lead with: zero-install hosted path + a real copy-paste one-call example (sin^2+cos^2=1 -> HOLDS, cite seal/e392836d) + the "permanent, independently-checkable receipt" pitch + 70+ verifier coverage + search/fetch discovery; kept the O(1) claim + pip install as secondary. (DEPLOY of the live narrowhighway.com/llms.txt is operator-gated -- SURFACE.)
- **#2 OpenAPI / actions spec.** Memory: "openapi-actions omits moat"; none found in repo. The standard discovery artifact for ChatGPT Actions / agent tool-builders is missing or omits the verify+seal endpoints. BUILD a clean `openapi.json` (paths: POST /derivation/verify, GET /seal/{hash}, GET /identity, GET /capabilities) with accurate schemas. (Deploy/wiring gated.)
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

## LOOP ORDER
Build A (#1 done -> #2 -> #3 -> #4) one per tick; then prep + SURFACE B/C with concrete diffs. After each safe build: commit explicit paths, SURFACE the deploy, short report. When the safe queue is exhausted, SURFACE the gated bundle for Matt and idle.
