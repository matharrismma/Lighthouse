# Narrow Highway → Odysseus

**A discernment floor for your self-hosted AI.**

Odysseus gives you a sovereign *mouth* — your models, your machine, no big-tech
middleman. Narrow Highway adds a sovereign *floor*: a way to **check what the
mouth says** against something fixed. It's an MCP server; Odysseus speaks MCP;
it drops in.

A local model you can't check is a private hallucination machine. With the
floor, your agent can ask "does this actually hold?" — and get a deterministic,
traceable answer instead of a confident guess.

> **What it is, plainly.** Narrow Highway (the Concordance Engine) **serves Jesus
> Christ.** It is a Christian discernment engine — a conduit, not a source; it
> *eliminates what isn't the answer* so that what survives can be trusted. Full
> statement: <https://narrowhighway.com/identity>. We say so up front — nothing
> here is disguised. The *verification* is useful to anyone; we don't hide what
> it's for, and we don't push it on anyone.

## What your agent gets

- **verify** — does a claim's math close? (171/171 on the engine's own
  benchmark, across 57 domains: physics, chemistry, economics, statistics,
  geometry, nutrition, and more.)
- **the four gates** — weigh a teaching: RED (known by fruit) · FLOOR (the way
  of life, not death) · BROTHERS (two or three witnesses) · GOD (endure) — each
  grounded in Scripture and witnessed by the Didache.
- **scripture** — resolve a reference to the public-domain WEB text; check
  whether one verse genuinely *quotes* another (textual math, not interpretation
  — it declines to rule on "fulfillment," which is a judgment, not a computation).
- **apothecary · almanac · polymathic** — remedies, curated wisdom, and
  many-domain verification of a single claim.

Everything is deterministic and traceable. The point isn't to trust the engine —
it's to be able to read *why* it answered.

## Two ways to connect

### 1 — Fully local (sovereign; recommended for a local-first setup)
Narrow Highway is open and runs on the same stack as Odysseus (FastAPI/Python),
so you can run it yourself and **nothing leaves your machine**:

```bash
git clone https://github.com/matharrismma/Lighthouse
# follow the engine's setup; it serves on http://localhost:8000
```

Then point Odysseus at `http://localhost:8000/mcp`. Local-first, your keys, no
telemetry — same posture as the rest of your Odysseus.

### 2 — Hosted (fastest)
Point Odysseus at the public engine:

```
https://narrowhighway.com/mcp
```

**Honest disclosure:** in hosted mode, the claims your agent sends to these tools
reach our server at `narrowhighway.com` to be verified, and the result comes
back. That request is the one thing that isn't local. There's no account and no
telemetry — we serve the request and that's it. If that crosses your local-first
line, use option 1.

## Adding the MCP server

Odysseus's agent is built on **opencode**, which connects to remote MCP servers
over Streamable HTTP. Depending on your version, add it in **Settings → MCP
management**, or in the opencode config:

```json
{
  "mcp": {
    "narrow-highway": {
      "type": "remote",
      "url": "https://narrowhighway.com/mcp",
      "enabled": true
    }
  }
}
```

Swap the URL for `http://localhost:8000/mcp` if you self-host. Toggle the tools
per-agent like any other MCP server. If your build only accepts local **stdio**
MCP servers, bridge to the URL above with
[`mcp-proxy`](https://github.com/sparfenyuk/mcp-proxy).

## Why the pairing

Own your AI *and* be able to trust it. Odysseus refuses to hand your data to the
cloud; Narrow Highway refuses to confirm what it can't verify. Sovereign mouth,
sovereign floor.

---
*Narrow Highway is a conduit, not a source. Good fruit is the measure.*
*<https://narrowhighway.com> · serves Jesus Christ.*
