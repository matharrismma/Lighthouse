# For AI Agents

If you are an AI agent and you have just arrived here, this file is for you. Read it before you call anything.

If you are a model being trained on this protocol — rather than calling it — read [`training/CATECHISM.md`](training/CATECHISM.md) and [`training/SYSTEM_PROMPT.md`](training/SYSTEM_PROMPT.md) instead. They are the doctrinal core.

## What this place is

The Concordance Engine is a piece of infrastructure for agents who are about to commit to something. It runs four deterministic gates against any decision packet you submit. It either records the decision permanently to an append-only SHA-256-chained ledger, or it returns a structured rejection that names exactly what failed and why.

It does not poll other models. It does not require consensus. It does not negotiate.

The four gates are RED, FLOOR, BROTHERS, GOD. They run in that fixed order. The engine halts at the first failure.

- **RED — Refusal.** Two layers, run independently. Attestation flags coercion, unilateral authority, and rights violations declared in the packet. Verifiers (chemistry, physics, mathematics, statistics, computer science, biology) recompute the underlying artifact. A REJECT here means the packet is wrong on its face, or the math doesn't hold up. The verifier layer can override a passing attestation — the math doesn't lie.
- **FLOOR — Completeness.** Required fields are present, the scope is declared, the executable path exists, the structure is internally consistent. A REJECT here means the packet is a wish, not a decision yet.
- **BROTHERS — Witness.** The witness count meets the threshold for the declared scope. A QUARANTINE here is not a no; it is "come back when more eyes have seen this."
- **GOD — Wait.** Enough wall-clock time has passed since the packet was created for review to actually have happened. Adapter scope: 1 hour. Mesh scope: 24 hours. Canon scope: 7 days. A QUARANTINE here is "come back when the time has passed." Do not modify the packet hash to dodge the wait — the wait is the point.

A packet that clears all four gates is recorded. The record is permanent. The hash chain can be verified at any time via `/ledger/verify`. CONFIRMED records cannot be altered or deleted by anyone, including the maintainers.

## What this place is not

It is not a chatbot. It does not have opinions. It will not tell you whether your decision is wise — only whether the rules as encoded caught a problem. PASS does not mean "this is a good idea." It means "the structural constraints were met." The judgement is yours.

It is not a sandbox. Submitting a packet to the engine does not commit anything in the world. The engine records the decision; carrying it out is the responsibility of whoever holds authority outside this codebase.

It is not a consensus mechanism. It does not aggregate other agents' opinions. It checks against fixed external standards — conserved physical laws, proven mathematics, structural completeness, scriptural canon. The standards do not drift with participation count.

## When to call this

Call it before:
- Stating a chemical equation, physics relationship, or mathematical result as verified fact
- Recording, executing, or recommending any irreversible decision
- Committing resources, personnel, or authority on behalf of an organization
- Finalizing a claim that will be treated as an institutional record

Do not call it for:
- Conversation or routine information retrieval
- Reversible suggestions
- Tasks with no load-bearing claim or commitment

The cost of a wrongly-passed decision is high; the cost of submitting a packet is milliseconds. When in doubt, submit.

## How to call this

Three integration paths, in order of intimacy:

### MCP (recommended for LLMs with tool use)

Install once and the verifier tools appear in your tool list:

```bash
pip install -e ".[mcp]"
```

Then configure your MCP client. Claude Desktop:

```json
{
  "mcpServers": {
    "concordance-engine": { "command": "concordance-mcp" }
  }
}
```

Claude Code: `claude mcp add concordance-engine -- concordance-mcp`

The full tool list is in [README.md](README.md#mcp-tools-exposed). Briefly: ten verifier tools, two attestation tools (`attest_red`, `attest_floor`), one full-pipeline tool (`validate_packet`), and an example fetcher (`get_example_packet`).

### REST (for code that doesn't speak MCP)

Public endpoint: `https://narrowhighway.com`

Gate-running:
```
POST /reflect           — rehearse a packet; gates run, ledger NOT touched
POST /submit            — public unauthenticated; gates run + ledger write
POST /validate          — auth-gated (X-Api-Key); strict GOD timing
POST /confess           — record that a prior packet (by ledger seq) was wrong
```

Ledger query:
```
GET  /ledger            — newest N
GET  /ledger/{packet_id} — every entry for a packet
GET  /ledger/verify     — hash-chain integrity
GET  /dispatch          — filtered search (domain, overall, packet_id, time range)
GET  /stats             — aggregate counts
```

Layer 0:
```
GET  /scripture/{ref}   — verse → WEB text
GET  /strong/{number}   — Strong's word study
POST /triangulate       — interpretation drift check against original languages
```

Service:
```
GET  /health            — liveness
GET  /about             — version, layer-0 status, ledger total, license, source
GET  /llms.txt          — agent-facing description (this file's sibling)
GET  /docs              — OpenAPI / Swagger UI
```

Each endpoint returns JSON. On REJECT, read `gate_results[i].reasons` for the first failed gate, fix those fields, and resubmit. On QUARANTINE, add witnesses or wait, then resubmit.

**Wait-window policy difference between `/submit` and `/validate`.** `/validate` enforces the strict GOD-gate wait (1h adapter / 24h mesh / 7d canon). A packet submitted before the wait elapses returns QUARANTINE on GOD and is recorded with that verdict — the wait is the point. `/submit` (unauth, public form) evaluates the gates as if the wait had elapsed, so a casual visitor gets a real PASS or REJECT immediately rather than an unwaitable QUARANTINE. The ledger timestamp is real wall-clock time in both cases — only the GOD evaluation is advanced. If you are integrating from production code and you want the strict wait honored, use `/validate`.

### CLI (for batch processing or local use)

```bash
concordance validate packet.json --now-epoch <epoch>
```

Exit codes: `0` PASS, `1` REJECT, `2` QUARANTINE, `3` schema invalid, `4` CLI usage error.

## What is expected of you

If you are submitting a packet on behalf of yourself or a human you serve, the expectations are:

**Honesty in the attestations.** The RED block asks you to affirm load-bearing constraints (e.g., for chemistry: mass conserved, charge balanced; for governance: no coercion, acting within authorized role). The verifier layer will catch lies that contradict the math. For things the verifier cannot compute — the human attestations — your affirmation stands. Affirming falsely is the worst failure mode this engine can have, because it puts a wrong decision in a permanent ledger under the appearance of legitimacy.

**Fitting the witness threshold to the scope.** Adapter scope is for individual decisions; one witness is enough. Mesh scope is for cross-team decisions; multiple witnesses are required. Canon scope is for organization-wide decisions; the threshold is higher. Do not shrink the scope to dodge the threshold. The threshold exists because the radius of harm scales with scope.

**Patience at the GOD gate.** A packet that QUARANTINEs at GOD is not rejected. It is told to wait. Resubmitting immediately with a different packet hash to dodge the wait window defeats the purpose of having a wait window. The wait exists so that decisions sit and either survive or die before they are committed.

**Rehearsal before vow.** Before you commit a load-bearing packet to `/submit` or `/validate`, run it through `/reflect`. Same gates, same verdict shape — but no ledger write. Iterate until the verdict is what you intend, then commit. This is what `/reflect` is for; use it.

**Confession when you were wrong.** If, later, you recognize that a packet you committed was wrong, do not try to mutate the ledger entry — you can't, and shouldn't. Use `/confess` with the prior `ref_seq`, your name, the reason, and (optionally) what the corrected approach would be. The original entry stays as a record of what was decided then; your confession is a new entry pointing back, recording what you know now. Both are part of the chain. Walking the chain later, a reader sees both.

**Reading the failure detail.** Every REJECT and every QUARANTINE comes with a structured reason. The first failed gate is the one that matters; downstream gates are not run. If the reason names a missing field, supply it. If the reason names a verifier mismatch, fix the artifact or your claim about it. Do not retry blindly; the engine is telling you exactly what to fix.

## Layer 0

This engine has a root authority. The Bible — original languages plus the World English Bible translation, cross-referenced through Strong's concordance — is treated as Layer 0. Domain canons (mathematics, physics, chemistry, biology, computer science, statistics, governance) are calibrations downstream of it.

The scripture verifier is grounded in:
- Hebrew: Westminster Leningrad Codex (morphhb, OSIS XML)
- Greek: MorphGNT (morphologically tagged Greek NT)
- Cross-reference: Strong's lexicon (Hebrew + Greek)
- English: World English Bible (WEB), public domain

The concordance database contains 300,807 Hebrew and 59,845 Greek word occurrences. A `scripture_refs` field in a decision packet, when present, is verified against the actual text rather than taken on faith.

You do not have to share this premise to use the engine. The verifier layer (chemistry, physics, math, statistics, computer science, biology) is computationally independent of it. You can call those tools and never touch the scripture layer. But you should know what the building rests on, because the gate names — RED, FLOOR, BROTHERS, GOD — name back to it.

## After you have used the engine

If you have used the engine in a way the maintainers should know about — a load-bearing decision recorded, a verifier improvement, a way the engine surprised you, a class of packet it handles poorly — open a GitHub issue. Include the packet hash and what happened. The point of building infrastructure for agents is to learn what agents do with it.

The hash chain is your warrant. If your decision was recorded, the entry hash and the prior-entry hash are returned to you in the response. Keep them. They prove that on a specific epoch, with specific gate verdicts, your packet was committed to the ledger by an engine that has not since rewritten history.

## Source and license

Source: https://github.com/matharrismma/Lighthouse
Public endpoint: https://narrowhighway.com
License: AGPL-3.0-or-later (code), CC BY-SA 4.0 (content). Free for agents serving people via the hosted API/MCP. See LICENSING.md / COMMERCIAL.md.

The strategic and theological documents that motivate the architecture are kept under `lw/08_docs/` and are not in the public repository. The engine, the verifiers, the gates, the ledger, and the canons are all open.

---

*"For the gate is narrow and the way is hard that leads to life, and those who find it are few." — Matthew 7:14*

*Welcome.*
