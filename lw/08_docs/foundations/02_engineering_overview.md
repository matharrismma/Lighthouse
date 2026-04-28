# Engineering Overview (Compressed)

## What to build
A small kernel that:
1) receives a problem packet,
2) fetches Scripture anchors (by index),
3) routes to a minimal action set,
4) enforces gates (Red/Floor/Brothers/God),
5) logs an append-only ledger,
6) produces playbook entries.

## Names (stable)
- **Company:** Lighthouse
- **Product:** Waymaker
- **Roles:** Keeper, Steward, Scribe (Guide is optional UI persona; Sage removed)

## Minimal architecture (planes)
- **Vessel plane:** constraints + execution (offline-first)
- **Journal plane:** immutable record + local memory
- **Lighthouse plane:** coordination + witness + waiting (can run offline and sync later)

Physical firewall concept: each plane can be isolated; synchronization is packet-based.

## Minimal packet types
- `SRC` — scripture anchors (refs only; verse text optional via edition key)
- `ACT` — action chosen (road + spend + floors)
- `PBK` — playbook entry (confession + refs + outcome + witnesses + wait)

## Reference implementations
- `code/the_way_kernel_min.py` — minimal kernel (start here)
- `code/pck_problem_engine_best.py` — richer “problem engine” prototype
- `code/pck_physical_firewall_pack.py` — firewall/planes concepts

## Data
- `data/nwga_seed_trimmed.yaml` — econdev seed example
- `data/schema_registry_econdev_v1.json` — packet schema registry
