# Concordance Canon — Biology (v1.0)

This repository contains the **Biology domain canon** for the Concordance / Lighthouse-style constraints-first engine.

## Structure

- `biology/canon.yaml` — entrypoint registry (core + schema + module registry)
- `biology/core/biology_core.yaml` — domain identity, primitives (frozen nouns), RED/FLOOR/WAY/Execution, diagnostics, truth tables, measurement doctrine, bridges
- `biology/schema/biology_schema.yaml` — packet schema and rules
- `biology/modules/*.yaml` — operational modules (cell, metabolism, genetics, systems/control, evolution/ecology)
- `biology/templates/` — packet template + proof checklist
- `biology/examples/` — example packet inputs for diagnostics
- `tools/` — lightweight structural validator

## Quickstart

```bash
python -m tools.validator_biology
python -m tools.validator_biology --modules all
```

## Notes

- This package is designed to compose with Chemistry / Physics / Engineering / Materials via bridge rules.
- It is *constraints-first* and *AI-parseable* (YAML).
