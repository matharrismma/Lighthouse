# Authority

This repository implements a four-gates validation protocol. The protocol order is fixed: **RED → FLOOR → BROTHERS → GOD**. The engine evaluates them in that order and halts at the first failure. It never self-confirms.

This file documents the governance assumptions for the software layer.

## What this software claims authority over

- **Mechanical adjudication of a packet** against the rules encoded in `src/concordance_engine/domains/` (attestation) and `src/concordance_engine/verifiers/` (computation). The engine returns `PASS`, `REJECT`, or `QUARANTINE` and a structured reason. That output is authoritative for the rules as encoded.
- **Computational verification** of artifacts (chemical equation balance, dimensional consistency, p-value recompute, runtime complexity, code termination, etc.). Where the engine confirms, the underlying math holds up to the assumptions stated by the verifier.

## What this software does not claim authority over

- **The choice of rules.** The set of forbidden categories at RED, the structural requirements at FLOOR, the witness threshold at BROTHERS, and the wait window at GOD are inputs to the engine, not outputs. A community, board, or maintainer authors them. The engine enforces them.
- **The truth of an attestation.** The author of a packet declares that constraints are met. The engine reads the declaration. The verifier layer can override an author's claim only when artifacts contradict it computationally — a passing attestation does not bind the engine if the math is wrong.
- **The wisdom of a decision** that passes all four gates. PASS means "the rules as encoded did not catch a problem." It does not mean "this is a good idea." The WAY-style judgement (sequencing, sustainability, charity) lives outside this codebase.

## Trust boundaries

- The engine and its verifiers run locally. There are no network calls in core validation. A user's packets and code never leave the machine.
- The CS verifier executes user-supplied Python in a restricted namespace (no `__import__`, `open`, `exec`, `eval`, `compile`). It is not a sandbox suitable for adversarial code; it is suitable for code the user controls.
- The MCP server inherits the same boundary: every tool maps to a verifier; no tool issues network requests.

## Versioning

Engine versions are SemVer-shaped (`MAJOR.MINOR.PATCH`). A bump signals:
- **PATCH** — bug fix in an existing verifier, no schema change.
- **MINOR** — new verifier mode, new tool, new schema field that is non-breaking.
- **MAJOR** — schema change that breaks existing packets, or a gate-order change.

The packet `version` field is informational; the engine does not refuse stale packets, but the maintainer is free to surface them in the result detail.
