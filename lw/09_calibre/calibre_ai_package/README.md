# Calibre - Alignment/Calibration Engine (ledgerless)

Export package for the refined model at **formula + code** level.

## Concepts included
- Triadic Flow (Spirit->Mind->Body)
- Health + Beauty (heuristics)
- Shadow of Law (boundary distortion under load)
- Vice (channel bypass / speed over form)
- Milk->Meat smoothing (access + streak gates)

## Quickstart
```python
from calibre import Rules, Contract, State, Signals
from calibre import step

r = Rules()
c = Contract(law_ok=True, wait_open=True, witness=1, mutual=True, proof=True)
s = State(tier=None)  # or State()

sig = Signals(rumination=0.1, peace=0.6, obedience=0.5, clarity=0.4, fruit_delta=0.2)
s, res, blk = step(c, s, r, sig)
print(s, res, blk)
```
(Tip: Use the `docs/spec.md` as the "prompt spec" for other AIs.)

## Capping harvest growth — `fruit_ceiling`

`Rules.fruit_ceiling: float` defaults to `inf`, which preserves the original unbounded behavior. The harvest function compounds `fruit * harvest_gain * (1 + w_align*align + w_clean*clean)` per cycle, so under strong sustained signals fruit climbs without limit (~446 in 10 cycles at default rules, ~9329 in 10 cycles under maximal signals).

When Calibre is read as a forecast model rather than as an alignment metaphor, the unbounded form produces nonsense numbers. Set a finite ceiling:

```python
from dataclasses import replace
from calibre import Rules, Contract, State, Signals, step

r = replace(Rules(), fruit_ceiling=50.0)
# ... cycles will saturate fruit at 50 instead of compounding past it
```

The cap applies only to the harvest output. `firstfruits` (10% of fruit set aside before harvest) continues to accumulate normally and is independent of the ceiling.

Choose the ceiling based on how Calibre is being used:
- Alignment metaphor (no ceiling needed): leave at `inf`.
- Personal formation tracker (numbers should feel like reality): pick a ceiling roughly matching the unit you're measuring in.
- Group / org dashboard (numbers must be comparable across runs): pick a ceiling per metric type and document it alongside the rules.
