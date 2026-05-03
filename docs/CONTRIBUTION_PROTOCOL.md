# Contribution Protocol

`CONTRIBUTING.md` at the repo root covers the standard contributor workflow: setup, tests, lint, branch + PR conventions, adding a verifier domain. This file extends that with the protocol-specific rules — the things a contributor needs to know that are not generic open-source practices.

---

## What "Canon-scope" means in practice

Some changes are not just code changes. They touch the architectural commitments themselves. Per [`CANON.md`](CANON.md) §2, the following changes are **Canon-scope** and must go through the same gates as a substantive packet:

- Renaming a kernel noun (WORD, RED, LAW, WAY, GATE, FLOOR, WITNESS, WAIT, VESSEL, RULE, ACTION, STATE, LEDGER)
- Reordering the gate sequence
- Adding a new gate
- Removing a gate
- Changing the wait windows for a scope
- Changing what BROTHERS counts as a witness
- Changing the hash chain construction (`_entry_hash` function in `api/ledger.py`)
- Changing the license

**What "going through the gates" looks like for a code change:**

1. Open a draft PR describing the proposed change.
2. Submit a Canon-scope decision packet to the engine itself (use `/reflect` first to see the verdict). The packet's `DECISION_PACKET.scope` is `canon`.
3. Hold for the 7-day GOD wait.
4. Collect explicit review and witness from at least two maintainers (BROTHERS).
5. Only after both gates pass, merge the PR.

This is not bureaucracy for its own sake. It is the engine being subject to its own protocol. The day we stop holding ourselves to it is the day the engine becomes ornamental.

---

## Domain-scope changes

The vast majority of work is **not** Canon-scope. Adding a new verifier mode, a new MCP tool, a new test, a documentation fix — these are domain-scope and follow the standard `CONTRIBUTING.md` workflow. PR review by one maintainer is sufficient; CI must pass; tests must accompany the change.

If you're not sure whether your change is Canon-scope, ask. The default is to escalate when in doubt.

---

## The kernel-noun rule

A new domain, verifier, or feature that needs vocabulary the kernel doesn't have should add a **domain-scoped term**, not redefine a kernel noun.

Example: a chemistry verifier that wants to talk about "balancing" should use `balance` or `coefficients` — not redefine RULE or LAW. A statistics verifier that talks about "rejection" should use `rejection_set` or `null_rejected` — not redefine REJECT.

The kernel vocabulary is small for a reason. Polluting it fragments interpretation across deployments.

---

## Layer 0 / scripture content

The canonical Layer 0 source is the World English Bible, Westminster Leningrad Codex (Hebrew), MorphGNT (Greek), and Strong's lexicon. These are public-domain references with locked content.

**Do not:**

- Substitute a different translation as the locked English reference.
- Modify the source data files in `lw/00_source/web/` or `lw/00_source/original/`.
- Rewrite Strong's definitions to "improve clarity."

**You can:**

- Add additional language layers (Vulgate, Septuagint, etc.) as supplementary references that the engine can consult — provided they don't replace the canonical four sources.
- Improve the parsers, indexes, and lookup performance over the canonical sources.
- Extend the drift-check logic with additional triangulation rules.

---

## License compatibility

The engine and all contributions are released under Apache 2.0 (see `LICENSE`). Contributions that are themselves under a non-compatible license (GPL, AGPL, proprietary) cannot be accepted into the core repo. The contribution must either be Apache-2.0-compatible or live in a separate repository with a clean integration boundary.

Note: an earlier draft of the project README named MIT; the LICENSE file and pyproject have been Apache 2.0 since v1.0.6 (2026-04-29). All contributions are Apache 2.0.

---

## Sensitive material

Per [`../.gitignore`](../.gitignore) and the project's privacy memory, the following do not belong in the public repo:

- Strategic and theological documents under `lw/08_docs/` (these are private working documents; the public repo references their existence but does not include them)
- Hardware playbooks under `lw/07_hardware/`
- Frozen distribution snapshots (`concordance_engine-1.0.4/`)
- Local Cloudflare tunnel tokens (now read from `C:\Concordance\tunnel.token` rather than embedded)
- Any contract documents
- Any file matching `*.token`, `.env*`, `*_contract.docx`, `*_contract.pdf`

If you find yourself wanting to commit something that pattern-matches one of these, stop and ask first.

---

## Voice and tone

The project documentation is written in a specific voice: technical, theologically literate, sober. New documentation should match. Specifically:

- Avoid marketing language ("revolutionary," "cutting-edge," "world-class")
- Avoid hyperbole ("unprecedented," "the only," "guaranteed")
- Use scriptural references when they are load-bearing, not for decoration
- Don't preach. The architecture is the witness; the docs explain it.
- "Glory to God alone" appears once at the close of the canon and the foundational README. It does not need to appear in every file.

---

## Discussions and disagreements

Disagreement about Canon-scope changes should happen in the open: GitHub issues with clear position statements, witnessed responses, time to settle. The same protocol the engine enforces applies to its own governance — slow is the point, not the bug.

For domain-scope disagreements, the standard PR-review back-and-forth is fine.

---

*See also: [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for setup and PR mechanics; [`CANON.md`](CANON.md) for the immutable commitments this protocol defends.*
