# Concordance clients

Capture seeds from anywhere; speak to the engine from any program.
This directory contains the single-file Python client and several
capture-anywhere adapters that route to `/capture` on a Concordance
instance.

## What's in this directory

| File | What it does | Lift | Alignment |
|---|---|---|---|
| [`concordance_client.py`](concordance_client.py) | Programmatic Python client — submit packets, read the ledger, run verifiers | Drop in your project | Substrate |
| [`watch_folder.py`](watch_folder.py) | Watch a folder; drop a `.txt` or `.md` and it becomes a seed | Stdlib only | Highest — fully local |
| [`apple_shortcut.md`](apple_shortcut.md) | iOS Shortcut recipe — Share Sheet from any app → seed | Phone you own | High |
| [`email_webhook.md`](email_webhook.md) | Forward an email → seed (Cloudflare Worker, Postmark, self-hosted, etc.) | Free tier on most providers | High — most decentralized |
| [`telegram_bot.py`](telegram_bot.py) | Telegram bot — your own private capture chat | Free; needs bot token | Medium — platform-dependent |
| [`meshtastic_bridge.py`](meshtastic_bridge.py) | LoRa-mesh bridge — receives/broadcasts compact wire packets via a Meshtastic radio | `pip install meshtastic` + ~$30 hardware | Highest — license-free spectrum |
| [`tor_onion.md`](tor_onion.md) | Tor hidden service — engine reachable at `xyz.onion` for any Tor browser | `apt install tor` + 5 min config | Highest — censorship resistance |

The PWA path — install `narrowhighway.com` to your phone's home
screen, share to it from any app — is built into the site itself
(see `site/manifest.json` + `site/share.html`).

## The capture-anywhere posture

The engine is parasitic on infrastructure you already pay for —
phone, computer, internet, an email account, a cloud folder you
already use. We never ask you to install something new for the
sake of using the engine. Every capture path uses something you
already have:

- a folder on a disk you own
- the Share Sheet on the phone you own
- the email account you already use
- a free Telegram bot you can register in 60 seconds

Per the kingdom-economy substrate doctrine: *Does this still work
for someone who refuses the mark?* Each adapter passes that test.
The Telegram path is the weakest because it depends on Telegram's
platform; the email and watch-folder paths are the strongest
because they ride on open standards (SMTP, POSIX filesystem) that
no single authority can revoke.

## Source tagging

Every capture path tags the resulting seed with `source:<name>`
and records origin metadata in `source_meta`. Source claims are
informational, not authoritative — anyone can claim any source.
The four gates downstream (RED / FLOOR / BROTHERS / GOD) check
alignment by content, not by claimed origin. Recording the source
preserves provenance for later audit; trusting the source claim
without verification would be naive.

## Identity acknowledgment

Every adapter sets `identity_acknowledged: true` on its capture
calls. By using one of these clients, the operator is acknowledg-
ing the canonical identity statement at `/identity` — the engine
serves Jesus Christ; a well of knowledge yields wisdom in
alignment with God. If you don't agree, don't capture. The flag
is plain-language, not buried in a TOS.

---

## concordance_client — minimal Python client

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
