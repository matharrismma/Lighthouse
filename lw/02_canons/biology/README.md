# Concordance Canon — Biology (v1.0)

The **Biology domain canon** for the Concordance / Lighthouse-style constraints-first engine.

## Structure

- `canon.yaml` — entrypoint registry (core + schema + module registry)
- `core/biology_core.yaml` — domain identity, primitives (frozen nouns), RED/FLOOR/WAY/Execution, diagnostics, truth tables, measurement doctrine, bridges
- `schema/biology_schema.yaml` — packet schema and rules
- `modules/*.yaml` — operational modules (cell, metabolism, genetics, systems/control, evolution/ecology)
- `templates/` — packet template + proof checklist
- `examples/` — example packet inputs for diagnostics
- `../tools/` — lightweight structural validator (shared across canons)

## Quickstart

```bash
python -m tools.validator_biology
python -m tools.validator_biology --modules all
```

## Notes

- Designed to compose with Chemistry / Physics / Engineering / Materials via bridge rules.
- Constraints-first and AI-parseable (YAML).
