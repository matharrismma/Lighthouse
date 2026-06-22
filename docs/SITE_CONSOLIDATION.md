# Narrow Highway — Site Consolidation Plan

> Produced 2026-06-20 by a 15-agent audit of all 168 top-level pages (workflow
> `site-consolidation-audit`). The steering doc for collapsing the site to a
> mobile-first 1–3 UI shape. Verdict: **.com = Walk + Library**, **.org = The
> Map**, **.tv = Watch & Listen** — two interfaces on the front door, three
> across the triad. Hubs redirect (301), nothing load-bearing 404s.

The audit confirms the operator's verdict. 168 surfaces, ~70+ tools, a dozen
front-doors, six Codex faces, eight media players, seven operator consoles
leaking onto the public site. The plan to collapse it follows.

## 1. Site map (by real function)
- **Front-doors / onboarding (11)** — index, enter, welcome, door-org, door-tv, see, about, how-it-works, ten-second-proof, benchmark, parable
- **Verify engine — the product (18)** — try, run, poly, proof, gauntlet, four-gates, enter, seal, verify-seal, codex-seal, chronicle, receipts, scribe, discern-teaching, robots, residue, gaps, innovation
- **Walk / Shepherd / discernment (8)** — walk, walks, shepherd-room, paths, discern-teaching, daily, today, journal
- **Codex / Scripture (13)** — codex, canon, bibles, concordance, codex-deep, codex-connections, codex-themes, codex-xref, codex-seal, proof-bridges, tradition, testimony, scripture
- **Knowledge / reference (14)** — almanac, packets, atlas, atlas-map, encyclopedia, places, card, archetypes, shelves, library, search, coordinate-map, registry, brain/breath/grid/map
- **Learn / practice (16)** — read, learn, learn-deep, curriculum, unit, training, maker, reading, fieldkit, stack, common-book, kept, calendar, bible-trivia, games, submit-curriculum
- **Family / community / mission (13)** — family, hearth, missions, prayer, refuge, marketplace, recipes, submit-recipe, witness, assembly, letters, you, take-part
- **Media / witness — .tv (24)** — watch, channels, radio, listen, kids, podcast, podcast-theatre, pilots, live, church-streams, hymns, reading-room, media-center, schedule, apokalypsis, molasses, dade, characters, works, workshop, parable, games, watch-listen(stub)
- **Giving (6)** — giving, support, sponsors, wallet-help, wallet-transparency, deposit(stub)
- **Creation / capture (8)** — funnel, share, nfc, health, household, profile, tasks, tools
- **Operator-internal (18)** — keep, operator, dashboard, engine-queue, inbox, tickets, curate, steward, outreach, publish, cards-dev, setup, agents, handoff, roadmap, gap-analysis, surface-map, guidance
- **Agent / integration docs (6)** — connect, mcp, install, odysseus, agents, reach
- **Meta / legal / system (7)** — privacy, theory, organic-design, offline, 404, robots.txt, verifiers
- **Redirect / dead stubs (5)** — desk, gates, deposit, watch-listen, surface-map

## 2. Overlap chart (clusters, most-redundant first)
1. **Front-Door (11→1)** — index, enter, welcome, door-org, see, about, how-it-works, ten-second-proof, benchmark, parable, four-gates
2. **Verify-a-claim (8→1)** — try, run, poly, proof, gauntlet, four-gates, enter, pyodide
3. **Codex (10→1)** — codex, canon, bibles, concordance, codex-deep, codex-connections, codex-themes, codex-xref, codex-seal, proof-bridges
4. **Walk/Shepherd (6→1)** — walk, walks, shepherd-room, paths, discern-teaching, stack
5. **Receipt/Seal (5→1)** — receipts, seal, verify-seal, codex-seal, scribe
6. **Knowledge-index (5→1)** — packets, atlas, atlas-map, almanac, encyclopedia
7. **Graph-viz (5→.org)** — brain, breath, grid, map, coordinate-map, workshop
8. **Daily-anchor (4→1 tab)** — today, daily, journal, calendar
9. **Saved-things (5→1 drawer)** — kept, common-book, stack, you, household/profile
10. **Media (8+→.tv)** — watch, channels, radio, listen, kids, podcast, media-center, schedule
11. **Operator (7→.org/operator)** — operator, keep, dashboard, engine-queue, inbox, curate, steward, outreach, tickets
12. **Learn (5→1)** — read, learn, learn-deep, curriculum, unit
13. **Submission (6→1)** — scribe, take-part, share, funnel, submit-content, submit-recipe, submit-curriculum
14. **Giving (4→.org)** — giving, support, sponsors, wallet-transparency, wallet-help

## 3. The consolidation (1 primary, 3 max)

### TARGET 1 — The Walk (`.com`, THE primary UI)
Bring anything — claim, question, situation, teaching, worry — and the engine
verifies it (trail + seal), shepherds it (Scripture + precedent + gates), or
keeps it. One box, one loop, points to Christ.
**Mobile:** single full-width sticky-bottom input + mic; result card slides up
(HOLDS/BROKEN/Shepherd answer, collapsible trail, tap-to-copy seal chip); saved
cards in a slide-in drawer; one column.
**Folds in:** core = walk, try, run, poly, enter; tabs = gauntlet, four-gates,
discern-teaching, shepherd-room, walks/paths, daily/today, apothecary; drawer =
kept, stack, common-book, you, household, profile; artifacts = seal, verify-seal,
receipts, scribe, chronicle; front-doors = index/welcome/parable/ten-second-proof/
benchmark/how-it-works/see. Cut: journal, pyodide(toggle), deposit, gates, desk, share.

### TARGET 2 — The Library (`.com`, secondary)
Look up what you can name — Scripture, place, archetype, verified entry, Codex.
**Mobile:** one search bar + lens chips (Bibles · Codex · Places · Encyclopedia ·
Archetypes · Field Kit); chip → single-column list → detail (card). No graphs on mobile.
**Folds in:** library(shell), codex, bibles, places, encyclopedia, archetypes,
fieldkit, almanac, packets, search, card. Codex faces (canon, concordance,
codex-deep/connections/themes/xref/seal, proof-bridges) → tabs inside codex.
atlas/atlas-map → packets; shelves → codex; misalignments → almanac.
Learn (read/curriculum/training) and Family (family/hearth/missions/prayer) are
**decks reachable from the Walk home**, not a fourth UI.

### TARGET 3 — the two triad faces
- **.tv (Watch & Listen)** — media-center shell; watch/channels/radio/listen/kids as tabs.
- **.org (The Map)** — apologetic + engine internals + operator + giving + agent docs.

Net: a .com visitor sees **two things** — *Walk* (do/ask) and *Library* (look up).

## 4. Triad distribution
- **.org (True / map / engine / apologetic):** coordinate-map, registry, theory,
  organic-design, tradition, proof-bridges, works; graph viz brain/breath/grid/map;
  honesty surfaces gaps/innovation/residue/verifiers/gap-analysis; operator bench
  operator/keep/dashboard/curate/setup/guidance/tickets; agent docs agents/connect/
  mcp/install/odysseus/reach/nfc; giving giving/support/sponsors/wallet-*; refuge/
  marketplace/witnesses; health (WHOOP).
- **.tv (Beautiful / witness):** media-center ← watch/channels/radio/listen/kids/
  podcast*/pilots/live/church-streams/hymns/reading-room/schedule; narrative
  apokalypsis/molasses/dade/characters/workshop; games/bible-trivia; door-tv;
  submit-content/pitch.
- **.com (Good / daily mercy):** Walk + Library; apothecary(sick), read/curriculum
  (free education), family/hearth/missions/prayer, recipes→apothecary/hearth, tools.

## 5. Stale pages & bad links
**Retire:** handoff (CUT), surface-map (CUT), gates (CUT→/walk), desk/deposit/
watch-listen (CUT after link fix); publish/roadmap/engine-queue/inbox/cards-dev/
outreach/steward/dashboard/gap-analysis → .org operator bench, noindex.
**FIX (don't cut):** privacy (DRAFT w/ TODOs — legal requirement for the ChatGPT Action).
**Hub fix-or-redirect (no 404):** scribe(38)→submissions view; atlas(33)→301 /packets;
canon/codex(32+17)→codex-*  301 /codex#tab; almanac(43) absorbs misalignments(21);
curriculum(29) (read stays); bibles(24)→301 /codex#bibles; packets/archetypes/
fieldkit/places stay as Library tabs; parable→/index section; chronicle→/receipts;
walk(57)/daily(33)/training(24) keep. **Rule: each merge ships with a 301.**

## 6. Mobile (root causes + fix)
1. Dashboards w/ no breakpoint (keep/outreach/steward/inbox/dashboard/engine-queue) → move to .org operator bench.
2. Canvas graphs hijack touch (map/brain/breath/workshop/coordinate-map; map broken) → move to .org.
3. Fixed multi-column form rows (letters/household/profile/sponsors) → single-column drawer; pricing → .org.
4. Cramped tap targets (calendar 7-col, codex/card grids) → 44px min; calendar → agenda list.
5. Horizontal overflow (seal/proof-bridges/shelves monospace) → break-all + scroll-contained code.
6. **The win:** `nh-shell.css` (sticky-bottom input, single-column default, 44px, break-all) already
   works on misalignments/places/atlas/packets/scribe — **mandate it for the two .com targets.**

## 7. Sequenced execution
1. **Freeze the shell** — `nh-shell.css` as the only .com shell (the mobile fix).
2. **Build The Walk** on walk.html + try.html — sticky input, mode tabs, your-things drawer.
3. **Build The Library** on library.html — lens chips → live tabs.
4. **Collapse the Codex** — six codex-* + canon + concordance + proof-bridges → codex tabs; 301s.
5. **Collapse front-doors** — index = Walk home; others → sections / 301 /.
6. **Wire redirects BEFORE deleting** — atlas→/packets, misalignments→/almanac, walks/paths/
   shepherd-room/discern-teaching→/walk, chronicle/verify-seal/codex-seal→/receipts,
   learn/learn-deep/unit→/curriculum, kept/common-book/stack/you/profile→Walk drawer,
   recipes/submit-recipe→/apothecary & /take-part.
7. **Move .org content** (apologetic, graph viz, engine-honesty, agent docs, giving, refuge) + redirects.
8. **Consolidate .tv** — media-center shell; fold players + narrative + tv submissions.
9. **Hide operator bench** — → .org/operator, noindex, off public nav.
10. **Fix privacy.html** TODOs (legal; required for the ChatGPT Action).
11. **Retire the dead** after links repointed; verify each old URL 301s, none 404.
12. **Verify on the droplet** — every inbound-hub URL resolves (200/301); both .com targets render at 375px.

**After:** `.com` = Walk + Library · `.org` = The Map · `.tv` = Watch & Listen.
One thing to use, one place to look, one map to show, one witness to behold.
Conduit, not idol — every surface hands a receipt and points up.
