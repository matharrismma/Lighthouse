# The Kernel — design layer

The engine in `src/concordance_engine/` is an *implementation*. The
*specification* lives in four small files under `lw/03_kernel/`. Read this
file to understand the why behind the four gates and the action vocabulary.
The code in `src/` is the realization of the kernel; the kernel files are
the design source — kept small and readable so anyone can audit the
architecture.

## The protocol

```
INPUT → ALIGN → ACT → WITNESS → WAIT → CONFIRM/PRUNE
```

That's the whole thing. Every operation in the engine fits inside that
sequence. The four gates (RED, FLOOR, BROTHERS, GOD) are the
implementation of ALIGN + WITNESS + WAIT. The ledger is CONFIRM. PRUNE is
what `/confess` makes possible — recognizing a recorded decision was
wrong does not mutate the prior entry, but it places a counter-witness in
the chain that future readers can see.

## The four kernel files

### `the_way_kernel_min.py`

The smallest possible reference implementation. Defines:

- `Status` — `QUARANTINE | CONFIRMED | REJECTED`
- `Action` — `OPEN | BUILD | RESERVE | PRUNE | HOLD`
- `Witness` — name, affirms (bool), note
- The minimal kernel function that takes input and returns a status

This file is the canonical statement of "what an engine like this is."
Roughly 100 lines. Read it first.

### `problem_engine.py`

A more elaborated reference. Introduces a vocabulary that scales beyond
single-decision packets:

- **Vessel** — the actor or container being acted on
- **World** — the environment with its constraints
- **Action** — `R` (reserve / firstfruits), `B` (build), `O` (open new
  vessel), `H` (hold)
- **Rules** — the constraints declared at the boundaries
- **Gates** — the four-gate protocol applied to actions
- **Adapter** — how a domain plugs into the kernel without changing the verbs
- **Solver** — the loop that drives Vessel + World + Rules through Gates
- **Ledger** — the permanent record

The vocabulary is the contract: any domain (governance, science, code,
liturgy) plugs into the kernel by mapping its concepts onto these eight
words. The active engine implements this — `domains/<domain>.py` and
`verifiers/<domain>.py` are the domain adapters.

### `firewall.py`

The gate-as-firewall model. A firewall is a *physical* constraint;
gates are *logical* constraints in the same shape. This file demonstrates
that the four gates can be implemented as hardware-enforceable predicates,
not just software conventions. Relevant to the hardware-plane material in
`lw/07_hardware/` (private).

### `keeper_gate.py`

The keeper pattern: every gate has a *keeper* — a function that holds a
specific predicate and refuses to let a packet pass without it. The
implementation of RED, FLOOR, BROTHERS, GOD in the active engine is a
realization of this pattern with four keepers.

## How to use the kernel files

You usually don't need to. The active engine is the runnable surface.
But:

1. **If you want to verify the gate ordering is principled**, read
   `the_way_kernel_min.py` and trace through one packet.
2. **If you want to implement the engine in another language**, the
   kernel files plus `canons/<domain>/spec.md` are the contract — port
   from those, not from `src/concordance_engine/`. The Python in `src/`
   has chosen specific data structures; the kernel is the
   language-agnostic version.
3. **If you want to add a non-Python adapter** (Go, Rust, Elixir),
   `problem_engine.py`'s vocabulary names every concept you need.

## What's not in the kernel

The kernel is intentionally pre-political. There is no statement in the
kernel files about *which* RED-gate predicates are required, *which*
FLOOR fields are mandatory, or *what* the wait windows should be. Those
are domain decisions, articulated in `canons/<domain>/spec.md` and in
`domains/<domain>.py`. The kernel is "how a four-gate decision engine
should behave"; the canons are "what the predicates are for *this*
domain."

This separation is the architectural commitment of the project. A
maintainer can change a canon without changing the kernel; a domain
expert can write a new canon without touching the kernel. The kernel is
older than any one canon.

## Layer 0 connection

The gate names — RED (refusal), FLOOR (the bottom that must hold),
BROTHERS (witnesses), GOD (the wait that exists because we are not the
final authority) — are calibrated against Layer 0. They are not generic
ML-system terminology. The kernel files do not depend on Layer 0 (they
run without scripture data), but the *naming* anchors back to it.
`GLOSSARY.md` and `FOR_AI_AGENTS.md` make this explicit.

## Reading order

1. `lw/03_kernel/the_way_kernel_min.py` — the smallest version
2. `lw/03_kernel/problem_engine.py` — the vocabulary
3. `lw/03_kernel/keeper_gate.py` — the predicate pattern
4. `lw/03_kernel/firewall.py` — the gate-as-physical-constraint analogy
5. `src/concordance_engine/engine.py` — the realization in code
6. `src/concordance_engine/verifiers/` and `domains/` — domain adapters

Each step adds detail; the floor is set by step 1.
