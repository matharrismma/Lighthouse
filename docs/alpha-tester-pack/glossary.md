# Concordance Glossary

Definitions of every term used in the engine. If a tester doesn't know these, the framework is opaque to them.

## Gates (the four checks the full engine runs)

**RED** — Forbidden categories. A packet lists actions/outcomes that are off-limits ("debt_increase", "hidden_spending", "unsupervised_minor_contact"). The RED gate scans the packet for any matches and rejects on hit. Treat RED as: *what must never happen, regardless of upside.*

**FLOOR** — Protective constraints that must be present, not absent. ("both_spouses_present", "written_record", "two_eyewitnesses"). Where RED is "thou shalt not," FLOOR is "thou must." A packet that lacks a required FLOOR item fails this gate.

**BROTHERS** — Witness count. The packet must list at least N witnesses (people who saw and consented to the decision). The default minimum depends on scope (see below). The check is a count, not a name match.

**GOD** — Time-wait gate. The packet must have aged at least `wait_window_seconds` since `created_epoch` before it can be enacted. The point is to prevent same-moment decisions on weighty matters. A packet with `wait_window_seconds=0` waives this.

## Scope (how big a decision is)

**adapter** — Local, reversible, low-stakes. ("Buy this brand of detergent," "switch chore day.") Lowest witness/wait requirements.

**mesh** — Affects multiple parties or systems. ("Change family budget categories," "adopt a new homeschool curriculum.") Higher witness count.

**canon** — Foundational, hard to reverse. ("Sell the house," "change church membership," "covenant change.") Highest witness count and longest wait.

The scope a packet declares determines the BROTHERS minimum and the default GOD wait.

## WAY

**way_path** — A short prose description of *how the decision will actually be carried out*. Not the decision itself ("we will do X") but the execution route ("Sunday evening, both present, in writing, with quarterly review"). The way_path is the bridge between the decision and the `execution_steps` list.

## Status taxonomy

Single-domain verifiers (math, physics, chemistry, etc.) return:

- **CONFIRMED** — Independent recomputation agrees with the claim.
- **MISMATCH** — Recomputation disagrees. Includes the recomputed value and the claimed value for comparison.

The full-packet engine (`validate_packet`) returns one of:

- **PASS** — All four gates passed.
- **REJECT** — At least one gate hard-failed (e.g., RED hit).
- **QUARANTINE** — At least one gate is incomplete or ambiguous (e.g., missing `created_epoch`, no witnesses listed). The packet isn't wrong, it's *unfinished*.

## Witness, scripture_anchor, execution_step

**witnesses** — A list of people (names or roles) who participated in or saw the decision and consent to it. Used by BROTHERS.

**scripture_anchors** — Optional list of scripture references that ground the decision. Not gated, but their presence/absence is recorded in the packet shape check.

**execution_steps** — Ordered list of concrete actions that carry out the way_path. The shape check counts these; a packet with zero steps will not pass.

## Two terms that look similar but aren't

**red_items vs. forbidden actions in execution_steps** — `red_items` is a category list ("debt_increase"). The RED gate uses it to scan the rest of the packet. An execution step that *contains* the word "debt" is a hit.

**floor_items vs. execution_steps** — `floor_items` are *constraints* ("both_spouses_present"). `execution_steps` are *actions*. Floor items can repeat across many decisions; steps are decision-specific.
