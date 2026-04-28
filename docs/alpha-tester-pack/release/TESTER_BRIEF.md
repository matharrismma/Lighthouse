# Concordance v1.0.4 — Alpha Tester Brief

Thank you for agreeing to look at this. This page is everything you need.

## What Concordance is

A deterministic verification engine. You hand it a claim — a math equation, a chemical reaction, a statistical p-value, or a structured decision packet — and it independently recomputes the result. It returns one of CONFIRMED / MISMATCH for single claims, or PASS / REJECT / QUARANTINE for full decision packets after running four gates: RED (forbidden categories), FLOOR (protective constraints), BROTHERS (witness count), GOD (time-wait).

It doesn't *make* the decision. It checks the work and refuses to certify a decision that hasn't been thought through.

## Status

Alpha. Four engine bugs were fixed today (2026-04-27); the interface layer was written this week. Expect rough edges. The framework vocabulary (RED/FLOOR/BROTHERS/GOD/WAY/scope) is load-bearing — if you don't know what those mean after reading the glossary, that's our bug, not yours, and we want to know.

## What I'm asking from you

About two hours, spread across two weeks.

1. **Read** `quickstart.md` (5 min) and `glossary.md` (5 min).
2. **Run** the 19 examples in `training_set.json` against the live engine (or read them as documentation if you don't have the MCP server running). Confirm each produces the documented `actual_status`.
3. **Try** running one decision you're actually weighing through `validate_packet`. Use `decision_packet_template.json` as the starting point. Doesn't have to be high-stakes — a household call works.
4. **Return** the feedback form. Honest answers, not encouraging ones.

## What's in the package

- `quickstart.md` — first 5 minutes
- `glossary.md` — every term defined
- `schemas.md` — every verifier with required/optional fields
- `training_set.json` — 19 worked examples
- `known_issues.md` — what's currently rough or broken
- `decision_packet_template.json` + `decision_packet_example.json` — the canonical packet shape
- `FEEDBACK_TEMPLATE.md` — the form I'm asking you to return

## What I want to learn from you

The framework or the interface? The bugs we already know about, or the ones we haven't seen? Whether the engine actually helps you make better decisions, or whether it's just paperwork? I want all four answers.

## How to reach me with questions

[Matt fills in: email / phone / Signal — whatever feedback channel you commit to]

Two-week window starts the day you receive this. One-week check-in around the midpoint. After two weeks: I read everyone's feedback, fix or document, and either expand the cohort or revise.

Thank you for your time. This tool is more useful with your eyes on it than without.

— Matt
