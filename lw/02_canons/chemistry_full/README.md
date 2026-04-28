# Concordance Canon — Chemistry (Universal)

A universal, domain-focused **Chemistry Canon** package for the Concordance / Canon architecture.

## What this is
- **Plain-text YAML** system definition for chemistry: frozen nouns, constraints, diagnostics, and operational modules.
- Organized as **RED → FLOOR → WAY → Execution** layers.
- Designed to be **GitHub-friendly** (human-readable) while remaining **machine-ingestible**.

## Package layout
- `chemistry/canon.yaml` — domain entrypoint
- `chemistry/core/chemistry_core.yaml` — domain core: frozen nouns + constraints + diagnostics
- `chemistry/schema/chemistry_schema.yaml` — schema for packets/modules
- `chemistry/templates/` — packet and proof checklists
- `chemistry/modules/` — operational modules by topic (acid-base, redox, separations, etc.)

## How to use
1. Start with `chemistry/canon.yaml`.
2. Use triggers to route a question/problem to the relevant module(s).
3. Validate outputs against:
   - **RED** (non-negotiable constraints)
   - **FLOOR** (minimum scientific hygiene)
   - **WAY** (best-practice methods)
   - **Execution** (calculations, procedures, checks)

## Version
See `CHANGELOG.md`.
