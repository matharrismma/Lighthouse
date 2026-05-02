# Known Issues

Tracked here so the README and onboarding remain honest about what works.

## Open

*(none)*

If you find a reproducible problem, file it above with: a minimal repro, observed
output (`status`, `detail`, `data`), expected output, and the rule the engine
should have applied.

---

## Resolved

The four entries below are kept as a record of what the README-audit on
2026-04-28 surfaced. All were closed in v1.0.5 (2026-04-29). See `CHANGELOG.md`
for the per-fix details.

### tests/test_mcp_tools.py — ImportError on `ALL_TOOLS` *(resolved 1.0.5)*

The test imported `ALL_TOOLS` and expected `dict[name -> callable]`. The
`mcp_server/tools.py` module had since switched to a `TOOLS` (list of
descriptors) + `TOOL_BY_NAME` shape, leaving the test pointing at a name that
no longer existed. Fix: re-exported an `ALL_TOOLS` mapping from `tools.py`.

### tests/test_canon_validators.py — path resolution *(resolved 1.0.5)*

The test resolved canons via `parents[3] / "02_canons"`, which only worked from
the old `lw/01_engine/concordance-engine/tests/` layout. Fix: replaced the
hard-coded path with a probe that finds canons at either `canons/` or
`lw/02_canons/`.

### Two parallel `src/` trees *(resolved 1.0.5)*

`src/concordance_engine/` (top-level, Apr 28) and
`lw/01_engine/concordance-engine/src/concordance_engine/` (Apr 27) had
diverged on `engine.py`, `verifiers/computer_science.py`, and
`verifiers/statistics.py`. Fix: declared the top-level tree canonical;
the lw subtree now contains a single README pointing back at the top-level
package.

### `concordance_engine-1.0.4/README.md` byte-identical to top-level *(resolved 1.0.5)*

A frozen v1.0.4 release snapshot was being maintained in parallel with the
live README. Fix: marked the directory as a frozen distribution artifact
(see `.gitignore`) and stopped tracking it.
