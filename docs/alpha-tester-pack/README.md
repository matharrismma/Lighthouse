# Concordance Interface Pack

This folder is the interface layer for the Concordance verification engine. It exists because the engine works but the *interface* — schemas, vocabulary, examples, status semantics — was underdocumented.

## Files

- **glossary.md** — every term a new tester needs (RED, FLOOR, BROTHERS, GOD, WAY, scope, status taxonomy).
- **schemas.md** — for each of the 9 verifiers + full-packet engine: required/optional fields, expected status values, and one minimal call.
- **training_set.json** — 14 worked input/output examples captured from real engine runs on 2026-04-27. Use as documentation, regression tests, and tester onboarding.
- **known_issues.md** — three reproducible bugs found while building the training set. Includes minimal repros and proposed fixes.
- **decision_packet_template.json** — fill-in-the-blanks template for the full-packet engine.
- **decision_packet_example.json** — a completed example (weekly family budget review).
- **quickstart.md** — first 5 minutes for a new tester.

## How a new tester should use this

1. Read `quickstart.md` (5 min).
2. Skim `glossary.md` (5 min) — without this the framework vocabulary is opaque.
3. Pick a verifier from `schemas.md` and run the minimal example shown.
4. When something fails unexpectedly, check `known_issues.md` before assuming user error.
5. For a real decision, copy `decision_packet_template.json`, fill it in, and run through `validate_packet`.

## Status taxonomy at a glance

| Status | Meaning | Where it appears |
|---|---|---|
| CONFIRMED | Independent recomputation matches the claim | Single-domain verifiers |
| MISMATCH | Recomputation disagrees with the claim | Single-domain verifiers |
| PASS | Gate satisfied | Full packet engine (RED, FLOOR, BROTHERS, GOD) |
| REJECT | Gate failed; packet should not proceed | Full packet engine |
| QUARANTINE | Gate is incomplete or ambiguous; packet held pending fix | Full packet engine |

## Versioning

`training_set.json` carries a `version` field. Bump it when you change the engine and re-run examples. A diff between versions tells you which verifiers changed behavior.
