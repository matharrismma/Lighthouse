# Site audit — the human interface (2026-06-19)

Re-run the ground truth any time: `python tools/site_audit.py` (full) or
`--orphans`. This doc is the judgment layer on top of that data.

## The finding

**167 HTML pages in `site/`.** Only 6 are true orphans (4%) — so the problem is
NOT unreachable pages. It is three things:

1. **Fake connectivity.** Pages are reachable only through link-dump hubs:
   `surface-map` (151 outbound), `workspace`/"Desks" (38), `welcome` (32),
   `dashboard`/`operator`/`gaps`/`works` (~19 each). There is no curated path —
   a visitor hits a wall of dozens of links with no hierarchy.
2. **Operator/back-office pages mixed into the public site** (~20): dashboard,
   operator, inbox, outreach, publish, engine-queue, tickets, tasks,
   marketplace, wallet-help, wallet-transparency, handoff, residue, reach,
   setup, nfc, share, pyodide, innovation, roadmap. These are tooling, not a
   user experience.
3. **Duplication within every family** — one canonical hub + a tail of
   near-duplicates. Plus personal/portfolio essays and a 492 KB page.

## The principle (Matt: "statistics and geometry — they all connect")

The interface should be a **navigable map of connections**, not a flat menu.
Each family already has ONE canonical hub (the high-inbound page). Make those
~7 hubs the navigation; everything else either merges into its hub, moves behind
auth, or is retired. The few hubs ARE the map, and they link to each other.

## Canonical hub per family (by inbound links = de-facto center)

| family | KEEP (canonical) | MERGE into it | RETIRE / MOVE |
|---|---|---|---|
| the map | `atlas` (in=30) + `breath` (living viz) + `grid` (technical) | `atlas-map`, `map`, `coordinate-map` (492KB), `surface-map`→sitemap | `roadmap`→operator |
| engine/verify | `verifiers` (in=8) + `gauntlet` (the hook) + `benchmark` | `proof`, `proof-bridges`, `ten-second-proof`, `verify-seal`, `seal`, `codex-seal` → one Proof page | — |
| scripture/codex | `canon` (in=31) + `codex` | `codex-deep`→codex; `codex-xref/connections/themes` as sub-tabs | `concordance` (orphan) |
| learn/tutor | `curriculum` (in=28) + `read` (tutor) | `learn`, `learn-deep`, `reading`, `reading-room` | — |
| apothecary/heal | `apothecary` (in=37) | `health` | — |
| community/serve | `missions` + `assembly` | `common-book`, `household`, `connect` | `church-streams` (check live) |
| write/keep | `kept` + `scribe` | `daily`, `cards`, `curate`, `well` | — |
| media/channels | `channels` (one hub) | `listen`, `schedule`, `today`, `watch` | per-show pages → behind channels |
| dev/agents | `mcp` | `agents`, `connect`, `setup` | `pyodide`, `nfc` |
| operator (NOT public) | — | — | **MOVE behind auth / off public**: dashboard, operator, inbox, outreach, publish, engine-queue, tickets, tasks, marketplace, wallet-*, handoff |
| personal/portfolio | (own section or off) | — | works, dade, molasses, stack, seeds, odysseus, theory, residue |

## Target

~167 → **~25–30 public pages**, organized as ~7 canonical hubs (the map) +
their sub-pages. Operator tooling behind auth. Personal essays in their own
clearly-separate section or retired.

## Order of operations (destructive steps need Matt's OK)

1. **DONE — re-anchor the front door** (lead with verify + the connected map;
   work-area kept as the mechanic, not the headline). `site/index.html` +
   `api/i18n_strings.py`.
2. **Move operator pages off the public surface** (auth-gate or `/op/`). Biggest
   single cleanup; low risk (they're tooling).
3. **Merge duplicate families** into their canonical hub (301 redirects from the
   merged page so no link rots).
4. **Retire** personal essays + the 492 KB page (or slim them).
5. Re-run `tools/site_audit.py` to confirm the map is clean.

Nothing in 2–4 is deleted without review — `git` keeps everything, and merges
leave a redirect so no inbound link breaks.
