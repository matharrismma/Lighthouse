"""Verify the autonomy governor enforces the control-theory discipline."""
from api.autonomy import Governor, CONTINUE, STOP, HOLD

ok = []

# 1) Converging error -> CONTINUE, then STOP at convergence.
g = Governor(reference="reach the goal", tolerance=0, patience=3, max_ticks=50)
d1 = g.tick(5).decision
d2 = g.tick(3).decision
d3 = g.tick(0).decision   # reached tolerance
ok.append(("converge", d1 == CONTINUE and d2 == CONTINUE and d3 == STOP and g.converged()))

# 2) No progress -> STOP drifting (after patience).
g = Governor(reference="x", tolerance=0, patience=2, max_ticks=50)
g.tick(4)                 # improve (best=4)
s1 = g.tick(4).decision   # stall 1/2 -> continue
s2 = g.tick(4).decision   # stall 2/2 -> stop
ok.append(("anti-drift", s1 == CONTINUE and s2 == STOP and not g.converged()))

# 3) Runaway bound -> STOP at max_ticks even if still improving.
g = Governor(reference="x", tolerance=0, patience=99, max_ticks=3)
g.tick(9); g.tick(8)
b = g.tick(7).decision    # i == max_ticks -> bounded stop
ok.append(("bounded", b == STOP))

# 4) Uncertainty -> HOLD (fail-safe; never actuate on a bad signal).
g = Governor(reference="x")
h = g.tick(5, acted=False, uncertain=True)
ok.append(("fail-safe-hold", h.decision == HOLD and not h.acted))

# 5) Bounded actuation clamps magnitude.
g = Governor(reference="x", max_actuation_per_tick=1.0)
ok.append(("clamp", g.clamp(5.0) == 1.0 and g.clamp(-9.0) == -1.0 and g.clamp(0.4) == 0.4))

# 6) Authority ceiling: reversible auto-ok; outward/irreversible refused.
g = Governor(reference="x")
internal = g.authorize("build a local page")
outward = g.authorize("publish to the public site")
pay = g.authorize("transfer money")
ok.append(("authority", internal["auto_ok"] and outward["requires_authority"]
           and pay["requires_authority"]))

print("autonomy governor checks:")
for name, passed in ok:
    print(f"  {'PASS' if passed else 'FAIL'}  {name}")
print("ALL PASS" if all(p for _, p in ok) else "SOME FAILED")
