# Cookbook

Worked examples for the most common kinds of packets. Each recipe shows the
packet, the verdict the engine returns, and what would change the verdict.
Copy a recipe, edit the parts that apply to your case, submit.

If you only read one section, read **A. Reflect first, commit later.** The
`/reflect` endpoint runs the same gates as `/submit` without writing to the
ledger — use it to rehearse a packet until it passes, then commit.

---

## A. Reflect first, commit later

Every packet in this cookbook can be sent to `POST /reflect` instead of
`POST /submit` to see the verdict without recording anything. The response
shape is identical. The only difference: `ledger_seq` and `ledger_entry_hash`
will be `null` because the ledger was not touched.

```bash
curl -s -X POST https://narrowhighway.com/reflect \
  -H 'Content-Type: application/json' \
  -d @your_packet.json | jq .overall
```

When you see `"PASS"`, switch the URL to `/submit`. The packet that passed
in reflect will pass in submit because the gate logic is the same; only the
side effect (ledger write) differs.

---

## B. A chemistry equation

The smallest possible chemistry packet that asks the engine to verify a
balanced reaction:

```json
{
  "domain": "chemistry",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "CHEM_RED": {
    "mass_conserved": true,
    "charge_balanced": true,
    "elements_consistent": true,
    "phases_specified": true
  },
  "CHEM_SETUP": {
    "reagents": ["C3H8", "O2"],
    "products": ["CO2", "H2O"],
    "temperature_K": 298.15
  },
  "CHEM_VERIFY": {
    "equation": "C3H8 + 5 O2 -> 3 CO2 + 4 H2O",
    "temperature_K": 298.15
  }
}
```

**Verdict:** PASS. Atoms balance (C: 3=3, H: 8=8, O: 10=10). Charge balances
(neutral). Temperature is positive. All four gates pass.

**To make it REJECT:** change `5 O2` to `4 O2`. The verifier responds
`unbalanced under stated coefficients but balances as: C3H8 + 5 O2 -> 3 CO2 + 4 H2O`
— the engine tells you the right coefficients.

**To make it MISMATCH on RED attestation but PASS on the math:** flip
`mass_conserved` to `false` while leaving the equation correct. The
attestation gate rejects (you declared a violation); the verifier would
have passed if it ran.

---

## C. A physics dimensional check

```json
{
  "domain": "physics",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "PHYS_RED": {"units_consistent": true, "limits_respected": true},
  "PHYS_VERIFY": {
    "mode": "dimensional",
    "equation": "F = m * a",
    "symbols": {
      "F": "newton",
      "m": "kilogram",
      "a": "meter/second**2"
    }
  }
}
```

**Verdict:** PASS. Both sides reduce to `kg·m·s⁻²`.

**To break it:** change `"F": "newton"` to `"F": "joule"`. Joule is
`kg·m²·s⁻²`, which doesn't match `kg·m·s⁻²`. MISMATCH with the unit
signatures named explicitly.

---

## D. A statistical p-value claim

```json
{
  "domain": "statistics",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "STAT_RED": {
    "test_pre_registered": true,
    "no_p_hacking": true,
    "raw_data_available": true
  },
  "STAT_VERIFY": {
    "test": "two_sample_t",
    "n1": 30, "n2": 30,
    "mean1": 5.0, "mean2": 4.0,
    "sd1": 1.0, "sd2": 1.0,
    "claimed_p": 0.0003
  }
}
```

**Verdict:** PASS. The verifier recomputes p from the raw inputs and
finds it within tolerance of `0.0003`.

**To make it MISMATCH:** change `claimed_p` to `0.05`. The recompute
returns the real p-value (~0.0003) and flags the discrepancy.

**To exercise the multiple-comparisons verifier instead:** swap
`STAT_VERIFY` for the `multiple_comparisons` shape with `raw_p_values`,
`method`, and `claimed_rejected_indices`.

---

## E. A computer-science correctness + complexity claim

```json
{
  "domain": "computer_science",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "CS_RED": {"deterministic": true, "terminates": true},
  "CS_VERIFY": {
    "code": "def lsum(a):\n    s = 0\n    for x in a:\n        s += x\n    return s",
    "function_name": "lsum",
    "test_cases": [
      {"args": [[1, 2, 3]], "expected": 6},
      {"args": [[]], "expected": 0},
      {"args": [[-1, 1]], "expected": 0}
    ],
    "input_generator": "def gen(n):\n    return [list(range(n))]",
    "claimed_class": "O(n)"
  }
}
```

**Verdict:** PASS. Static termination scan succeeds (the `for` loop is
bounded). All three test cases match. Runtime measurement at log-spaced
sizes shows linear scaling within the slope tolerance.

**To make it MISMATCH:** change `claimed_class` to `O(log n)`. The
log-log slope fit comes out near 1.0, not near 0; the verifier rejects.

**To make the code reject on RED:** introduce non-determinism (e.g.
`return s + random.random()`). The static scan flags the import; even if
it didn't, the determinism-trials check would fail across repeated runs.

---

## F. A governance decision packet

```json
{
  "domain": "governance",
  "witness_count": 3,
  "created_epoch": 1700000000,
  "DECISION_PACKET": {
    "title": "Approve Q2 community-trades cooperative funding",
    "decision": "Allocate $250,000 from the Phase 1 fund to launch the trades cooperative pilot.",
    "rationale": "Aligns with the strategic foundation for raising the regional floor; pilot scope and exit criteria documented.",
    "scope": "canon",
    "red_items": [
      "No coercion applied to participating members",
      "Acting within the board's authorized scope",
      "No rights of any party are violated"
    ],
    "floor_items": [
      "Participating members informed and acknowledged",
      "Treasury approval recorded",
      "Exit criteria documented if pilot fails"
    ],
    "way_path": "Issue RFP through GNWTC partnership; constrain pilot to trades curriculum; quarterly review with public reporting.",
    "execution_steps": [
      "Draft RFP",
      "Board review",
      "Public comment period",
      "Issue RFP",
      "Evaluate responses"
    ],
    "witnesses": ["Board Chair", "Treasurer", "GNWTC President"],
    "witness_count": 3,
    "scripture_anchors": ["Mic 6:8", "Pr 22:16"]
  }
}
```

**Verdict:** PASS at `/reflect`. At `/submit` the strict timing of the GOD
gate would QUARANTINE because canon-scope decisions require 7 days of
elapsed wait. (See `/submit` vs `/validate` policy in `llms.txt`.)

**Notable:** the scripture verifier runs automatically on this packet
because `scripture_anchors` is present. If the references resolve in WEB,
you get a `scripture.anchors: CONFIRMED` result attached. If a reference
is fabricated, you get MISMATCH with the failed refs named.

**To make it REJECT:** shorten `way_path` to two words. The governance
verifier rejects with `way_path is too short to describe the chosen path`.
Real decisions name the path in at least one full sentence.

---

## G. A multi-domain packet

A single packet can carry multiple `*_VERIFY` blocks. The engine routes
based on `domain` for the attestation gates, then runs every applicable
verifier:

```json
{
  "domain": "chemistry",
  "scope": "adapter",
  "created_epoch": 1700000000,
  "CHEM_RED": {"mass_conserved": true, "charge_balanced": true,
               "elements_consistent": true, "phases_specified": true},
  "CHEM_VERIFY": {
    "equation": "2 H2 + O2 -> 2 H2O",
    "temperature_K": 298.15
  },
  "MATH_VERIFY": {
    "mode": "equality",
    "expr_a": "(x+1)**2",
    "expr_b": "x**2 + 2*x + 1",
    "variables": ["x"]
  }
}
```

**Verdict:** PASS. Both verifiers run; both confirm.

**Use this when** your decision rests on multiple kinds of computational
truth (e.g. a process-design packet that needs the chemistry to balance
AND the throughput math to check).

---

## H. A packet with scripture anchors only

Sometimes you want the engine to verify references without doing anything
else load-bearing — useful for citation review.

```json
{
  "domain": "governance",
  "witness_count": 1,
  "created_epoch": 1700000000,
  "DECISION_PACKET": {
    "title": "Citation-only review",
    "decision": "Verify these scripture references resolve in WEB.",
    "rationale": "Pre-flight check before publishing.",
    "scope": "adapter",
    "red_items": ["No coercion"],
    "floor_items": ["Reference list provided"],
    "way_path": "Submit references for verification against the World English Bible.",
    "execution_steps": ["Submit", "Read result"],
    "witnesses": ["editor"],
    "witness_count": 1,
    "scripture_anchors": [
      "Mic 6:8",
      "Pr 22:16",
      "Jas 1:27",
      "Mat 25:40"
    ]
  }
}
```

**Verdict:** depends on whether each ref resolves in the WEB. The
governance verifier processes the packet structure; the scripture
cross-cutting verifier processes the anchors. You get
`scripture.anchors: CONFIRMED` if all four resolve, or MISMATCH naming
the ones that don't.

**Note:** if the server hasn't provisioned Layer 0 (no
`lw/00_source/fetch_sources.py` run), the result will be SKIPPED with a
detail explaining how to enable it. The packet still goes through every
other gate normally.

---

## I. Scripture lookup without a packet

You don't have to wrap a single reference in a packet — there's a direct
endpoint:

```bash
# Look up a verse
curl -s https://narrowhighway.com/scripture/Jn3:16

# Strong's word study
curl -s https://narrowhighway.com/strong/G26
```

Or via MCP from inside an LLM tool loop:

```
resolve_scripture_ref(ref="Jn3:16")
word_study(strongs_num="G26")
verify_scripture_anchors(anchors=["Mic 6:8", "Pr 22:16"])
```

These don't touch the ledger and don't run gates. They're for citation
verification and word study, full stop.

---

## J. Reading the ledger

Every committed decision is on the public ledger. To browse:

```bash
# Newest 50
curl -s https://narrowhighway.com/ledger | jq .

# Just one entry by packet_id
curl -s https://narrowhighway.com/ledger/governance | jq .

# Verify the hash chain end-to-end
curl -s https://narrowhighway.com/ledger/verify
```

A successful `/ledger/verify` response (`{"valid": true, "entries_checked": N}`)
is your proof that the chain has not been rewritten since each entry was
committed. Anyone can run this check at any time. The genesis hash is 64
zeroes; every subsequent entry's hash is computed from the prior entry's
hash plus the packet hash plus the overall verdict plus the timestamp.
Tampering with any one of those values invalidates every later entry.

---

## What goes here next

Patterns worth adding once we have real examples to point at: a biology
dose-response with the new Hardy-Weinberg check, a physics conservation
packet with `law=energy` named-law profile, a Calibre/canon-scope packet
that exercises the 7-day GOD wait against `/validate`. PRs welcome.
