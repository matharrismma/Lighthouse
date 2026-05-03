# Training Data

Two JSONL files. Both are hand-written. No machine-generated content
should be added to either without explicit attribution.

## `conversational_train.jsonl` (20 items)

Reasoning protocol training items: `RED → FLOOR → WAY → EXECUTION`. The
model's job is to evaluate a real-world scenario, walk the gates in
order, and produce a verdict with `OUTPUT:` and `NEXT STEP:`.

**Distribution:**
- Domains: governance ×5, business ×4, household ×4, education ×4, church ×3
- Halt gates: RED ×7, FLOOR ×5, WAY ×4, NONE (full pass) ×4
- Difficulty: easy ×6, medium ×11, hard ×3

The format matches `eval/eval_chat.jsonl` exactly so the same loader
covers both. The system prompt is the canonical one in
`training/SYSTEM_PROMPT.md`, byte-for-byte.

## `packet_train.jsonl` (8 items)

Validation protocol training items: `RED → FLOOR → BROTHERS → GOD`. The
model's job is to predict what the Concordance Engine will return given
a structured packet — an internal model of the engine that an agent can
consult before submitting.

Each item includes:
- A packet (the user message, JSON)
- Expected `overall` (PASS / REJECT / QUARANTINE)
- Expected `first_failed_gate` (RED / FLOOR / BROTHERS / GOD / null)
- A one-sentence reason

**Distribution:**
- Domains: chemistry ×2, physics ×1, governance ×3, CS ×1, statistics ×1
- Outcomes: PASS ×2, REJECT(RED) ×3, REJECT(FLOOR) ×1, QUARANTINE(BROTHERS) ×1, QUARANTINE(GOD) ×1

Use this set when training a model that will be calling the engine in a
loop — it teaches the verdict shape so the model anticipates rejections
rather than being surprised by them.

## Adding items

Read [`../FORMAT.md`](../FORMAT.md) for the schema. Two principles for
additions:

1. **Keep the seed clean.** Never copy items from `eval/eval_chat.jsonl` —
   that's your held-out test set, and contaminating it invalidates your
   numbers.
2. **Cover the gates.** Check the distribution above before adding. If
   you add three new RED-halting items in a row, you're skewing the seed.

## Provenance

All items in this directory were hand-written by the project maintainers
to teach the protocol from first principles. They are NOT extracted from
the live ledger; the live ledger is reserved for actual decisions.
