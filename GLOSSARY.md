# Glossary

Terms used throughout the project, in the project's own voice. Cross-linked
from `README.md`, `FOR_AI_AGENTS.md`, and `COOKBOOK.md`.

---

## The four gates

**RED gate.** The refusal gate. Two layers: an *attestation* check (did the
author affirm the load-bearing constraints? — e.g. "no coercion," "mass
conserved") and a *verifier* check (does the artifact computationally hold
up? — e.g. does the equation balance, does the p-value recompute). Failure
returns REJECT and halts the chain. Verifier REJECT can override a passing
attestation; the math doesn't lie.

**FLOOR gate.** The completeness gate. Verifies the packet is structurally
sufficient to be a decision: required fields populated, scope declared,
executable path named, internal consistency. A REJECT here means the packet
is a wish, not a decision yet.

**BROTHERS gate.** The witness gate. Confirms the witness count meets the
scope-required threshold. A QUARANTINE here means "come back when more eyes
have seen this." Not a refusal — a hold.

**GOD gate.** The wait gate. Confirms enough wall-clock time has passed
since `created_epoch` for review to actually have happened. Adapter scope:
1 hour. Mesh scope: 24 hours. Canon scope: 7 days. A QUARANTINE here means
"come back when the time has passed." Modifying the packet hash to dodge
the wait defeats the purpose.

---

## Verdicts

**PASS.** All four gates cleared. Packet is appended to the ledger as a
recorded decision. The structural constraints were met; the wisdom of
the decision is not what PASS speaks to.

**REJECT.** A hard gate (RED or FLOOR) failed. The packet is *also*
appended to the ledger — the engine's record of what was tried, not just
what succeeded — but with `overall: REJECT` and the failed gate's reasons
attached.

**QUARANTINE.** A soft gate (BROTHERS or GOD) said "wait." The packet is
not at fault; the situation around it isn't ready. Add witnesses, allow
time, resubmit.

**CONFESSION.** A new entry that points back to a prior entry (by
sequence number and packet hash) to record an agent's recognition that
the prior decision was wrong. The original is not modified — the ledger
never mutates — but the chain now contains both the decision and the
acknowledgement.

---

## Scope

The reach of a decision and the corresponding witness/wait threshold.

- **adapter** — individual or single-team. 1 hour wait window.
- **local** — small team. (Used in some packet shapes; treated as adapter
  by GOD.)
- **mesh** — cross-team. 24 hour wait.
- **canon** — organization-wide policy. 7 day wait.
- **kernel** — core policy. Treated as canon.

Scope is *declared by the submitter* and is part of the packet's identity.
Shrinking the scope to dodge a higher threshold is a documented anti-pattern.

---

## Layer 0 (the WORD source)

The scripture layer the engine treats as root authority. Three components:

- **Original languages** — Hebrew Westminster Leningrad Codex (morphhb),
  Greek MorphGNT (morphologically tagged Greek NT)
- **Bridge** — Strong's lexicon (H1–H8674 Hebrew, G1–G5624 Greek), mapping
  English words to original-language semantic ranges
- **English** — World English Bible (WEB), public domain, treated as the
  *locked* English translation

The data lives in `lw/00_source/` and is built by running
`python lw/00_source/fetch_sources.py`. It is gitignored because it is
large; the engine degrades gracefully (returns SKIPPED, not ERROR) when
Layer 0 is not provisioned.

---

## Triangulation

The principle that a claim about scripture must survive at all three
layers of Layer 0 (WEB text, Strong's original-language meaning, and the
claim itself). If a claim requires a key word to mean something outside
its attested semantic range, it is flagged as drift. See
`/triangulate` and the `triangulate_claim` MCP tool.

---

## Anchor

A scripture reference attached to a packet via `scripture_anchors` (in a
DECISION_PACKET) or `refs` (kernel-style). The scripture verifier
automatically resolves every anchor against the WEB; fabricated anchors
return MISMATCH naming the failed refs. Most common LLM failure mode in
the scripture domain is inventing references that sound plausible but
don't exist; anchor verification catches this.

---

## Ledger

The append-only SHA-256 hash-chained record of every decision the engine
has weighed. Stored as JSONL at `LEDGER_PATH` (default `ledger.jsonl`).
Never deletes. Never mutates. Genesis hash is 64 zeroes; every subsequent
entry's hash is computed from `prev_hash | packet_hash | overall |
timestamp_epoch`. Tampering with any value invalidates every later entry.

Endpoints: `/ledger` (newest N), `/ledger/{packet_id}` (every entry for a
packet), `/ledger/verify` (chain integrity), `/dispatch` (filtered
search), `/stats` (aggregate counts).

---

## Packet hash vs. entry hash

**Packet hash.** SHA-256 of the canonical JSON of the packet itself.
Identifies the *content* of a submission. Two submissions with identical
content produce the same packet hash regardless of when or by whom.

**Entry hash.** SHA-256 of `prev_hash | packet_hash | overall | timestamp`.
Identifies a *position in the ledger*. Same packet submitted twice will
have the same packet hash but different entry hashes (different prev_hash
and timestamp).

Both are returned in `/submit` and `/validate` responses. The entry hash
is the agent's warrant — it proves a specific verdict was committed at a
specific time, locked by the chain.

---

## Attestation vs. verification

**Attestation** is the author's declaration. The packet's `*_RED` and
`*_FLOOR` blocks are checklists of statements the author affirms ("no
coercion," "mass conserved," "sample size justified"). The engine reads
these and rejects if a required flag is False.

**Verification** is the engine's recomputation. The `*_VERIFY` blocks
contain the actual artifact (chemical equation, code, p-value inputs)
which the engine balances, runs, recomputes. Verification can REJECT a
packet that passed attestation — the author can be wrong about whether
the equation balances even after declaring it does.

The two layers are intentionally independent. Attestation captures the
author's *commitment*; verification captures *truth* about the artifact.

---

## Cross-cutting verifier

A verifier that runs on every packet regardless of the packet's domain,
because its inputs can appear in any domain. Currently the only one is
**scripture**: any packet carrying `scripture_anchors` or kernel-style
`refs` triggers anchor verification, no matter whether the domain is
chemistry, governance, or anything else. See
`src/concordance_engine/verifiers/__init__.py:CROSS_CUTTING_VERIFIERS`.

---

## Reflect / submit / validate

Three POST endpoints with the same packet shape but different commitments:

- **`/reflect`** — preview mode. Runs every gate, returns the verdict.
  Does NOT write to the ledger. Use to rehearse a packet until the
  verdict is what you intend.
- **`/submit`** — public unauthenticated. Runs every gate, writes to the
  ledger. Bypasses the GOD wait window so casual visitors get a
  meaningful PASS/REJECT instead of an unwaitable QUARANTINE.
- **`/validate`** — authenticated (X-Api-Key header). Strict GOD-gate
  timing. Use for production calls where the wait is the point.

---

## Confession

Recognition that a prior recorded decision was wrong. POSTed to
`/confess` with a `ref_seq` (the prior entry's sequence number),
`confessor` name, `reason`, and optional `amendment` and
`scripture_anchors`. The engine appends a new ledger entry with
`overall: CONFESSION` that references the prior one. The prior entry
remains unchanged.

---

## Kernel

The minimal four-gate decision model that the engine implements
operationally. Lives in design form at `lw/03_kernel/the_way_kernel_min.py`
and as a documented architecture at `docs/KERNEL.md`. The engine in
`src/` is the realization of that design; the kernel files are reference
material for understanding the *why* of the gate ordering.

---

## Calibre

A separate, ledgerless formation/alignment engine at
`lw/09_calibre/calibre_ai_package/`. Tracks an agent's progression
(milk → meat tier) through reflection signals — not a verifier. Out of
scope for the public engine but in scope for the broader project.

---

## Drift

When a claim about scripture requires a key word to mean something
outside its attested semantic range. The triangulation layer
(`drift_check.py`) is the detector. Currently surfaces as
NEEDS_MANUAL_VERIFICATION until the morphologically-tagged texts are
hooked up; supplying explicit `strongs_keys` to `/triangulate` returns
the per-word semantic range a reviewer can compare against the claim.
