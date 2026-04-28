# Concordance Engine — Agent Guide

This file is for AI coding assistants working in this repository.

## What this codebase does

Concordance Engine validates decision packets and computational claims through a four-gate pipeline (RED, FLOOR, BROTHERS, GOD) and exposes the validators as MCP tools. The core claim: O(1) authority-based validation is structurally more efficient than O(n²) consensus-based validation at any scale.

## Architecture

```
src/concordance_engine/
├── engine.py        # gate orchestrator — start here to understand the pipeline
├── gates.py         # GateResult, PacketResult types
├── packet.py        # packet and result dataclasses
├── domains/         # attestation validators per domain (RED/FLOOR flag checking)
├── verifiers/       # computational verifiers per domain (artifact checking)
└── mcp_server/      # MCP server wrapping the verifier tools
```

The engine runs gates in fixed order: RED then FLOOR then BROTHERS then GOD. It halts at the first failure. It never self-confirms.

RED has two independent layers: attestation (did the author affirm constraints?) and verification (does the artifact hold up computationally?). Verification can REJECT despite a passing attestation.

## Key conventions

- Verifiers are in `verifiers/`. Each exposes a `run(packet)` function returning `list[VerifierResult]`.
- Domain validators are in `domains/`. Each exposes `validate_red(packet)` and `validate_floor(packet)`.
- Adding a new domain: drop files in both directories, register the verifier in `verifiers/__init__.py`.
- MCP tools in `mcp_server/tools.py` are plain Python functions. They never raise exceptions. On bad input they return `{"status": "ERROR", "detail": "..."}`.

## Running tests

```bash
PYTHONPATH=src python tests/test_engine.py        # 67 integration tests
PYTHONPATH=src python tests/test_verifiers.py     # 53 verifier unit tests
PYTHONPATH=src python tests/test_mcp_tools.py    # 44 MCP tool tests
PYTHONPATH=src python tests/test_cli.py          # 16 CLI tests
```

All 164 tests should pass before any change is considered complete.

## Running the MCP server

```bash
pip install -e ".[mcp]"
concordance-mcp
```

## CLI

```bash
concordance validate examples/sample_packet_chemistry_verify.json --now-epoch 9999999999
```

## What not to change

- Gate order (RED, FLOOR, BROTHERS, GOD) is fixed. Do not reorder.
- The engine must never self-confirm. BROTHERS and GOD gates exist to enforce human witness and time-wait. Do not short-circuit them.
- MCP tool functions must not raise exceptions. Always return structured error dicts.

## The efficiency claim

O(1) vs O(n²) is the load-bearing technical claim of this system. Any change that introduces participant polling, voting, or consensus aggregation contradicts the architecture. External authority validation means checking against a standard that exists independently of the participants.
