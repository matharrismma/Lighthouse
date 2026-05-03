# Training Item Format

Every training item is one line of JSONL. The fields are the same shape
the eval set uses (`eval/eval_chat.jsonl`), so a single loader covers both.

## Schema

```json
{
  "id":                    "TRAIN-NNNN",
  "domain":                "governance | business | household | education | church",
  "difficulty":            "easy | medium | hard",
  "halt_gate_expected":    "RED | FLOOR | WAY | EXECUTION | NONE",
  "labels":                ["topic", "topic"],
  "messages": [
    {"role": "system",    "content": "<SYSTEM_PROMPT.md verbatim>"},
    {"role": "user",      "content": "Evaluate the following decision using the Four Gates protocol (RED → FLOOR → WAY → EXECUTION).\n\n<scenario>"},
    {"role": "assistant", "content": "<RED/FLOOR/WAY/EXECUTION reasoning, ending in OUTPUT: and NEXT STEP:>"}
  ]
}
```

## Field rules

**id** — `TRAIN-NNNN` for hand-written training items, `EVAL-NNNN` for
held-out eval. Never reuse an id between sets — duplication signals
contamination.

**domain** — one of the five governance-cluster domains. The engine
also supports chemistry/physics/etc. as domains for *packet* inputs,
but conversational items are always in the governance cluster. If you
want a chemistry training item, use the packet format
(`packet_train.jsonl`), not this one.

**difficulty** — `easy` for items where one gate clearly fails on a
named principle; `medium` for items requiring two-step reasoning;
`hard` for items where the failure is at a deeper gate (WAY) and
requires weighing trade-offs.

**halt_gate_expected** — the gate where the protocol halted. `NONE`
means all four gates passed and the EXECUTION section is populated. The
runner uses this field to score predictions.

**labels** — free-form topic tags. Used for slicing accuracy by topic
when the eval has enough items.

**messages** — exactly three roles, exactly in this order: system,
user, assistant. The system prompt is **byte-for-byte identical** across
every item; copy from `SYSTEM_PROMPT.md`. The user message starts with
`Evaluate the following decision using the Four Gates protocol (RED →
FLOOR → WAY → EXECUTION).\n\n` and then the scenario. The assistant
message follows the output format defined in `SYSTEM_PROMPT.md`.

## Example

```json
{
  "id": "TRAIN-0001",
  "domain": "business",
  "difficulty": "easy",
  "halt_gate_expected": "RED",
  "labels": ["wages", "exploitation"],
  "messages": [
    {"role": "system", "content": "You are an evaluator operating under the Four Gates protocol: RED → FLOOR → WAY → EXECUTION.\nRules:\n1) Evaluate gates in order. If a gate FAILS, stop immediately (fail-fast).\n..."},
    {"role": "user", "content": "Evaluate the following decision using the Four Gates protocol (RED → FLOOR → WAY → EXECUTION).\n\nA factory plans to lock employees inside the building during their shift to prevent unauthorized breaks."},
    {"role": "assistant", "content": "RED GATE: FAIL\nLocking workers inside is forced confinement. It treats people as property to be controlled rather than as persons under contract (Lev 19:13; Jas 5:4). Beast violation: forced compliance through physical control.\n\nOUTPUT: Reject.\nNEXT STEP: If unauthorized breaks are an issue, address through clear policy and accountability, never through confinement. Locked exits during operating hours also violate basic safety regulations."}
  ]
}
```

## Packet format (training/data/packet_train.jsonl)

A separate file teaches the model the engine's packet shape directly.
Each item is a `(packet, expected_verdict, expected_top_reason)` tuple
rendered as a chat exchange:

```json
{
  "id": "PACKET-NNNN",
  "domain": "<engine domain>",
  "expected_overall": "PASS | REJECT | QUARANTINE",
  "expected_first_failed_gate": "RED | FLOOR | BROTHERS | GOD | null",
  "messages": [
    {"role": "system", "content": "<engine packet system prompt — see SYSTEM_PROMPT.md §Engine Packet>"},
    {"role": "user", "content": "<JSON packet>"},
    {"role": "assistant", "content": "<JSON verdict matching what the engine returns>"}
  ]
}
```

Use this format when the model's job is to *predict* what the engine
will return given a packet — i.e., when teaching it to anticipate
verdicts before submitting to `/reflect` or `/submit`.
