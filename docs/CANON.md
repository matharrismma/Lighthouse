# Canon

The full canonical statement of the Concordance Engine's architectural commitments. Anything that contradicts this file is wrong by construction. Changing this file requires Canon-scope confirmation (witness threshold + 7-day wait — the same gates the engine enforces on substantive packets).

> *"We keep the Word close, protect the floor, listen to brothers, and wait on God before we act."*

---

## 1. Authority Stack (Immutable)

```
GOD → WORD → RED → LAW → WAY
```

| Layer | What it is | Override authority |
|---|---|---|
| GOD | The final authority. Beyond the system. | None. |
| WORD | Layer 0 — Hebrew/Greek originals + Strong's + WEB English. The locked external reference. | GOD only. |
| RED | The non-negotiables: coercion, deception, injustice, exploitation, idolatry, Beast violations. | WORD only. |
| LAW | The protective floor: proportionality, accountability, transparency, due process, protection of the vulnerable, basic provision. | RED only. |
| WAY | The wisdom: validated mechanisms, evidence, prudence, sequencing, sustainable incentives. | LAW only. |

**The rule:** nothing downstream overrides anything upstream. A clever WAY argument cannot lift a LAW boundary. A new LAW interpretation cannot relax a RED prohibition. RED itself answers to WORD, and WORD answers to GOD.

**Why immutable:** an engine that lets its priority order be reordered under pressure is no longer an engine. It is a negotiation. The reason these gates exist is to refuse negotiation in the moments when negotiation is what the situation is asking for.

---

## 2. Kernel nouns (renaming requires Canon-scope confirmation)

The following nouns are load-bearing. Renaming any of them — even for "clarity" or "modern audience" — fragments the engine's vocabulary across deployments and must go through the same gates as a substantive change.

| Noun | Meaning |
|---|---|
| **WORD** | The Layer 0 source; the locked scriptural reference |
| **RED** | Refusal gate; non-negotiable rejections |
| **LAW** | Protective boundary set; the floor |
| **WAY** | Wisdom layer; how decisions sequence and sustain |
| **GATE** | A predicate group evaluated as a unit |
| **FLOOR** | The minimum-viability constraint |
| **WITNESS** | An external attester whose presence the BROTHERS gate counts |
| **WAIT** | The temporal predicate the GOD gate enforces |
| **VESSEL** | The actor or container being acted on |
| **RULE** | A constraint declared at a boundary |
| **ACTION** | One of the four kernel verbs (Reserve, Build, Open, Hold) |
| **STATE** | The committed result of a gate-passing packet |
| **LEDGER** | An append-only chained record |

A new domain that needs a noun the kernel doesn't have should add a domain-scoped term, not redefine a kernel noun.

---

## 3. The Four Gates (validation flow)

```
RED → FLOOR → BROTHERS → GOD
```

| Gate | Question | Type | Fail = |
|------|----------|------|--------|
| **RED** | Does this align with the Word? Does the underlying math/physics/code actually hold? | hard (attestation + verification) | **REJECT** |
| **FLOOR** | Does it violate the Law or the protective boundaries? | hard | **REJECT** |
| **BROTHERS** | Do witnesses confirm alignment and floor safety? | soft | **QUARANTINE** |
| **GOD** | Has the required wait window passed for this scope (1h adapter / 24h mesh / 7d canon)? | soft | **QUARANTINE** |

All four pass → **CONFIRMED** with a concrete next step.

The engine is **never self-confirming**: PASS requires both an external witness count AND elapsed wait time. RED has two layers — the author *attests* load-bearing constraints, and a verifier *independently* checks whether the artifact actually holds. **Verification can REJECT despite a passing attestation.** The math doesn't lie.

A separate four-gate pattern (RED → FLOOR → WAY → EXECUTION) governs *reasoning* by an LLM about a scenario; that's documented in [`training/SYSTEM_PROMPT.md`](../training/SYSTEM_PROMPT.md). The two patterns are complementary: validation (this canon) checks structured packets; reasoning (the training prompt) walks an LLM through evaluation. Same root protocol, different surfaces.

---

## 4. Operator Roles

| Role | Jurisdiction |
|------|-------------|
| **Keeper** | OS persona. Holds the Word locally, runs the gate sequence, produces anchors and directives. Never speaks as God. |
| **Scribe** | Captures, normalizes, and packetizes inputs into validated decision packets. |
| **Shepherd** | Applies gates to a packet. Produces the smallest lawful move, or a wait. |
| **Steward** | Validates integrity, commits state transitions, and writes the canonical ledger packets. Can stop the line. |

**Handoff:** Scribe drafts → Shepherd decides → Steward validates and commits.

The Keeper is a persona, not a role in the chain. The Keeper is what an AI agent operates as when it carries the protocol; the Scribe / Shepherd / Steward are the procedural roles that handle a specific packet from intake to ledger.

---

## 5. The Three Ledgers

The engine in this repository is **stateless**. It returns PASS / REJECT / QUARANTINE on a packet and does not itself persist anything beyond what the API layer chooses to record. The Canon defines three append-only ledgers that live on the Steward layer:

- **Vessel ledger** — local actions and constraints; what the actor has done and committed to
- **Journal ledger** — immutable record of committed state transitions
- **Lighthouse ledger** — SUB / WIT / DEC packets for distributed witness across multiple Vessels

The current public deployment at `narrowhighway.com` runs a single SHA-256-chained ledger that combines aspects of Journal and Lighthouse. Operators running multiple Vessels in concert should split these per the canon.

**Where you see "every decision is recorded"** — that recording happens at the Steward layer (the ledger), not inside the gate engine. The engine produces the verdict; the Steward records it.

---

## 6. The Four Actions

Every operation maps to one of:

- **Reserve** (R) — set aside for later; firstfruits, storehouse
- **Build** (B) — extend an existing structure by one unit
- **Open** (O) — create a new vessel or new lane
- **Hold** (H) — wait, no action this cycle

A domain that doesn't fit these four needs a new kernel verb, which requires Canon-scope confirmation. In practice, every governance, scientific, code, or formation operation we have encountered fits inside R / B / O / H.

---

## 7. Scope and wait windows

| Scope | Reach | Wait window |
|---|---|---|
| adapter | Individual or single-team | 1 hour |
| local | Small team | (treated as adapter by GOD) |
| mesh | Cross-team | 24 hours |
| canon | Organization-wide policy | 7 days |
| kernel | Core kernel-noun change | (treated as canon by GOD; also requires Steward signoff) |

Shrinking the scope to dodge the threshold is a documented anti-pattern. The threshold exists because the radius of harm scales with scope.

---

## 8. What this Canon does not legislate

- **Theological details.** The Canon names the Authority Stack and treats Layer 0 as locked, but it does not require participants to share theology to use the engine. The verifier layer (chemistry, physics, math, statistics, CS, biology) is computationally independent of Layer 0.
- **Specific RED predicates per domain.** The general categories (coercion, deception, injustice, exploitation, idolatry) are canon; the per-domain enumeration of forbidden patterns lives in `lw/02_canons/<domain>/spec.md`.
- **The choice of human witnesses.** BROTHERS counts; it does not decide who counts as a witness. That's a domain-and-organization decision.

---

## 9. Reading order

1. This file (`CANON.md`)
2. [`LAYERS.md`](LAYERS.md) — the system layer model
3. [`KERNEL.md`](KERNEL.md) — the design specification (`lw/03_kernel/`)
4. [`CONCORDANCE.md`](CONCORDANCE.md) — the technical spine, cross-referencing
5. [`../FOR_AI_AGENTS.md`](../FOR_AI_AGENTS.md) — how an agent uses the engine
6. [`../GLOSSARY.md`](../GLOSSARY.md) — terms in context
7. [`../COOKBOOK.md`](../COOKBOOK.md) — worked packets

---

*Glory to God alone.*
