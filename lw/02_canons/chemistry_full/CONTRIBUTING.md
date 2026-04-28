# Contributing

## Principles
- Keep everything **plain-text YAML** and deterministic.
- Prefer **explicit definitions** over prose.
- Add diagnostics and failure modes for each module.
- Never weaken **RED** constraints to make an answer "work".

## Changes
1. Create a branch.
2. Add/modify files under `chemistry/`.
3. Ensure YAML is valid and consistent with `chemistry/schema/chemistry_schema.yaml`.
4. Update `CHANGELOG.md`.

## Style
- Use `snake_case` keys.
- Use short, testable statements in constraints.
- Add `examples` sparingly and keep them unit-checked.
