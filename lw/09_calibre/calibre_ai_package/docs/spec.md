# Calibre Spec (Formula + Code Mapping)

## Triadic Flow
Spirit (Source) -> Mind (Channel) -> Body (Sink)

## Health
Let s,m,b in [0,1].
- presence = (s+m+b)/3
- spread = max(s,m,b) - min(s,m,b)
- health = clamp(0.60*(1-spread) + 0.40*presence)

## Beauty
- comp = max(s,m,b) - (s+m+b)/3
- economy = clamp(1-comp)
- beauty = clamp(health * economy)

## Shadow of Law
Inputs L,C,P in [0,1]:
- overload = max(0, P-C)
- shadow = clamp(L * overload)

Shadow is diagnostic (capacity/load mismatch), not "evil".

## Vice
Inputs S,K,D in [0,1]:
- bypass = D*(1-K)
- false_source = (1-S)*D
- vice = clamp(0.60*bypass + 0.40*false_source)

## Transition smoothing
Tier is binary, but progress is continuous:
- access: 0..3
- align_streak, proof_streak

Upgrade requires:
- Setup gates: LAW, WAIT, WITNESS
- Positioning gates: MUTUAL, PROOF
- Conversion gate: ALIGN
- access >= 3
- align_streak >= N
- proof_streak >= M

## Harvest ceiling
`harvest_gain * (1 + w_align*align + w_clean*clean)` compounds without a
natural bound. v0.1 left this unbounded (faithful to the metaphor: there is
no ceiling on what God may give). v0.2 adds `Rules.fruit_ceiling` (default
`+inf`, preserves prior behavior) so deployments that use Calibre as a
forecast can cap growth without forking the engine.
