# Agent surface audit — the 134-tool MCP surface (2026-06-17)

A cold-agent navigability audit of the MCP tool surface (`src/concordance_engine/
mcp_server/server.py`). The doors all *work*; this is about whether an agent that just
called `tools/list` can find and use the right tool. Verified live during the fresh-look.

## The shape (134 tools / 6 prompts / 4 resources)

- **64 `verify_*`** domain verifiers (incl. 5 umbrellas: physics, statistics, biology,
  energy, computer_science — each wraps sub-checks that are *also* exposed directly).
- **1 funnel:** `check` (subsumes the verifiers; plain-language / structured / multi-step).
- **~70 non-verify tools:** Scripture/concordance (≈12), Layer-0 lookups (≈19),
  cards/substrate (≈11), almanac/search (≈5), packets/gates (≈8), curriculum/herbs/flows/
  robot/atlas/etc.

## Done (safe, shipped 2026-06-17)

- **Instructions rewrite** — the block told agents "start with check" but not *how*. Now
  states the three `check` paths + points multi-claim situations to `run_polymathic`.
  Doctrine preserved verbatim.
- **Duplicate marked** — `polymathic_run` is a thin wrapper of `run_polymathic`; its
  docstring now says so (prefer `run_polymathic`). Not removed (no break).
- **`find_verifier(keyword)` added** — the missing claim→verifier index (audit RANK 2),
  read live from the registry (never stale). Named `find_verifier` (not `verify_*`) so it
  doesn't pollute the verifier count or list itself. Instructions point to it. (135 tools now.)
- **Search disambiguation** — `search()`'s docstring now maps which-search-for-which-
  substrate (see below); resolves the "which one?" confusion without a risky merge.

## Decisions made during the work (corrections to the audit)

- **Gate renames (`attest_*`→`gate_*`): declined.** The docstrings already define RED
  (coercion/authority/hard-failure) and FLOOR (completeness/consistency). A rename adds a
  duplicate tool for niche tools during the deprecation window — net clutter, low value.
- **`verify_phase` is NOT a stub** — it's a terse-but-functional phase classifier
  (setup/positioning/conversion). Left as-is.
- **Search tools are NOT pure duplicates** — `search`/`fetch` are a *required ChatGPT-
  connector contract*; `almanac`/`packets_search`/`cards_walk` hit different substrates.
  Fixed by disambiguation, not consolidation.

## Proposed for review (not built — your call on the design)

- **`find_in_substrate(query, kind=…)`** — a unified fan-out that searches corpus +
  almanac + packets in one call and tags results by source. Genuine convenience, but the
  substrates differ enough that the merge shape is a design question. Worth doing
  deliberately, not rushed at session's end.

## Remaining menu

### Safe / additive (no break — can do anytime)
1. **`verify_lookup(domain)` discovery tool** — agent passes "chemistry" → gets the
   verify_* tools for it + an example. The missing claim→tool index. *High value.*
2. **Docstring pass on the ~10 weakest** — `verify_phase` (what is a "phase"?),
   `verify_witness` (cryptic fields), `triangulate_claim` (Strong's jargon, needs an
   example), `attest_red`/`attest_floor` (explain RED/FLOOR upfront), `flow_run` (show the
   state dict + mention `flow_list` first), `verify_computer_science` (define
   claimed_class/input_generator), `scribe_submit` ("the keeping"?), `get_example_packet`.
3. **Umbrella note** — say in each umbrella's docstring that sub-checks are also callable
   directly and omitted keys are NA.

### Breaking (changes the public tool surface — operator's call)
4. **Renames for clarity** — `attest_red`→`gate_red`, `attest_floor`→`gate_floor`;
   consider `triangulate_claim`, `apothecary_compound`, `shepherd_interview` (jargon).
   Breaking unless done as add-alias-then-deprecate.
5. **Remove `polymathic_run`** entirely (now a soft alias). Breaking for anyone using it.
6. **Consolidate substrate search** — `search` / `fetch` / `almanac` / `almanac_search` /
   `packets_search` / `cards_walk` are ~6 overlapping discovery tools. One
   `find_in_substrate(query, kind=…)` with the others as aliases would cut confusion.
   Bigger refactor; do behind a long deprecation window.

## Note on the funnel
`check` structurally subsumes the verifiers, but in practice an agent with a chemistry
claim prefers the explicit `verify_chemistry`. The funnel guidance + a `verify_lookup`
index together make both paths findable — that's the cheapest large navigability win.
