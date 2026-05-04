# Operator's guide

Running your own Concordance / Narrow Highway instance. One reading
covers every substrate channel, configuration knob, and persistence
concern. Read top-to-bottom once; come back to a section when you
need it.

This document is for *operators* — humans deploying instances. End
users (people writing seeds) need only the URL of your instance;
they don't need to read this. AI agents discover via `/identity` +
`/llms.txt` automatically.

---

## What an operator is doing

You're running a piece of substrate that:

- Holds a journal (private, your community's seeds)
- Surfaces sealed precedents (the well — public, drawn from)
- Shows what's been kept while you were away (the dawn surface)
- Routes captured seeds from many sources (web, email, NFC, LoRa)
- Optionally federates with peer instances

Per the kingdom-economy substrate doctrine: this works for someone
who refuses the mark. Every substrate channel uses tools that are
free or already paid for. Nothing requires a payment processor in
the path.

---

## Quick start

```bash
# Clone or pip-install
git clone https://github.com/matharrismma/Lighthouse.git
cd Lighthouse
pip install -e .[mcp,signing]   # signing extra needed for witness sigs

# Bring up the API (port 8000 by default)
uvicorn api.app:app --host 127.0.0.1 --port 8000

# In another shell, sanity-check
curl http://localhost:8000/identity | jq .short
curl http://localhost:8000/health  | jq .overall_status
curl http://localhost:8000/setup.html      # operator dashboard

# Plant a seed
curl -X POST http://localhost:8000/journal/write \
  -H "Content-Type: application/json" \
  -d '{"text":"Mt 5:37 — let your yes be yes","identity_acknowledged":true}'
```

Static site (the `/site/` folder) is served directly by the FastAPI
app. The browser-side journal is at `http://localhost:8000/`.

---

## Configuration (environment variables)

Operator-facing knobs read at startup. None are required; defaults
work for local development.

### Substrate addresses (surface as operator-configured at /reach + /setup)

```
CONCORDANCE_TOR_ONION         — public .onion URL for this engine
CONCORDANCE_EMAIL_INBOUND     — inbound capture address (e.g. seed@host)
CONCORDANCE_TELEGRAM_HANDLE   — capture bot @username
CONCORDANCE_LORA_FREQ         — LoRa frequency band (915MHz / 868MHz)
CONCORDANCE_NOSTR_NPUB        — Nostr public key (npub1...)
CONCORDANCE_IPFS_GATEWAY      — preferred IPFS gateway URL
CONCORDANCE_MAILING_LIST      — mailing-list subscribe address
CONCORDANCE_FETCH_REMOTE      — upstream engine to fetch from
```

These are addresses, not secrets. They surface publicly via
`GET /reach` so visitors know how to reach your instance through
alternative substrates. Set whichever channels you've actually
wired up; the rest stay generic in the public listing.

### Capability secrets (never exposed)

```
ELEVENLABS_API_KEY            — TTS (POST /speak)
ELEVENLABS_VOICE_ID           — TTS voice id
```

The `/reach` endpoint reports `speak_voice: true` when both are
present, without exposing the key.

### Storage paths

```
CONCORDANCE_DATA_DIR          — base dir for journal/keeping/fetched
                                (defaults to ~/.concordance)
CONCORDANCE_LEDGER_DIR        — primary precedent corpus
                                (defaults to <repo>/lw/ledger)
CONCORDANCE_PRECEDENT_DIRS    — extra dirs (os.pathsep separated)
                                searched alongside primary
CONCORDANCE_WITNESS_DIR       — witness attestations storage
                                (defaults to ~/.concordance/witness)
CONCORDANCE_HOST              — base URL emitted by `concordance qr`
CONCORDANCE_FETCH_REMOTE      — default for `concordance fetch`
```

For microSD-portable deployments per the deployment-modes doctrine,
point `CONCORDANCE_DATA_DIR` at the SD card mount and the entire
substrate (journal + ledger + witness records + fetched precedents)
travels with the card.

---

## Substrate channels (one row per channel)

Each channel has a recipe in `client/`. Wire up the ones your
community needs; ignore the rest.

| Channel | Recipe | Operator action | What users do |
|---|---|---|---|
| **Tor onion service** | [`client/tor_onion.md`](client/tor_onion.md) | install Tor, edit `torrc`, share the `.onion` | Open in Tor Browser |
| **Email-in** | [`client/email_webhook.md`](client/email_webhook.md) | Cloudflare Email Routing → Worker, OR Postmark, OR self-hosted Postfix | Forward email to `seed@yourdomain` |
| **Telegram bot** | [`client/telegram_bot.py`](client/telegram_bot.py) | get bot token from @BotFather, run `python telegram_bot.py --token ... --allow <user_id>` | Send messages to your bot |
| **LoRa mesh** | [`client/meshtastic_bridge.py`](client/meshtastic_bridge.py) | flash Meshtastic firmware on a $30 Heltec board, run `meshtastic_bridge.py --port COMx --bridge` | Carry a Meshtastic device on the same channel |
| **Apple Shortcut** | [`client/apple_shortcut.md`](client/apple_shortcut.md) | publish a Shortcut for distribution (or paste recipe in operator's docs) | iOS Share Sheet |
| **Watch folder** | [`client/watch_folder.py`](client/watch_folder.py) | run `python watch_folder.py --dir ~/concordance-inbox --bridge` | Drop `.txt` / `.md` files |
| **PWA + Web Share Target** | already wired | (no setup needed; site/manifest.json handles it) | "Add to Home Screen" + Share to Concordance |
| **NFC** | already wired | (no setup needed; `/nfc.html` works on Android) | Tap a writable NFC tag |
| **Nostr publication** | [`client/nostr_publish.py`](client/nostr_publish.py) | `pip install pynostr`, run `nostr_publish.py keygen` once, then `nostr_publish.py sync --nsec ...` periodically | Subscribe in any Nostr client |
| **IPFS pinning** | [`client/ipfs_pin.py`](client/ipfs_pin.py) | install kubo, run `ipfs daemon`, then `ipfs_pin.py sync` periodically | Fetch content by CID via any IPFS gateway |
| **Mailing list digest** | [`client/digest_mail.py`](client/digest_mail.py) | configure SMTP, list of subscribers, schedule via cron | Receive email digests |
| **QR / paper** | [`client/qr_share.md`](client/qr_share.md) | use `concordance qr <id>` + any QR generator (`qrencode`, `segno`, phone QR app) | Scan with phone camera |

The dashboard at `/setup.html` shows live ✓/○ status per row plus
links to each recipe.

---

## Federation (pull and push)

Two engines federate by exchanging audit-chain entries. Neither
merges into the other's chain — both store mirrors tagged with the
remote's URL.

### Pull (`concordance fetch`)

You pull from a peer:

```bash
concordance fetch --remote https://peer.example
concordance fetch --status                    # per-remote last_seq + age
concordance fetch --list --remote https://peer.example --limit 10
```

Idempotent (only entries past your last-seen seq are fetched).
Offline-tolerant (unreachable remote returns `status: offline`,
no error). Stored at `<DATA_DIR>/fetched/<slug>.jsonl`.

### Push (`concordance push`)

You push to a peer:

```bash
concordance push --remote https://peer.example
concordance push --remote https://peer.example --from-url https://my-instance.com
```

Sends our locally-sealed precedents to the peer's
`POST /chain/receive` endpoint. Same storage shape on their side
as a pull would produce.

### Receiving pushes

Your instance accepts pushes at `POST /chain/receive` automatically.
No configuration needed beyond your engine running. Senders are
identified by their `from` URL; storage is per-sender at
`<DATA_DIR>/fetched/<slug>.jsonl`.

### Closest-case across the federated corpus

When users write seeds, the closest-case overlay searches:

1. The primary ledger directory (your own)
2. Each path in `CONCORDANCE_PRECEDENT_DIRS`
3. `<DATA_DIR>/fetched_precedents/`

Local seals take precedence on `precedent_id` collision. Fetched
precedents are reference, not authority.

To make federation feed wisdom: copy peer-curated precedent JSONs
into `fetched_precedents/`. Future tooling can do this automatically
via the federation channels.

---

## Witness keys

Ed25519 attestations on sealed precedents — the BROTHERS gate's
required-by-name witnesses gain cryptographic teeth.

### One-time: each witness generates a keypair

```bash
concordance sign keypair > my-witness.key
# my-witness.key contains both private + public; share only the public.
```

Or programmatically:

```python
from concordance_engine import signing
priv, pub = signing.generate_keypair()
# Store priv securely; share pub with the operator.
```

### Operator: distribute pubkeys + collect signatures

For each precedent that needs witness signatures:

```bash
# Witness signs (locally — private key never leaves their machine)
concordance witness sign \
    "ledger://decision/2024-11-08/admit-member-007" \
    "<entry_hash>" \
    --name "Alice" --role "elder" \
    --key /path/to/my-witness.key \
    --append \
    > attestation.json

# Operator collects each witness's attestation.json into the
# CONCORDANCE_WITNESS_DIR (or the witness uses --append to write
# directly).
```

Anyone reading the well sees attestations under "carry the witness"
on each precedent, with verify status (✓ / ✗) per witness. Tampered
attestations show `verify_reason` in red.

```bash
# Verify any attestation file from anywhere
concordance witness verify --file attestation.json

# List all attestations on file for a precedent
concordance witness list "ledger://decision/2024-11-08/admit-member-007"
```

---

## Persistence + backup

Things to back up regularly:

| Path | What | Restore impact if lost |
|---|---|---|
| `<DATA_DIR>/journal/` | User seeds (the journal layer) | seeds gone forever |
| `<DATA_DIR>/keeping/` | Keeping log (continuous body-practice observations) | lose dawn-surface signal |
| `<DATA_DIR>/witness/` | Ed25519 attestations | precedents lose verifiable proof |
| `<DATA_DIR>/fetched/` | Pulled / received entries from peers | re-fetchable |
| `<DATA_DIR>/fetched_precedents/` | Peer-curated precedent corpus | re-distributable |
| `api/ledger.jsonl` | This instance's audit chain (sealed precedents log) | local seals lost |
| `lw/ledger/` | Static reference precedents | re-distributable from repo |
| `.env` | Configuration (NOT secrets to back up online) | reconfigure |

Per the deployment-modes doctrine, the practical pattern: keep
`<DATA_DIR>` on a microSD or removable drive. Daily snapshot is
small (a few MB unless you have thousands of seeds). The whole
substrate of one community fits in well under 1 GB.

For Restricted / Lockdown modes, the SD card travels with you. Plug
into another machine, point `CONCORDANCE_DATA_DIR` at it, the
substrate runs.

---

## Operating modes (per deployment-modes doctrine)

Same code, different operational stance:

### Open mode (default)

API publicly reachable; clearnet domain (`narrowhighway.com`)
serves the journal page. Federate with willing peers via fetch +
push. This is what `pip install concordance-engine && uvicorn
api.app:app` gives you.

### Restricted mode

When clearnet becomes hostile:

- Bind API to `127.0.0.1` only: `uvicorn api.app:app --host 127.0.0.1`
- Expose only via Tor onion service (see `client/tor_onion.md`)
- `CONCORDANCE_TOR_ONION` set to your `.onion` so reach.html shows it
- Email-in / Telegram bot continue to work if those platforms
  remain reachable for your community
- LoRa mesh becomes the primary federation channel for nearby
  communities

### Lockdown mode

Network entirely hostile or absent:

- Engine on a Raspberry Pi or laptop with `<DATA_DIR>` on microSD
- LoRa-mesh radio for community-to-community substrate sync
- Sneakernet (physical SD swap) for cross-region precedent sharing
- QR codes printed on paper for trans-physical distribution
- Witness signatures sealed using offline keys

The same engine code runs in all three modes. The transition is
operational, not architectural.

---

## Adding a new domain verifier

If you want to extend the engine with a new verification axis:

1. Write `src/concordance_engine/verifiers/<name>.py` per the pattern
   in `electrical.py` or `energy.py`. Required: `run(packet)` returning
   `List[VerifierResult]`. Each check returns `confirm` / `mismatch`
   / `error` / `na`.
2. Register in `src/concordance_engine/verifiers/__init__.py` —
   add to the `VERIFIERS` dict; aliases optional.
3. Add to `src/concordance_engine/grid.py` — pick the dimensions
   the axis sits on (encoding / metabolism / reasoning /
   physical_substance / authority_trust / time_sequence /
   conservation_balance).
4. (Optional) Expose as MCP tool in
   `src/concordance_engine/mcp_server/{tools,server}.py`.
5. Tests in `tests/test_<name>.py`.

The grid-sync test (`test_every_verifier_has_a_grid_entry`) catches
omissions automatically.

See [`docs/ADDING_DOMAINS.md`](docs/ADDING_DOMAINS.md) (if present)
for the discovery-not-design discipline — natural axes emerge from
data, not a target count.

---

## When something breaks

- **Engine won't start**: check `python -c "import concordance_engine; print(concordance_engine.__version__)"`. Should print 1.2.0+.
- **Tests fail**: `python -m pytest tests/ -q`. Should be 1303+ green.
- **Verifier reports ERROR**: see the `data` field of the result; it has the inputs the verifier saw.
- **`/health` shows degraded**: a module is unreachable. Check logs.
- **Federation pull returns offline**: peer is genuinely unreachable. No-op. Try later.
- **Witness verify fails on a known-good attestation**: check `cryptography` is installed. Run `pip install cryptography`.

---

## Per the doctrine

Read [`/identity`](https://narrowhighway.com/identity) before doing
anything operator-shaped. The engine serves Jesus Christ; we steward
the substrate, we don't author wisdom. Every architectural decision
passes the test: *does this still work for someone who refuses the
mark?*

For deeper context, the project memory at
`~/.claude/projects/.../memory/MEMORY.md` indexes the doctrinal
decisions captured during build (kingdom-economy substrate, wise
serpents + innocent doves, multiplication-not-scaling, free use +
alignment to execute, deployment modes, LoRa wilderness layer,
principal goal — assist in wisdom).

The well is open. The keeping continues.
