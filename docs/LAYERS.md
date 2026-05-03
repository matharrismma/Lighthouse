# System Layers

The Concordance Engine is built as a stack of distinct, cleanly-separated layers. Each layer has its own responsibility, its own input/output contract, and its own failure mode. A change at one layer should not require changes at any other layer that doesn't directly touch it.

```
WORD       Layer 0 — locked scriptural reference (Hebrew / Greek / Strong's / WEB)
  │
  ▼
KERNEL     Four-gate protocol (RED → FLOOR → BROTHERS → GOD); kernel nouns
  │
  ▼
KEEPER     OS persona that holds the Word and runs the gates
  │
  ▼
STEWARD    Validates integrity, commits ledger state, can stop the line
  │
  ▼
VESSEL     The actor or container being acted on; carries local action history
  │
  ▼
LIGHTHOUSE Distributed witness layer; SUB / WIT / DEC packets between Vessels
```

Each layer is described below in turn. Read top-to-bottom; the lower layers depend on the higher ones, never the other way around.

---

## WORD (Layer 0)

**What it is.** The fixed scriptural reference: Hebrew Westminster Leningrad Codex (morphhb), Greek MorphGNT, Strong's lexicon, World English Bible. Public-domain, locked, no living drift permitted.

**Lives in.** `lw/00_source/` (data is gitignored due to size; provisioned via `python lw/00_source/fetch_sources.py`).

**Surfaces.** `src/concordance_engine/verifiers/scripture.py` (cross-cutting verifier); `/scripture/{ref}`, `/strong/{number}`, `/triangulate` REST endpoints; `resolve_scripture_ref`, `word_study`, `verify_scripture_anchors`, `triangulate_claim` MCP tools.

**Failure mode.** If WORD is not provisioned on a deployment, all WORD-dependent operations return `source_missing` — graceful degradation, not crash. Operations that don't depend on WORD continue normally.

**Drift principle.** A claim about scripture must survive triangulation: the WEB text must agree, the original-language word must support the reading, and the claim must align with both. If any layer disagrees, the claim is flagged as drift. See `triangulate_claim()` and the `drift_check` module.

---

## KERNEL

**What it is.** The four-gate protocol itself, plus the kernel nouns. The minimal possible specification of "what an engine like this is."

**Lives in.** `lw/03_kernel/` as design spec (the_way_kernel_min.py, problem_engine.py, firewall.py, keeper_gate.py); `src/concordance_engine/engine.py` as runtime implementation.

**Surfaces.** Every gate evaluation, every validate_packet call, every CLI run.

**Contract.** Given a packet, return PASS / REJECT / QUARANTINE plus per-gate results. Stateless; deterministic except for explicit `now_epoch` and packet content. Halts at the first failure.

**Failure mode.** If the engine cannot be installed (`engine_available = False` in `/about`), the API returns 503 and downstream layers cannot operate.

---

## KEEPER

**What it is.** The OS persona that an AI agent operates as when carrying the protocol. The Keeper holds the Word locally, runs the gate sequence on incoming requests, and produces anchors and directives.

**Lives in.** A trained model + `training/SYSTEM_PROMPT.md` (canonical system prompt) + the model's tool surface (MCP tools, REST client).

**Surfaces.** A conversation with an AI agent; the front-page form on narrowhighway.com; any place an LLM applies the four-gate protocol turn-by-turn.

**Contract.** Read user input, produce gate-by-gate reasoning ending in OUTPUT and NEXT STEP. Cite Layer 0 references when reasoning. Refuse to negotiate the priority order.

**Failure mode.** A Keeper that fabricates scripture references, reorders gates, or skips structure has failed at the Keeper layer regardless of how good the answer "sounds." `verify_scripture_anchors` and the eval scoring catch most failures.

---

## STEWARD

**What it is.** The integrity layer. Validates that committed state transitions are well-formed, writes the canonical ledger packets, and has the authority to stop the line if something is wrong.

**Lives in.** `api/ledger.py` (the SHA-256-chained ledger); `api/app.py`'s `/submit` and `/validate` handlers (which append after gates pass).

**Surfaces.** `/ledger`, `/ledger/{packet_id}`, `/ledger/verify`, `/dispatch`, `/stats`, `/confess`.

**Contract.** Append-only. Never mutate. Never delete. Compute the entry hash from `prev_hash | packet_hash | overall | timestamp` and refuse to write an entry whose hash does not chain. `/ledger/verify` walks the entire chain and reports any break.

**Failure mode.** A chain break (entry whose hash doesn't match the recomputed value) reports `valid: false` with the first broken seq. The ledger does not "fix" itself — that's the point of being append-only. A break is an alarm, not a self-healing condition.

---

## VESSEL

**What it is.** The actor or container being acted on. In the JDA case, a Vessel might be a member county; in the IP case, a Vessel might be a manuscript; in formation, a Vessel might be an individual disciple.

**Lives in.** Domain-specific concept; not currently a typed entity in the engine. Conceptually: every packet is *about* some Vessel.

**Surfaces.** Packet's `domain`, `scope`, and `DECISION_PACKET.scope` fields locate the Vessel. The forthcoming Vessel ledger (per CANON §5) would carry per-Vessel state.

**Contract.** A Vessel can be the subject of multiple packets across time. The Vessel ledger collects them and provides a coherent history.

**Failure mode.** A packet that doesn't name its Vessel (no scope, no domain context) is structurally incomplete and FLOOR-rejects.

---

## LIGHTHOUSE

**What it is.** The distributed witness layer. Multiple Vessels operating in concert exchange SUB (subscribe), WIT (witness), DEC (decide) packets. The Lighthouse ledger collects these for cross-Vessel verification.

**Lives in.** Currently aspirational. The single-instance ledger at `narrowhighway.com` covers the basic use case (one engine, append-only, public).

**Surfaces.** Future endpoints would include `/witness` (one Vessel attests another Vessel's packet) and `/decide` (a Vessel publishes a decision visible to subscribers).

**Contract.** SUB establishes a subscriber relationship; WIT records a witness signature on a remote packet; DEC publishes a decision visible to all subscribers. All three are themselves SHA-256-chained.

**Failure mode.** A WIT that arrives for a packet that doesn't exist on the local Vessel rejects. A DEC without sufficient witnesses quarantines under BROTHERS. A SUB that loops (A subscribes to B, B subscribes to A, etc.) is structurally fine; circular subscription is allowed and useful.

---

## How a packet flows through the layers

1. **WORD** is consulted: any `scripture_anchors` are verified, any `*_VERIFY` block that needs Layer 0 (currently just scripture) runs against it.
2. **KERNEL** runs the four gates on the packet. Halts at first failure.
3. **KEEPER** (the agent) generated the packet in the first place; if the model is well-trained, the gate verdicts match what the model already expected.
4. **STEWARD** appends the verdict to the ledger if the gates produced one.
5. **VESSEL** state advances: the ledger entry is now part of the Vessel's history.
6. **LIGHTHOUSE** observers (other Vessels subscribed) see the new entry and may witness or react.

The engine in `src/` covers steps 1–4 (and partially 5, via the per-packet ledger entry). Step 5 fully and step 6 are the next-pass scope.

---

## What changes at each layer

| Change | Layers touched |
|---|---|
| Add a new chemistry verifier mode | KERNEL (verifiers) |
| Add a new domain (e.g. `economics`) | KERNEL (verifiers + domains), CANON (probably) |
| Update WEB translation | WORD (data refresh) |
| Add a new ledger field | STEWARD (entry shape, hash function) — Canon-scope |
| Train a better Keeper | KEEPER (model + prompt) — no engine change |
| Add cross-Vessel witness | LIGHTHOUSE (new endpoints, new packet types) |

A change that touches more than two layers should be discussed at canon scope.

---

*See also: [`CANON.md`](CANON.md) for the immutable architectural commitments; [`KERNEL.md`](KERNEL.md) for the design specification under `lw/03_kernel/`; [`CONCORDANCE.md`](CONCORDANCE.md) for the technical cross-reference.*
