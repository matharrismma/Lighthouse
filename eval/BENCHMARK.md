# Concordance Engine Benchmark

A head-to-head benchmark: **Claude alone** vs **Claude + concordance-engine tools** on 37 items across chemistry (17), statistics (10), physics (10).

The point: produce a defensible number for "does adding the verifier toolbox to an LLM measurably improve accuracy?" If yes, we have evidence. If no, we have an honest finding.

## Files

```
eval/benchmark/
  build_items.py          # generate items.jsonl with engine-derived ground truth
  items.jsonl             # 37 benchmark items
  runner.py               # call a completion fn over items, score against truth
  adapter_anthropic.py    # claude_alone() + claude_with_tools() factories
  results_*.jsonl         # produced by adapter_anthropic.run_both()
```

## Build the items

```bash
python eval/benchmark/build_items.py
```

Idempotent. Ground truth comes from the engine itself for chemistry/physics and from `scipy.stats` for statistics, so re-running can't drift the labels.

## Smoke-test the runner (no API)

```bash
python eval/benchmark/runner.py
```

This runs an "always-yes / always-0.05" stub over all 37 items. Expected: ~43% (gets lucky on yes/no items, hits 0% on numeric). Confirms the wiring.

## Run the head-to-head against Claude

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

python eval/benchmark/adapter_anthropic.py
```

That runs both modes (alone, with-tools) on all 37 items, prints summaries, and writes `results_<model>_alone.jsonl` and `results_<model>_tools.jsonl`. Cost on Haiku 4.5 is roughly $0.05 per full run.

The script also prints which items the engine *fixed* (model wrong alone, right with tools) and which it *broke* (right alone, wrong with tools — this should be near zero if the tools are well-described).

## What "good" looks like

A meaningful result is at least one of:

- **Statistics: large delta.** Claude alone has to do mental p-value arithmetic on inputs like `n1=30, n2=30, mean1=5.0, mean2=4.0, sd1=1.0, sd2=1.0`. With `verify_statistics_pvalue` in scope, it should approach 100%. If alone scores below 70% and with-tools scores above 95%, that's the headline number.
- **Chemistry: the unbalanced ones.** Claude alone often confidently misidentifies `Fe + O2 -> Fe2O3` as balanced. With `verify_chemistry` it shouldn't. Watch the unbalanced subset specifically.
- **Physics: edge cases.** `s = u * t**2` is dimensionally wrong (s should be `u*t + 0.5*a*t**2` or similar). Both modes may get easy yes/no items right; the discriminator is the few that look right but aren't.

## What honest failure looks like

If Claude alone already scores 95%+ on this benchmark, it means the items are too easy and the engine adds no measurable value at this difficulty. That's a useful finding — extend the benchmark with harder items (subtle dimensional analysis, paired-t with non-obvious tail, p-values near α). Don't paper over a null result.

If the with-tools score is *worse* than alone, the tool descriptions need tightening (the model is calling tools wrong, or formatting the output wrong post-tool-call). That's also a finding: it tells you the LLM's bottleneck wasn't the math, it was the tool ergonomics.

## Extending the benchmark

Add items to `build_items.py`. The benchmark is intentionally small (37 items) so it costs cents per run; scale it as the discriminator becomes clearer. Aim for items where:

1. The right answer is mechanical (the engine can produce it).
2. Naive LLM intuition gets it wrong frequently.
3. The prompt format is unambiguous (single yes/no or single number).

A useful extension would be 30-50 items per domain pulled from real corpora (textbook problem sets, retracted papers, FDA-flagged medical claims). The current 37 are just enough to see if the signal exists.
