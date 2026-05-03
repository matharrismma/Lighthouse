# concordance_client — minimal Python client

A single-file sync client for `https://narrowhighway.com` (or any
compatible deployment). One dependency (`requests`) by default, or
zero dependencies if you pass `use_stdlib=True`.

## Install

Copy `concordance_client.py` into your project. That's it. Or:

```bash
pip install requests  # only if you want the requests-backed path
```

## One-minute example

```python
import time
from concordance_client import Concordance

c = Concordance()                                # narrowhighway.com
print(c.about())                                  # {name, version, layer_0_provisioned, ...}

# Build a packet
packet = {
    "domain": "governance",
    "scope": "adapter",
    "created_epoch": int(time.time()) - 60,
    "witness_count": 1,
    "DECISION_PACKET": {
        "title": "Smoke test",
        "decision": "Confirm the engine answers cleanly through the client.",
        "rationale": "First call from a fresh Python environment.",
        "scope": "adapter",
        "red_items": ["No coercion"],
        "floor_items": ["Coherent rationale"],
        "way_path": "Submit through /reflect, then commit if PASS.",
        "execution_steps": ["reflect", "submit"],
        "witnesses": ["smoke-tester"],
        "witness_count": 1,
    },
}

# Rehearse
preview = c.reflect(packet)
print(preview["overall"], "—", preview["elapsed_ms"], "ms")

# Commit only if it passes
if preview["overall"] == "PASS":
    record = c.submit(packet)
    print(f"recorded as ledger seq {record['ledger_seq']}")
```

## Using a private deployment

```python
c = Concordance(base_url="https://your-deployment.example", api_key="lh_...")
c.validate(packet)   # uses X-Api-Key, strict GOD-gate timing
```

## Zero-dependency mode

If `requests` is unavailable in your environment:

```python
c = Concordance(use_stdlib=True)
```

Uses `urllib.request` from the standard library. Same API.

## Surface

Method | Endpoint | Purpose
---|---|---
`reflect(packet)` | `POST /reflect` | rehearse, no ledger write
`submit(packet)` | `POST /submit` | unauth, ledger write, GOD bypassed
`validate(packet)` | `POST /validate` | auth, ledger write, strict GOD
`confess(ref_seq, ...)` | `POST /confess` | acknowledge a prior packet was wrong
`ledger(n, offset)` | `GET /ledger` | newest N entries
`ledger_by_id(packet_id)` | `GET /ledger/{packet_id}` | every entry for a packet
`verify_chain()` | `GET /ledger/verify` | hash-chain integrity
`dispatch(domain, overall, ...)` | `GET /dispatch` | filtered ledger search
`stats()` | `GET /stats` | aggregate counts
`about()` | `GET /about` | service metadata
`scripture(ref)` | `GET /scripture/{ref}` | WEB text for a verse
`strong(num)` | `GET /strong/{num}` | Strong's word study
`triangulate(ref, claim)` | `POST /triangulate` | interpretation drift check
`health()` | `GET /health` | liveness

## License

Apache 2.0 (matches the engine).
