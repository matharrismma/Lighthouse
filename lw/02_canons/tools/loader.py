from __future__ import annotations
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_canon(domain: str, modules="all") -> dict:
    domain_dir = ROOT / domain
    canon = load_yaml(domain_dir / "canon.yaml")
    core = load_yaml(domain_dir / canon["canon"]["entrypoints"]["core"])
    schema = load_yaml(domain_dir / canon["canon"]["entrypoints"]["schema"])
    regs = canon["canon"].get("module_registry", [])
    loaded_modules = {}
    if modules == "all":
        for m in regs:
            loaded_modules[m["id"]] = load_yaml(domain_dir / m["path"])
    else:
        wanted = set(modules)
        for m in regs:
            if m["id"] in wanted:
                loaded_modules[m["id"]] = load_yaml(domain_dir / m["path"])
    return {"canon": canon, "core": core, "schema": schema, "modules": loaded_modules}
