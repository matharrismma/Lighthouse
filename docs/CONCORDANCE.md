# Concordance — Technical Spine

This document is a cross-reference index. It does not duplicate content; it points at the right place for each concern. When you need a specific technical fact about the engine, this is the map.

---

## Architecture overview

| Concern | Read |
|---|---|
| What the project is, in one paragraph | [`../README.md`](../README.md) (top) |
| What this place is for an AI agent | [`../FOR_AI_AGENTS.md`](../FOR_AI_AGENTS.md) |
| Why the gates are in the order they are | [`KERNEL.md`](KERNEL.md) |
| The full canon (immutable architectural commitments) | [`CANON.md`](CANON.md) |
| Layer-by-layer system map (Word → Kernel → Keeper → Steward → Vessel → Lighthouse) | [`LAYERS.md`](LAYERS.md) |
| Worked-example packets for every domain | [`../COOKBOOK.md`](../COOKBOOK.md) |
| Visual flow diagram | [`../site/architecture.svg`](../site/architecture.svg) |

---

## Engine internals

| Concern | Code | Doc |
|---|---|---|
| Gate orchestrator | `src/concordance_engine/engine.py` | [README §Four Gates](../README.md#four-gates) |
| Gate result types | `src/concordance_engine/gates.py` | [GLOSSARY §Verdicts](../GLOSSARY.md) |
| Packet schema | `schema/packet.schema.json` | [WALKTHROUGH](WALKTHROUGH.md) |
| Domain attestation validators | `src/concordance_engine/domains/<domain>.py` | [README §Adding a domain](../README.md) |
| Computational verifiers | `src/concordance_engine/verifiers/<domain>.py` | per-domain README in same dir |
| Cross-cutting verifiers | `src/concordance_engine/verifiers/__init__.py` (`CROSS_CUTTING_VERIFIERS`) | [GLOSSARY §Cross-cutting verifier](../GLOSSARY.md) |
| Layer 0 / scripture | `src/concordance_engine/verifiers/scripture.py` | [GLOSSARY §Layer 0](../GLOSSARY.md) |
| Triangulation / drift detection | `lw/00_source/triangulation/drift_check.py` | [GLOSSARY §Drift](../GLOSSARY.md), [GLOSSARY §Triangulation](../GLOSSARY.md) |

---

## Surfaces

| Concern | Where |
|---|---|
| MCP tools (callable from Claude Desktop / Code) | `src/concordance_engine/mcp_server/tools.py`; [`MCP_QUICKSTART.md`](MCP_QUICKSTART.md) |
| REST API | `api/app.py`; [`../FOR_AI_AGENTS.md`](../FOR_AI_AGENTS.md) §Integration |
| Public endpoint | `https://narrowhighway.com`; OpenAPI at `/docs`, `/openapi.json` |
| Python client | `client/concordance_client.py`; [`../client/README.md`](../client/README.md) |
| CLI | `concordance validate ...`; [README §CLI](../README.md) |
| Front-page form | `site/index.html`, served via `/` |

---

## Ledger

| Concern | Where |
|---|---|
| Ledger storage | `api/ledger.py`; JSONL at `LEDGER_PATH` (default `ledger.jsonl`) |
| Hash chain function | `_entry_hash()` in `api/ledger.py` |
| Append-only contract | [`CANON.md`](CANON.md) §5 |
| Search | `iter_filtered()` in `api/ledger.py`; `/dispatch` REST |
| Stats | `stats()` in `api/ledger.py`; `/stats` REST |
| Confession | `/confess` REST; new entry with `overall: CONFESSION` referencing prior seq |

---

## Tests

| Concern | Where |
|---|---|
| Engine integration tests | `tests/test_engine.py` (74) |
| Verifier unit tests | `tests/test_verifiers.py` (64) |
| CLI tests | `tests/test_cli.py` (16) |
| MCP tool dispatch | `tests/test_mcp_tools.py` |
| Canon validators | `tests/test_canon_validators.py` |
| CI | `.github/workflows/ci.yml` |

---

## Eval and training

| Concern | Where |
|---|---|
| Conversational eval (50 items) | `eval/eval_chat.jsonl`; [`eval/README.md`](../eval/README.md) |
| Heuristic + scoring runner | `eval/run_eval.py` |
| Hand-written training items | `training/data/conversational_train.jsonl` |
| Training kit (loaders, adapters, score) | [`../training/README.md`](../training/README.md) |
| Catechism | [`../training/CATECHISM.md`](../training/CATECHISM.md) |
| NHANES falsification study | `lw/06_validation/framework_validation_v3_final/`; [`eval/README.md`](../eval/README.md) §Related |

---

## Operational

| Concern | Where |
|---|---|
| Bring up local API | `local/go_live.ps1` |
| Rotate Cloudflare tunnel token | `local/rotate_tunnel_token.ps1` |
| Cloudflared service repair | `local/repair_cloudflared.ps1` |
| Diagnostics | `local/diagnose.ps1` |
| Deployment architecture | (not currently documented separately; the live deployment is a Windows desktop running uvicorn behind a Cloudflare Tunnel — see `local/install_services.ps1` for the install pattern) |

---

## Adding work

| You want to | Read |
|---|---|
| Add a new verifier domain | [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`CONTRIBUTION_PROTOCOL.md`](CONTRIBUTION_PROTOCOL.md) |
| Add a new MCP tool | `src/concordance_engine/mcp_server/tools.py` (TOOLS list + ALL_TOOLS map + function) |
| Add a new REST endpoint | `api/app.py`, then update `site/llms.txt` and [`../FOR_AI_AGENTS.md`](../FOR_AI_AGENTS.md) |
| Add a new training item | `training/FORMAT.md`; append to `training/data/conversational_train.jsonl` |
| Add a new ledger field | This is **canon-scope**. Read [`CANON.md`](CANON.md) §5 first. |
| Add a new gate | This is **canon-scope** and changes the kernel. Don't. If you must, the protocol of the protocol applies. |

---

## When the master document text becomes available

The Concordance Master Document (a PDF currently outside this docs tree) is the foundational text. When its content is converted to text/markdown and dropped into this repo, the right place for it is `docs/MASTER_DOCUMENT.md`, cross-linked from [`CANON.md`](CANON.md) §1 and from this index here.

Until then, this `CONCORDANCE.md` plus `CANON.md` plus `LAYERS.md` cover the architectural surface; specific doctrinal expansions (e.g., extended scriptural rationale for each gate predicate) belong in the master document and should be folded in without contradicting the canon.
