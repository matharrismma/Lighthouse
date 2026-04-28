from __future__ import annotations
import json, random
from dataclasses import dataclass
from typing import Any, Dict, List
import yaml

@dataclass(frozen=True)
class SeedSpec:
    level: str
    seed_id: str
    jurisdiction: List[str]
    params: Dict[str, float]
    governance: Dict[str, Any]
    mission_outcomes: Dict[str, Any]
    portfolio_mechanics: Dict[str, Any]
    rng: int = 7

@dataclass
class KernelResult:
    seed_id: str
    level: str
    years: int
    final_cash: float
    final_reserves: float
    built_units: int
    matured_units: int
    never_events: int
    shocks: int

def _seed_from_node(level: str, node: Dict[str, Any]) -> SeedSpec:
    ident = node.get("identity", {})
    params = node.get("parameters", {})
    return SeedSpec(
        level=level,
        seed_id=ident.get("seed_id", f"UNKNOWN_{level}"),
        jurisdiction=ident.get("jurisdiction", []) or [],
        params={k: float(v) for k, v in (params.items() if params else [])},
        governance=node.get("governance_constraints", {}) or {},
        mission_outcomes=node.get("mission_outcomes", {}) or {},
        portfolio_mechanics=node.get("portfolio_mechanics", {}) or {},
        rng=int(node.get("rng", 7)),
    )

def iter_seeds(nwga: Dict[str, Any]) -> List[SeedSpec]:
    out: List[SeedSpec] = []
    if "region" in nwga:
        out.append(_seed_from_node("region", nwga["region"]))
    # Map plural collection name -> singular level label
    level_for = {"territories": "territory", "clusters": "cluster", "sites": "site"}
    for lvl, label in level_for.items():
        for item in nwga.get(lvl, []) or []:
            out.append(_seed_from_node(label, item))
    return out

def msk_run_stub(seed: SeedSpec, years: int = 40) -> KernelResult:
    rng = random.Random(seed.rng)

    cash = seed.params.get("OPF", 0.0) * 1.5
    reserves = 0.0
    built = 0
    matured = 0
    never_events = 0
    shocks = 0

    floor = seed.params.get("OPF", 0.0)
    reserve_target = seed.params.get("RESF", 0.0)
    sew_rate = seed.params.get("SEW_RATE", 0.9)
    seed_in = seed.params.get("SEED_IN", 0.0)
    cost_site = seed.params.get("COST_SITE", 1.0)
    surplus_site = seed.params.get("SURP_SITE", 0.0)
    firstfruits = seed.params.get("FIRSTFRUIT_RATE", seed.governance.get("reserve_rule_firstfruits", 0.1))

    shock_model = (seed.portfolio_mechanics.get("shock_model", {}) or {})
    shock_freq = int(shock_model.get("shock_frequency", 5))
    shock_impact = float(shock_model.get("shock_impact", 0.3))
    failure_rate = float(shock_model.get("failure_rate", 0.02))

    for t in range(1, years + 1):
        if shock_freq > 0 and (t % shock_freq == 0):
            shocks += 1
            cash *= (1.0 - shock_impact)

        if rng.random() < failure_rate:
            never_events += 1
            cash *= 0.98
            continue

        to_reserve = max(0.0, cash - floor) * firstfruits
        cash -= to_reserve
        reserves = min(reserve_target, reserves + to_reserve)

        can_build = (cash - seed_in) >= floor and rng.random() < sew_rate
        if can_build and seed_in > 0:
            spend = min(seed_in, cash - floor)
            cash -= spend
            built += max(1, int(spend // cost_site) or 1)
            cash += surplus_site
            matured += 1

    return KernelResult(
        seed_id=seed.seed_id,
        level=seed.level,
        years=years,
        final_cash=cash,
        final_reserves=reserves,
        built_units=built,
        matured_units=matured,
        never_events=never_events,
        shocks=shocks,
    )

def main(yaml_path: str) -> None:
    with open(yaml_path, "r", encoding="utf-8") as f:
        nwga = yaml.safe_load(f)

    seeds = iter_seeds(nwga)
    results = [msk_run_stub(s, years=40) for s in seeds]

    print("40-Year Stress Test Results (Harness + Stub Kernel)")
    for r in results:
        print(f"- {r.seed_id} ({r.level}): built={r.built_units}, cash=${r.final_cash:,.0f}, "
              f"reserves=${r.final_reserves:,.0f}, shocks={r.shocks}, never_events={r.never_events}")

if __name__ == "__main__":
    import sys
    main(sys.argv[1])
