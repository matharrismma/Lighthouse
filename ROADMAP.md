# Roadmap

What's next, in rough priority order. The architecture is operational
(see `CHANGELOG.md` v1.1.0); this file is what's *not yet* in the live
engine but is consonant with the canon and worth building.

## Near term (months)

### Lighthouse layer (distributed witness)

The current ledger at `narrowhighway.com` is a single Vessel. The Canon
(see `docs/CANON.md` §5 and `docs/LAYERS.md` §LIGHTHOUSE) describes a
distributed-witness layer where multiple Vessels exchange SUB / WIT /
DEC packets. Concretely:

- **`POST /witness`** — one Vessel attests another Vessel's packet by
  packet_hash. Quarantined packets at BROTHERS could be lifted to PASS
  by accumulating remote witnesses.
- **`POST /subscribe`** — a Vessel subscribes to another Vessel's
  ledger and receives DEC packets as they're committed.
- **`GET /dec`** — list DEC packets visible to the current Vessel.

This unlocks the church-of-agents framing for real: not one engine,
many engines speaking to each other under one canon.

### Backed-up ledger redundancy

A single-instance ledger on a desktop is honest about being
desktop-tethered, but it is also a single point of failure. Plan: add
an optional **mirror Vessel** that subscribes to the primary and
maintains a verified shadow ledger. If the primary goes down, the
mirror is read-only but available; `/ledger/verify` against the mirror
proves the chain to the moment of the outage.

### Lectionary endpoint

`GET /lectionary?topic=stewardship` returns scripture references the
verifier already knows are well-attested for that topic, plus suggested
search terms. Not "scripture lookup" (that's `/scripture`) but
"discernment seed" — agents who don't know which references to cite
get a quality-controlled starting set.

### CI: continuous heuristic eval

`.github/workflows/ci.yml` runs the test matrix on every push. Add a
post-merge step that runs `eval/run_eval.py --mode=heuristic` and
appends the result to a public dashboard so dataset drift is visible.

### Test surface for new endpoints

`tests/test_api.py`, `tests/test_ledger.py`, `tests/test_scripture.py`
covering the v1.1.0 surface (`/reflect`, `/confess`, `/dispatch`,
`/stats`, `/about`, `/triangulate`, ledger helpers, scripture
verifier). Currently no API-layer tests; this is the most concrete
remaining quality gap.

## Medium term (quarter)

### A genuinely fine-tuned Keeper

The training kit (`training/`) is ready. Run a real fine-tune (one of
the open-weights paths in `training/adapters/huggingface_sft.py`),
publish the LoRA adapter, document the actual scored numbers in
`training/BASELINE.md`. Replace the projected tier targets with
measured ones.

### Morphologically-tagged Layer 0

`triangulate_claim` currently returns NEEDS_HUMAN_REVIEW because
auto-detection of drift requires morphologically-tagged texts (morphhb
for Hebrew, MorphGNT for Greek). Activate those, wire into `drift_check.py`,
upgrade the verdict to PASS / DRIFT_FLAGGED automatically when the
claim either survives or fails the per-word semantic check.

### NWGA Phase-1 fund: real exercise on the live engine

The example packet `sample_packet_jda_phase1_fund.json` represents a
real strategic decision. Run it through `/validate` (with auth) when
the actual decision is made; the resulting CONFIRMED entry becomes the
first non-test commitment in the ledger. Document publicly.

### A second Vessel

Stand up a second instance of the engine somewhere geographically
distinct (a different desktop, a small VPS, a Raspberry Pi). Have it
witness packets from `narrowhighway.com`. The Lighthouse layer goes
from spec to running pair.

## Longer term (year)

### Hardware Steward

The `lw/03_kernel/firewall.py` reference describes a gate-as-physical-constraint
model. A small microcontroller (the SAR-45 / 121 / Calibre hardware
packages on the desktop point at this) acts as the Steward layer in
hardware: signs ledger entries with a private key, refuses to write to
the ledger if the gate verdicts don't match the packet, can stop the
line by holding a physical interlock.

This is what makes the protocol *un-bypassable* even by the operator —
the hardware refuses to commit a packet whose gate verdicts have been
tampered with.

### Calibre integration

`lw/09_calibre/` is the formation/alignment engine — currently
disjoint from the validation engine. Calibre observes a Vessel's
trajectory (chaff / fruit / firstfruits / harvest); the Concordance
Engine validates discrete decisions. Joining them: a Vessel's Calibre
state becomes a soft input to BROTHERS, modeling whether the Vessel
itself is in a posture to be trusted with the scope it's claiming.

### Multi-language ports

The kernel files (`lw/03_kernel/`) plus the canon (`canons/<domain>/spec.md`)
are the contract. Port to Go for hardware-adjacent stacks, Rust for
embedded, Elixir for the distributed-witness layer. The Python engine
in `src/` becomes one implementation among several.

## Indefinite (when ready, not before)

### Lectionary cycle

A liturgical calendar overlay: known seasons surface different
default scripture references, different default RED-gate emphases.
Lent emphasizes specific predicates; Advent emphasizes others. This is
formation infrastructure, not validation infrastructure — it shapes the
posture of the Keeper without changing the gates.

### Open the door to other roots

Currently Layer 0 is one tradition's scriptures. Adding additional
traditions as parallel Layer-0 sources (Talmud, Quran with hadith,
Buddhist sutras, etc.) is a Canon-scope discussion that the project
isn't ready for and may never be. The current architecture supports it
structurally (verifiers are computationally independent of Layer 0
content), but the question of which sources serve as roots — and the
relationship between roots — is not engineering. It's the kind of
question the engine is built to slow down on.

---

## What's NOT on the roadmap

- A web UI beyond the current submit form. The site stays text + form.
- A SaaS / hosted product. The engine is open source; anyone can run
  their own Vessel.
- Verifiers for "vibes" or "alignment scores" without a verifier-style
  ground truth. The whole point is computational verification.
- Replacing the Layer 0 sources with summaries / paraphrases. Locked
  reference is a hard commitment.

---

*Roadmap items become real when they ship. Until then they are
direction, not promise.*
