# Tor onion service — censorship-resistant access

Wrap any Concordance instance in a Tor hidden service. The engine
becomes reachable at a `xyz.onion` address that survives DNS
hijacking, ISP blocks, geo-fencing, and platform deplatforming.

Per the kingdom-economy substrate doctrine: works for someone who
refuses the mark even when the conventional internet's name resolution
turns hostile. Tor's network is a public good; running a hidden
service costs nothing beyond the operator's own bandwidth.

Per the wise-serpent + innocent-dove posture: Tor is mature, well-
documented, open-source. We use it as it's intended; nothing covert.

## What this gives you

- A stable `.onion` URL pointing to your Concordance instance
- Anyone with Tor Browser can reach it at that URL with no DNS
- The address survives any centralized takedown — it's a hash of
  a public key, generated on first run
- End-to-end encryption between the visitor and your engine
- No exit node sees the traffic (onion services are .onion-internal)

## What this does NOT give you

- Faster access — Tor adds latency (3-hop circuit)
- Anonymity for *operators* by default — you still have to harden
  your hosting environment if that matters (separate concern)
- Protection against application-layer attacks — the four gates
  still do that

## Setup (one-time, ~5 minutes)

### 1. Install Tor

Pick whichever fits your platform:

- **Debian/Ubuntu:** `sudo apt install tor`
- **macOS:** `brew install tor`
- **Windows:** download from [torproject.org](https://www.torproject.org/download/tor/)
- **Docker:** `docker run -d --name tor -v tor-data:/var/lib/tor osminogin/tor-simple`

### 2. Configure the hidden service

Edit `/etc/tor/torrc` (Linux/macOS) or `tor/torrc` in the Windows
installation directory. Add:

```
HiddenServiceDir /var/lib/tor/concordance/
HiddenServicePort 80 127.0.0.1:8000
```

If your Concordance API runs on a different port, change `8000`
to match. Keep the bind address at `127.0.0.1` — Tor reaches in
locally; you do not need to expose the API to the public network.

### 3. Restart Tor

```
sudo systemctl restart tor      # Linux
brew services restart tor       # macOS
```

### 4. Read your onion address

```
sudo cat /var/lib/tor/concordance/hostname
```

Tor will print something like:
```
abc123def456ghi789jkl012mno345pqr678stu901vwx234yz567abcdefghi.onion
```

That's your hidden service. Open Tor Browser, paste it in, and
your Concordance instance loads. Bookmark it.

### 5. Tell agents about it

If you want AI agents to discover the onion address, add a line
to your `site/llms.txt`:

```
Onion mirror: abc123...xyz.onion (requires Tor)
```

## Hardening (recommended)

### Bind the API to localhost only

If you don't want your engine reachable from the open internet at
all — only via Tor — bind it to `127.0.0.1`:

```bash
uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Now the engine is *only* reachable via the onion. Cloudflare /
your domain registrar can't touch this.

### Run a v3 onion (already the default)

Modern Tor uses v3 onion addresses (the long ones above). They're
56 characters, use Ed25519 keys, and are quantum-resistant for
the foreseeable future. v2 onions (16 characters) are deprecated;
do not use them.

### Protect the private key

The HiddenServiceDir contains your onion's private key. It's the
secret that proves "this onion is me." If you lose it, the address
changes. If someone else gets it, they can impersonate your onion.

```bash
sudo chmod 700 /var/lib/tor/concordance/
sudo chown -R debian-tor:debian-tor /var/lib/tor/concordance/   # Debian
```

Back it up to your microSD or other off-grid storage. Per the
kingdom-economy doctrine: this is the kind of secret that should
live on physical media you control, not in the cloud.

## Stable address across restarts

The onion address is derived from the keys in HiddenServiceDir. As
long as that directory persists, your address stays the same. If
you migrate to a new server, copy the directory over and the
address moves with you.

## Vanity addresses (optional)

You can grind for an onion address that starts with a chosen
prefix using `mkp224o`. For Concordance, something like
`concord...onion` is recognizable. Vanity grinding takes minutes
to days depending on the desired prefix length. Not necessary —
the doctrine doesn't require recognizability — but a 4-7 character
recognizable prefix is reasonable.

## Bridges + obfs4 (when Tor itself is blocked)

Some networks block Tor entirely. In that case, configure Tor
bridges using obfs4 transport. Get bridges from
[bridges.torproject.org](https://bridges.torproject.org). Add to
torrc:

```
UseBridges 1
ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy
Bridge obfs4 [bridge_address] [fingerprint] cert=[cert] iat-mode=0
```

This is the wilderness-layer of the wilderness layer — when Tor
itself needs help getting out.

## Connection to the deployment-modes architecture

Per project_deployment_modes.md:

- **Open mode:** Tor onion sits *alongside* the public domain. Both
  reach the same engine; users pick whichever works for them.
- **Restricted mode:** Tor onion may become the *primary* access
  path; public domain is taken down or geo-fenced.
- **Lockdown mode:** Tor itself may be blocked; bridges + obfs4
  become necessary, OR the substrate falls back to LoRa-mesh /
  microSD sneakernet.
- **Quantum:** Tor's Ed25519 v3 onions are durable enough to bridge
  to a post-quantum substrate when one exists.

## What to advertise where

| Channel | What to publish |
|---|---|
| `narrowhighway.com` (clearnet) | Public-friendly entry point |
| `xyz.onion` (Tor) | Censorship-resistant mirror |
| `llms.txt` on both | Doctrine + agent discovery |
| Stickers / business cards | Both URLs side by side |

The onion address is a permanent thing once generated. Print it
on bulletin boards, in book back-covers, on stickers. Survives
any digital adversary.
