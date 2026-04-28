# Concordance Quickstart

The first 5 minutes for a new tester.

## What is Concordance?

A verification engine. You hand it a claim — a math equation, a balanced reaction, a decision packet — and it independently recomputes the result using deterministic tools (Sympy, scipy, SI-unit reduction). It either CONFIRMS, returns a MISMATCH, or for full packets, runs four gates (RED, FLOOR, BROTHERS, GOD) and returns PASS / REJECT / QUARANTINE.

It doesn't *make* the decision. It checks the work.

## When to use it

- Before publishing a result, run the relevant single-domain verifier.
- Before enacting a meaningful family/business/church decision, run it through `validate_packet`.
- During testing, run the entire `training_set.json` and confirm every example still produces the documented `actual_status`.

## Try it in 60 seconds

Pick the smallest verifier and run it:

```json
{"mode": "derivative", "params": {"function": "sin(x**2)", "variable": "x", "claimed_derivative": "2*x*cos(x**2)"}}
```

Expected: `CONFIRMED`.

Now break it on purpose:

```json
{"mode": "derivative", "params": {"function": "x**3", "variable": "x", "claimed_derivative": "2*x**2"}}
```

Expected: `MISMATCH` with detail "d/dx of x**3 = 3*x**2, but claimed 2*x**2".

If both produce the right answers, math verification is wired up correctly.

## Try a decision packet in 3 minutes

Open `decision_packet_example.json`. Read it once. Notice:

- `text` carries the narrative (RED/FLOOR scan this).
- `red_items` and `floor_items` carry the structured categories.
- `witnesses` carries the BROTHERS list.
- `created_epoch` and `wait_window_seconds` feed the GOD gate.

Pass that whole object as `packet` to `validate_packet`. (Note: as of 2026-04-27, this currently QUARANTINES on a known schema mismatch — see `known_issues.md` issue #3.)

## When something looks wrong

Before assuming user error, check `known_issues.md`. Three known engine bugs as of 2026-04-27 can flag correct claims as wrong:

- Stats two-tailed p-values
- Computer science test_cases with multi-arg functions
- Full-packet validation of governance packets that pass the standalone verifier

If your failure matches none of those, capture the input and the actual output and add it to `training_set.json` so the next tester sees it.

A fourth issue (added after a verification run): `validate_packet` enforces a scope-based wait window (~3600s for adapter) that overrides the packet's `wait_window_seconds`. For test runs, pass `now_epoch >= created_epoch + 3600`.

## Glossary check

If you don't know what RED, FLOOR, BROTHERS, GOD, WAY, adapter, mesh, or canon mean — read `glossary.md` next. Without those, the framework is opaque.
