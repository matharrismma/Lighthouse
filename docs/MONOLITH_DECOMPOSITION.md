# Decomposing api/app.py -- a safe, incremental plan

`api/app.py` is **~19,400 lines / 386 routes / 560 defs** -- the single largest
maintainability liability in the repo. Every change risks the whole surface, and a broken
import means the live service 502s. This is the plan to tame it **without** a risky
big-bang refactor. It is written to be executed one cohesive group at a time, each behind
the same verification gate every deploy uses, with human eyes on each step.

## Why not just do it autonomously

`app.py` carries a large amount of module-level state and helpers that routes reference
directly (paths, stores, middleware, the MCP mount, shared `_helpers`). Naively cutting
routes out breaks those references -- and the file is deployed to prod, so a bad extraction
is a live outage. Decomposition must be **incremental and verified per step**, which is
human-supervised work, not an autonomous loop edit.

## The pattern: FastAPI APIRouter, one group at a time

1. Create `api/routers/<group>.py` with `router = APIRouter()`.
2. Move one cohesive group of route functions there, changing `@app.get(...)` -> `@router.get(...)`.
3. Move/​share the helpers and state they need: prefer importing from `api/app.py` or a new
   `api/shared.py` (do NOT duplicate state -- a second copy of a store or a counter is a bug).
4. In `app.py`: `from api.routers import <group>; app.include_router(<group>.router)` --
   register **before** the `StaticFiles("/")` mount so explicit routes still win.
5. Verify (the gate -- all must pass before the next group):
   - `python -m ast` parse on both files;
   - import the app in a fresh process (catches the shadowing/broken-import class);
   - restart, `systemctl is-active`, `benchmark_public_verify.py` = 58/58, 0 false-pos;
   - live-smoke every moved route (GET/POST a known request, confirm the same response).
6. Commit that one group. Repeat.

## Suggested order (lowest-risk first)

The first extractions should be **read-only, self-contained GET groups** with little shared
state -- they prove the pattern with minimal blast radius:

1. **Scripture / Word** -- `/scripture/*` (lookup, parallel, concord, cross-references),
   `/easton/*`. Read-only, already delegate to `tools` / `scripture_lookup`. Best first cut.
2. **Curriculum** -- `/phonics`, `/math`, `/workready`, `/bible_curriculum`, `/curriculum`.
   All read `_read_jsonl_safe(<path>)`; trivially groupable.
3. **Apothecary / herbs** -- `/apothecary`, herb lookups. Mostly self-contained.

Then the heavier, state-coupled groups (more care, smaller steps):

4. **Substrate writes** -- `/seal*`, `/cas`, `/chain/*`, `/receipts/*`, `/packets/*`. These
   are deployment-mode-gated and touch the CAS/ledger; extract with the middleware in mind.
5. **Gated generation / discern** -- `/api/generate-gated`, `/d/*`. Carries the rate-limit
   + budget state (`_GATED_HITS`); move that state with the router, keep it a single instance.
6. **Keep / community / coach** -- `/keep/*`, `/community/*`, `/coach/*`, `/shepherd/*`.

Target: app.py becomes a thin assembler (config, middleware, `include_router` calls, the
MCP mount, the static mount) with the routes living in `api/routers/`.

## Two related cleanups (also human-supervised)

- **The ~290 uncommitted working-tree files** are mostly *generated* artifacts that churn at
  runtime: `data/codex/index/*.json`, `data/trust_index/*.json`, `data/packets/*.jsonl`,
  `site/map-stats.json`, `data/github_traffic.jsonl`, eval results. The right fix is to
  decide per-path: `git rm --cached` + `.gitignore` the truly-generated ones (so they stop
  showing as dirty and real changes are visible again), while keeping the by-design-tracked
  data (e.g. `data/almanac/entries.jsonl`). This is a deliberate tracking-model decision --
  do it with review, not a blanket ignore, so nothing real gets hidden.
- **Duplicate `nhanes_extensions.py`** (identical copies in `research/nested_control_systems/`
  and `lw/06_validation/framework_validation_v3_final/`). Likely a sibling-import for the
  validation pipeline in the `lw/` dir; confirm no local import needs it before removing the
  copy, or make one a thin re-export of the other.

## Done so far (this hygiene pass)

- Removed root scratch artifacts (`physics_fixed.py` [tracked, unreferenced], `_tmp_*`,
  `_cr_*.json`, `*_slice.txt`, `conn_index.txt`) and added ignore patterns so they do not
  return. The decomposition itself remains for supervised, incremental work per the above.
