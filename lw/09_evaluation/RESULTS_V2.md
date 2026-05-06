# Benchmark V2 Results

**Date:** 2026-05-06  
**Dataset:** 202 items (50% correct, 50% incorrect)  
**Domains:** mathematics, chemistry, physics, statistics, formal_logic, computer_science  

## Overall Accuracy

| System | Accuracy | FPR | FNR | Abstains | Median Lat | p95 Lat |
|--------|----------|-----|-----|----------|-----------|---------|
| Concordance Engine | **100.0%** | 0.0% | 0.0% | 0 | 1ms | 29ms |
| Claude Haiku | **91.6%** | 1.0% | 15.8% | 0 | 688ms | 1428ms |
| Claude Sonnet | **96.5%** | 2.0% | 5.0% | 1 | 1293ms | 2183ms |

## Confusion Matrices

### Concordance Engine

| | Predicted correct | Predicted incorrect | Abstain |
|---|---|---|---|
| **Actually correct** | 101 | 0 | 0 |
| **Actually incorrect** | 0 | 101 | 0 |

### Claude Haiku

| | Predicted correct | Predicted incorrect | Abstain |
|---|---|---|---|
| **Actually correct** | 85 | 16 | 0 |
| **Actually incorrect** | 1 | 100 | 0 |

### Claude Sonnet

| | Predicted correct | Predicted incorrect | Abstain |
|---|---|---|---|
| **Actually correct** | 95 | 5 | 1 |
| **Actually incorrect** | 2 | 99 | 0 |

## Per-Domain Accuracy

| Domain | N | Concordance | Haiku | Sonnet |
|--------|---|-------------|-------|--------|
| chemistry | 30 | 100% | 87% | 100% |
| computer_science | 16 | 100% | 94% | 94% |
| formal_logic | 38 | 100% | 95% | 100% |
| mathematics | 60 | 100% | 98% | 100% |
| physics_conservation | 16 | 100% | 81% | 88% |
| physics_dimensional | 14 | 100% | 100% | 100% |
| statistics | 28 | 100% | 79% | 85% |

## Cost & Latency

| System | Cost (est.) | Tokens | Median Lat | p95 Lat |
|--------|------------|--------|-----------|---------|
| Concordance Engine | $0.00 | 0 | 1ms | 29ms |
| Claude Haiku | $0.0457 | 11,414 | 688ms | 1428ms |
| Claude Sonnet | $0.0685 | 11,414 | 1293ms | 2183ms |

## Notes

- Concordance engine is **deterministic** — same input always yields same result.
- LLM answers are stochastic; a single pass was used here.
- Concordance 'abstain' = verifier returned NOT_APPLICABLE (no evidence for or against).
- LLM 'abstain' = response did not contain 'correct' or 'incorrect'.
- Concordance cost is effectively $0 (local CPU, no API calls).
