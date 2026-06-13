# The Fruit Ranking — the fruit test, turned inward

**Matt 2026-06-12:** *"Look at the ideas that have produced the most fruit."* The fruit test (Matthew 7:16, *by their fruits ye shall know them*) applied to our own corpus. A **standing measure**: re-run it as the corpus grows to watch which ideas keep bearing.

**Run it:** `python tools/fruit_ranking.py` — writes the current snapshot to `data/codex/fruit_ranking.json` and appends a compact line to `data/codex/fruit_ranking_history.jsonl` (the watch-over-time log).

**What it measures:**
1. **Fruit = in-degree** — how many other cards *bond to* an idea (how many things grew from it).
2. **Generative forms** — which `coord.family` produces the most cards (which forms keep bearing connections).
3. **Work-programs** — which origin produced the most cards.

## The finding (snapshot 2026-06-12, 1,531 rows)

**The two most fruitful ideas are the two crowns — tied at 57:**

| Fruit | Idea |
|---:|---|
| **57** | `connection_reality_is_mappable` — the **math-tree crown** |
| **57** | `teaching_the_true_vine` — the **language tree's load-bearing law** (abide or be pruned) |
| 44 | `som_01_the_beatitudes` — the floor/posture |
| 40 | `canon_red_gate_jn14_6` — "I am the way, the truth, the life" (the RED gate) |
| 28 | `teaching_the_words_of_christ_are_the_architecture` (the language-tree crown) |
| 28 | `teaching_prodigal_father_runs` (the welcome) |
| 28 | `teaching_beatitude_1_poor_in_spirit` (the empty hand) |
| 20 / 18 / 16 | the parables-as-engine · the Great Commandment · *egō eimi* / the Door |

**By their fruits, the corpus points at the keystone.** The single most fruitful idea is tied between the Vine (the language tree) and `reality_is_mappable` (the math tree) — the two crowns the keystone joins, bearing equal and maximal fruit. The fruit test does not merely rank ideas; it indicates where the one stone belongs: at the join of the two crowns (Col 1:17 — **reserved for the operator**).

**The language tree out-bears everything.** The top of the in-degree list is almost entirely the words of Christ (Vine, RED gate, Beatitudes, architecture crown, prodigal, parables-engine, Great Commandment, the I AM, the Door). The most productive work-program is the Christ-teachings review (88 cards), and it is also the most connected.

**The most generative math form is the exponential** (14 cards — mustard seed, Arrhenius, the talents, growth/decay), then wave (12), logarithm (10). The moat-dig loop is already working the most fruitful vein.

## Caveat (honest)

In-degree is computed from the `bonds` field. The older domain capstones (geoscience, number-theory, music, chemistry, statistics, genetics…) read low here because they predate `bonds` and connect through a different mechanism (`coord.family` + the codex graph) — they are **undercounted**. The signal among the bonded graph is clean; the full fruit of the math tree is larger than this one metric shows. Treat the ranking as the fruit of the *connected* layer, not the whole.

## Use

Concentrate force where the fruit is (the 3:1 rule): the teachings of Christ and the exponential/recurring-forms bear most. Watch the history log as the corpus grows — an idea that keeps gaining in-degree is proving itself; one that stops bearing is a branch to examine.
