# Contribution Protocol (Lighthouse Ledger)

Governs changes to adapters, mesh rules, and Canon.

## Packets
- SUB: submission (includes confession + refs + scope)
- WIT: witness attestation (align + floor safety)
- DEC: decision (CONF/Q/REJ)

## Four Gates
RED → FLOOR → BROTHERS → GOD

Hard gates: RED/FLOOR (fail → REJ)
Soft gates: BROTHERS/GOD (fail → Q)

## Scope defaults
- A: wmin=2, wait=3600s
- M: wmin=3, wait=86400s
- C: wmin=7, wait=604800s
