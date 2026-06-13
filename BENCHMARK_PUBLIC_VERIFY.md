# Public-endpoint verification benchmark

A fresh, adversarial check of the **live** moat -- the public endpoint an AI agent actually
calls: `POST https://narrowhighway.com/derivation/verify`. Unlike a pass-only benchmark, this
deliberately mixes **true** claims (should hold) with **false** ones (should be caught), because
the property that matters for a verifier is not "does it confirm truths" but **"does it ever
seal a falsehood."**

## Result (run 2026-06-13)

| Mode | n | correct | accuracy | false-positive | false-negative |
|---|---:|---:|---:|---:|---:|
| equality | 24 | 24 | 100.0% | 0 | 0 |
| inequality | 12 | 12 | 100.0% | 0 | 0 |
| derivative | 16 | 16 | 100.0% | 0 | 0 |
| **overall** | **52** | **52** | **100.0%** | **0** | **0** |

**26 of the 52 claims were deliberately false** -- perturbed identities (e.g. `sin^2+cos^2 = 2`),
sign-flipped derivatives (`d/dt cos(t) = sin(t)`), a missing binomial cross term
(`(a+b)^2 = a^2+b^2`), wrong special values (`sin(pi/6) = sqrt(2)/2`), a corrupted Euler identity
(`exp(i*pi)+1 = 1`), and false inequalities. **All 26 were caught.** The 26 true claims -- including
the genuine Euler identity, the double-angle cosine, the golden-ratio relation, and eight
derivative facts -- all held.

- **False-positive rate (sealed a falsehood): 0 / 26.** This is the load-bearing number.
- **False-negative rate (rejected a truth): 0 / 26.**

## What this does and does not show

- It tests the **public, hosted** endpoint (the adoption-relevant surface), not a local copy.
- It is an **adversarial spot-check** of the three mathematics modes (equality / inequality /
  derivative), 52 claims -- deliberately small and curated, fully reproducible, and extensible.
  It complements, and does not replace, the larger 722-claim local-domain benchmark
  (`lw/09_evaluation/RESULTS.md`).
- Ground-truth labels are author-curated; the script reports any true claim the engine cannot
  auto-confirm as a false-negative rather than hiding it (there were none this run).

## Reproduce

```bash
python tools/benchmark_public_verify.py
```

Each claim is one `seal=False` call to the live endpoint (no receipts minted). Add claims by
editing the `CLAIMS` list in the script. A claim counts as correct when a true claim returns
`verdict: HOLDS` and a false claim returns anything else (`BROKEN` / `MISMATCH`).
