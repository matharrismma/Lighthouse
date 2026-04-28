from __future__ import annotations
import argparse
from tools.loader import load_canon

def _fail(msg: str) -> None:
    raise SystemExit(f"[BIO VALIDATION FAIL] {msg}")

def validate_biology(modules="all") -> None:
    canon = load_canon("biology", modules=modules)
    core = canon["core"]

    if "red_layer_constraints" not in core:
        _fail("core missing red_layer_constraints")

    nouns = core.get("frozen_nouns", [])
    if len(nouns) < 10:
        _fail("frozen_nouns should have at least 10 entries")

    diag = core.get("diagnostics", {})
    if "root" not in diag:
        _fail("missing diagnostics.root")

    anchors = core.get("scripture_anchors", [])
    if len(anchors) < 7:
        _fail("scripture_anchors should have at least 7 entries")

    md = core.get("measurement_doctrine", {})
    if "replication_minimum" not in md:
        _fail("measurement_doctrine missing replication_minimum")

    print("[OK] Biology Canon validated")

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modules", default="all")
    args = ap.parse_args()
    modules = "all" if args.modules == "all" else [x.strip() for x in args.modules.split(",") if x.strip()]
    validate_biology(modules=modules)

if __name__ == "__main__":
    main()
