# Contributing

## Ground rules

1. **Validators must be deterministic.** Same packet in, same result out. No clocks (other than the explicit `now_epoch` injected for the GOD gate), no randomness, no environmental reads.
2. **No network calls in core validation.** The engine, domains/, verifiers/, and the MCP tools must run fully offline. Adding a network dependency is an architectural change, not a feature.
3. **Tests for every new rule.** A new validator gate, a new verifier mode, a new MCP tool — each gets at least one passing case and one rejecting case in the existing test scripts.
4. **MCP tools never raise.** On bad input return `{"status": "ERROR", "detail": "..."}` so the LLM tool loop sees a structured failure rather than crashing.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running tests

```bash
PYTHONPATH=src python tests/test_engine.py
PYTHONPATH=src python tests/test_verifiers.py
PYTHONPATH=src python tests/test_cli.py
PYTHONPATH=src python tests/test_mcp_tools.py
PYTHONPATH=src python tests/test_canon_validators.py
```

Or all at once via pytest:

```bash
pytest tests/
```

CI runs the same five suites on Python 3.10, 3.11, and 3.12.

## Lint

```bash
ruff check src/ tests/
```

Ruff config lives in `pyproject.toml`.

## Branch + PR conventions

- Work on a topic branch off `main`.
- One conceptual change per PR. If you find an unrelated bug, file it in `KNOWN_ISSUES.md` rather than bundling.
- Bump the version in `pyproject.toml` and add a CHANGELOG entry as part of the PR that introduces a user-visible change.
- A passing CI matrix is a hard prerequisite for merge.

## Adding a verifier domain

See `src/concordance_engine/verifiers/README.md` for the verifier contract. The short version:
1. Drop `<domain>.py` in `domains/` exposing `validate_red(packet)` and `validate_floor(packet)`.
2. Drop `<domain>.py` in `verifiers/` with a `run(packet)` function returning `list[VerifierResult]`.
3. Register the verifier in `verifiers/__init__.py`.
4. Add the domain to the `enum` in `schema/packet.schema.json`.
5. Add a sample packet to `examples/`, plus tests.
6. Wire an MCP tool in `src/concordance_engine/mcp_server/tools.py` (function-style + descriptor entry in `TOOLS`) and add it to `ALL_TOOLS`.

## Reporting bugs

Open a GitHub issue with:
- A minimal packet or tool-call repro.
- Observed output (`status`, `detail`, `data`).
- Expected output and the rule the engine should have applied.

The `KNOWN_ISSUES.md` file at the repo root tracks anything reproducible that doesn't yet have a fix in flight.
