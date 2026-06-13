# Accessibility / Structure / Security / Routing / Visual-Mapping Review

**Matt 2026-06-13 (high-priority /loop, 60s):** "Review the entire project. Make sure it is forming the correct structure, not blocking access, not allowing attack. Make it accessible to Humans and agents. Use and map the use of .org and .tv to move periphery tools and content. Map everything you can visually -- but it must have a map/visual location."

The working doc for this loop. Each 60s tick takes ONE queue item: build the SAFE ones, SURFACE the operator-gated ones. Elegant bar: simple, durable, fewest steps. WE ARE THE CONCORDANCE OF REALITY -- a clean mirror; accessible, safe, every thing placed.

## Access points (present -- baseline good)
- **HUMANS:** 151 `site/*.html`. Entries: index, atlas + atlas-map, almanac, codex(+xref/themes/deep/seal), map, coordinate-map, proof + proof-bridges + ten-second-proof, gates, about, roadmap.
- **AGENTS:** `llms.txt` + `llms-full.txt` (orientation, well-written), `mcp.html`, `robots.txt`, `sitemap*.xml`; live `https://narrowhighway.com/mcp` (+ OpenAI search/fetch tools), `/identity`, `/capabilities`, `/scripture/original`, `/derivation/verify`, `/seal/<hash>`.

## Findings by dimension

### 1. Accessibility (humans + agents) -- GOOD, with ease-of-use items
- Agent surface is real (llms.txt welcomes agents; MCP live). Human entries exist.
- TO VERIFY/IMPROVE (safe): does `index.html` orient a first-time human to the core (the proofs, the maps, the Concordance) in one clear path? Is the coordinate-map linked from the entry? Is navigation between core surfaces clear? Ease-of-use = fewest steps to "open a seal / see the map / understand the two trees."

### 2. Security / attack surface
- **GOOD:** secrets are gitignored (`*passphrase*`, `.env`, `*API*.txt`, `client_secret_*.json`, session-handoff docs). No secret files tracked.
- **VERIFY (operator-gated -- surface, do NOT change posture):**
  - `/derivation/verify` accepts user-supplied expressions (sympy). CONFIRM the parser is safe (no arbitrary `eval`; use `parse_expr`/sympify with safe settings), with expression-size + compute limits (DoS guard) and rate-limiting on public endpoints.
  - CORS policy on public endpoints (agents need access; keep it scoped, not a write surface).
  - `local/rotate_tunnel_token.ps1` is tracked -- confirm it holds NO hardcoded secret (it should only rotate/reference).
  - Keep-page IP/token lockout (already designed) -- confirm still sound.
  - Do NOT probe/attack live endpoints; these are review items for the operator.

### 3. Correct structure (core vs periphery)
- CORE (.com -- the Concordance): atlas/almanac/codex/maps/proofs/scripture/gates/mcp/agents/identity/capabilities + the coordinate map.
- PERIPHERY (route to .tv / .org): channels, door-tv, church-streams, watch-listen, games, bible-trivia, kids, hymns, pilots, recipes + submit-recipe, hearth, marketplace, take-part, apokalypsis/apothecary/archetypes/serials (the gift/family + commerce sprawl).
- 117 pages need finer core/periphery classification (next ticks).

### 4. Visual mapping -- the GAP
- Cards ARE mapped: `coordinate-map.html` places 1540 cards (4-axis cruciform, in progress).
- SURFACES are NOT: the 151 pages, the tools, the .tv/.org content have NO visual/map location. Matt's rule: "everything must have a map/visual location."
- FIX (safe): build a SURFACE MAP -- a visual placement of every page/tool/content (core spine on .com; periphery routed to .tv/.org), integrated with / linked from the coordinate map. Every surface gets a coordinate too (the LAYERS depth axis = where it sits).

### 5. Routing periphery to .org / .tv (the lean-in)
- `.com` = the app/core (the Concordance, proofs, maps, MCP). `.org` = authority/registry layer. `.tv` = gift/family (curated, free) -- the sprawl-as-gift.
- The actual DNS/deploy MOVE of live content is OPERATOR-GATED (surface, do not execute). What the loop CAN do safely: produce the routing MAP (which surface -> which domain/layer) and the visual placement.

## FIX QUEUE (one per tick)
**SAFE -- loop builds:**
1. Finish classifying all 151 pages: core / periphery (.tv|.org) / tool. Output a routing table in this doc.
2. Build the SURFACE MAP (visual/map location for every page, tool, content), integrated with the coordinate map; everything gets a coordinate.
3. Ease-of-use: verify index.html -> core path is one clear step; link coordinate-map + proofs + the two-trees explainer from the entry.
4. Ensure no surface is orphaned (every page reachable + placed).

**OPERATOR-GATED -- surface, do NOT execute:**
- Security: confirm verify-endpoint parser safety + CORS + rate-limit + size limits; check rotate_tunnel_token.ps1; keep-page lockout.
- Routing: the live .org/.tv DNS/deploy moves of periphery content.
- Deploys of public pages (proof-bridges.html, coordinate-map.html, the surface map); reflect "Concordance of Reality" in /identity.

## DONE -- Surface map (tick 2)
Built `tools/surface_map.py` (re-runnable) -> `data/codex/surface_map.json` + `site/surface-map.html`. **All 151 surfaces now have a visual/map location**, placed by domain: **.com 123** (core -- the Concordance), **.org 11** (authority/registry/community), **.tv 17** (gift/family content). The page is the **routing PLAN** (periphery -> .org/.tv so the core stays lean); the actual DNS/deploy MOVES are operator-gated. Companion to coordinate-map.html (cards) -- now both cards AND surfaces are mapped; nothing lacks a place. NEXT (tick 3): ease-of-use (index -> core path); classification is heuristic -- refine .com=123 (many defaulted) into finer core/tool/periphery as the project settles.

## DEVELOP-TO-ACCURACY -- stiffen toward Maxwell-rigidity (Matt + Maxwell's rule)
The model is a framework; Maxwell's rule (bars = 2j-3) is its accuracy measure. **Rigidity ratio (1.0 = just-rigid) is the tracked number; climb it ONLY with TRUE braces -- never a faked edge (map-never-launder).** Braces are stored separately in `data/codex/kin_edges.json` (reversible; each carries its reason), DISTINCT from concord `bonds`; coordinate_map.py renders kin faint.
- Baseline: 534 concord bonds, ~1408 floppy (zero-bond) cards -> rigidity **0.21**.
- **Batch 1 (coord.family kin):** +367 braces, 228 floppy family-cards connected (same coord.family = same FORM = a true relation) -> rigidity **0.292**.
- NEXT batches (honest signals only): shared scripture-ref / scripture_anchors co-citers (the cross-ref web); domain-cluster anchoring (sparingly); axis/topic kin. Goal: every joint supplies (Eph 4:16), no floppy orphans, NOT over-braced (elegant, just-rigid), every brace a real relation.

## EASE-OF-USE (tick: core navigation)
FINDING: `site/index.html` (the family homepage, ".com app for Christian families") links NONE of the technical core (proofs/maps/MCP) -- but that is AUDIENCE SEPARATION, not blocking: the homepage is the family face; the proofs/maps/MCP are the technical/agent face (the Atlas/wedge layer). Do NOT force 3-manifold-map links onto the family homepage (audience mismatch). Agents reach the core via `llms.txt` -> `/mcp` (good). FIXED the real gap: `coordinate-map.html` was a DEAD-END (no links out) -- added a companion nav (surface-map, proof-bridges, atlas, /mcp) in the generator `tools/coordinate_map.py` so it persists. The core maps now cross-link: surface-map (the hub, links all) <-> coordinate-map <-> proof-bridges (-> /mcp) <-> atlas. A curious human or agent who lands in the core can now navigate it. NEXT (if pursued): a small, audience-appropriate "for the technically curious / for your AI" footer link from the homepage to the wedge/MCP -- SURFACE to Matt before editing the homepage (most prominent public surface; live deploy operator-gated).
