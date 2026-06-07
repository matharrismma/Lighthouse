# Scope — the verified cross-domain connection graph (the disruptive lever)

> Sequence: floor → Codex → **connections**. The floor is solid; the Codex is
> bound, indexed, and sealed. This is the next frontier — and the one Matt named
> as the longest lever to *disrupt*: "solve problems that usually cost a lot, or
> do something others can't."

## The thesis (why this is the lever, not a rabbit)

Verified, traceable cross-domain connections are:
- **Cheap for us** — we already own a 60-domain verifier bank, a witnessed
  substrate, a deterministic axis scaffold, and the card graph. Others need a
  polymath.
- **Trustworthy where LLMs hallucinate** — every connection is *verified and
  traced*, never generated. **The moat is trust.**
- **Compounding** — each new verified claim adds candidate edges; each new
  verifier promotes more candidates from resonance → verified.

Passes the lever test (HORIZONS): it *earns a return* (a trust moat no one can
cheaply copy) and *saves time* (the engine surfaces connections without Matt).

## What already exists (the candidate layer — honest, deterministic)

| Asset | What it is | Count | Provenance |
|---|---|---|---|
| `grid_connections.jsonl` (the Connector) | 2-domain edges: two claims sharing ≥1 axis | 13,953 | deterministic axis-overlap |
| `synthesis_patterns.jsonl` (the Synthesist) | 3+ domain clusters | — | pure fns, no oracle |
| `grid.AXIS_DIMENSIONS` | domain → axis scaffold (7 axes) | 60 domains | deterministic |
| `axis_index.json` | verified-claim `dims` for precedent | — | from CONCORDANT almanac entries |
| Codex scripture index | within-body cross-refs | 2,921 | **100% witnessed** |
| Card connection graph | typed links (cites/proof_text/see_also) | ~16k | witnessed connection cards |

The 7 axes: `time_sequence, reasoning, authority_trust, physical_substance,
encoding, conservation_balance, metabolism`.

## The gap: resonance ≠ verified connection

A grid edge says *"biology's ATP claim and thermodynamics' Gibbs claim both touch
conservation_balance."* That is a **resonance** — suggestive co-occurrence of
abstract axes. It is NOT a checkable assertion that the two are the *same
principle*. Presenting resonances as connections would be exactly the
generate-don't-eliminate failure this project exists to refuse.

**So the build is a verification + smoothing layer over the candidates**, not a
new finder. We have plenty of candidates. We have ~zero *verified* ones surfaced.

## The verification model — four tiers, trail = trust

A connection is only promoted when something **checkable** backs it. Each carries
its **trail** (the engine's creed: "read the elimination trail; the trail is the
reasoning").

1. **Structural-verified** (the real moat). Both claims reduce to the same
   machine-checkable structure — e.g. both satisfy a conservation law. Mechanism:
   dispatch `sample_a` and `sample_b` through the deterministic dispatcher
   (`agent/dispatch.py`) → if both return CONFIRMED from their domain verifiers
   *and* the shared axis is a real structural correspondence, the connection is
   true *because the math on both sides is confirmed*. Trail = both verifier
   results.
2. **Witness-verified**. Both sides anchor to the same Scripture verse (from the
   scripture index) or the same witnessed almanac claim. The connection inherits
   the existing witness (Deut 19:15).
3. **Trace-verified**. A path through the witnessed card graph (A cites X, X
   parallels Y, Y → B) where every hop is already a typed, witnessed connection.
4. **Candidate (unverified)**. Axis-overlap only. Kept, but **labeled
   "resonance, not verified"** and never presented as truth.

## The honest constraints (non-negotiable)

- **The oracle may PROPOSE candidates; it may never ASSERT a connection.**
  Assertion comes only from a deterministic verifier, a witness, or a traced
  path. Asking the LLM "are these connected?" is the hallucination trap.
- **Quality over quantity.** A few hundred genuinely-verified connections beat
  14k resonances. Most cross-domain analogies *cannot* be deterministically
  verified — that's fine. Promote what can be checked; label the rest.
- **No silent caps.** If the structural tier can only verify N of M candidates,
  say so on the surface.

## Phased build

**Phase 1 — The connection ledger + smoothing (deterministic, no oracle).**
Unify grid edges + synthesis clusters + scripture cross-refs + card links into one
scored, deduped, ranked store. "Smoothing" = pruning 14k noisy edges to the
meaningful ones (axis_count, domain distance, witness backing). Output:
`data/codex/index/connections.json`; API `/codex/connections[/{domain}]`.
*This alone is shippable and honest — the candidate layer made navigable.*

**Phase 2 — The verification tiers (the moat). Pilot small, prove, then scale.**
Start with **witness-verified** (cheap — reuse the scripture index) and **one
structural pilot** (pick 1-2 axis pairs, e.g. conservation_balance across
biology/thermodynamics/chemistry; dispatch both samples; confirm both).
Measure the promotion rate. Expand only what proves out.

**Phase 3 — The faces.** Per-connection trail view; a connection explorer
(pick a domain/concept → verified connections + their trails); the connections
fold into the signed artifact (Face 2) so the graph is sealed too.

## Risks / watch-items

- Structural verification of free-text samples is genuinely hard (the grid
  samples are prose, not structured specs). The dispatcher may extract few. **Pilot
  before scaling** — this is the lever, treat it with care, not as a sprint.
- Don't let Phase 1 (easy, navigable candidates) masquerade as the lever. The
  lever is Phase 2 (verified). Ship Phase 1 honestly labeled; the disruption is
  the verified tier.
- Scale to the proof. A small set of *verified* connections with airtight trails
  is the asset — not a big graph of resonances.

## Recommended first increment

**Phase 1 + the witness-verified tier.** It's fully deterministic, reuses the
scripture index, and produces the first connections that are *verified, not
generated* — proving the model end to end before the harder structural pilot.

## Built (2026-06-06)

**Phase 1 + witness tier — shipped** (`48c7dc3`). 139 witnessed co-citation hubs
(332 sources) + 1,269 smoothed candidate domain-pairs. API `/codex/connections`,
page `/codex-connections.html`.

**Phase 2 — verified-structural — shipped.** Pilot, measured-first per this scope:
- **Path A (dispatch the grid samples): DEAD — 0% of 400 samples matched** the
  structured dispatch rules. The grid's 441 unique samples are free-text prose;
  the dispatcher needs structured claim forms. Abandoned, as the scope warned.
- **Path B (the almanac): WORKS.** Almanac entries are already four-gate verified
  and carry `pre_run.domain_results`. An entry confirmed by **2+ domain verifiers**
  is a verified cross-domain connection with a per-verifier trail. **81
  connections / 40 domain-pairs** (penicillin → biology+chemistry+medicine; a
  5-verifier synthesis; citrus-canker → agriculture+biology+chemistry).

Modest by design — quality over quantity, exactly as scoped. The tier grows as
the almanac grows (each new multi-verifier entry is a new verified connection).

**Still ahead:** a deeper structural tier (same-equation / same-conservation-law
correspondence, not just co-confirmation); promoting candidates by re-verifying
*structured* claims (not the prose samples); folding connections into walks.
