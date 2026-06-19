# Agent discoverability — listing the engine where agents look

**Status: DRAFT for review. Nothing here has been submitted anywhere.** These are the
artifacts to get the Concordance MCP server discoverable by agents. Matt approves (and
makes the namespace/wording calls) before anything goes outward.

The engine already *works* over MCP — `https://narrowhighway.com/mcp` (streamable HTTP)
and `/mcp/sse`. This is only about agents *finding* it.

---

## 1. Self-hosted discovery — DONE (on our own domain, nothing external)

A discovery doc now serves at the conventional path on our own site:

    GET https://narrowhighway.com/.well-known/mcp.json

Same category as the `llms.txt`, `robots.txt`, and `sitemap.xml` we already serve. Pure
pointers (transports, doctrine, `/mcp-stats`, manifest, the robot conscience) — no counts
to drift. Anything probing `/.well-known/` on our domain now finds the engine.

## 2. The official MCP registry — DRAFT (needs your go + one decision)

`registry.modelcontextprotocol.io` is the canonical index MCP clients/aggregators read.
Publishing is a deliberate, authenticated act (not a silent crawl).

- **Draft entry:** [`discovery/server.json`](server.json)
- **The one decision — the namespace** (proves you own the thing you're publishing):
  - `io.github.matharrismma/concordance` — verified by signing in with the GitHub
    account that owns the repo. Simplest; no DNS needed.
  - `com.narrowhighway/concordance` — verified by a DNS TXT record on narrowhighway.com.
    Cleaner brand, slightly more setup.
  - `server.json` is now set to `io.github.matharrismma/concordance` (the recommended,
    no-DNS default). Change it to `com.narrowhighway/concordance` if you prefer the
    domain brand. **Nothing has been submitted — publishing is your call (it authenticates
    as you and is outward-facing).**
- **How to publish (you run this — it authenticates as you):**
  1. Install the publisher CLI: `mcp-publisher` (per the registry repo's current README —
     confirm the install command, the tooling is young).
  2. `mcp-publisher login github` (or `dns` for the domain namespace).
  3. `mcp-publisher publish ./discovery/server.json`
- **Confirm before running:** the schema URL/date in `server.json` and the exact field
  names — the registry schema is still moving; check it against the registry repo the day
  you publish so we don't submit against a stale schema.
- **Verified ready (2026-06-19):** `server.json` parses, carries all required fields
  ($schema / name / description / version / remotes), and the namespace is the GitHub
  default. The remote URLs were corrected to the CANONICAL trailing-slash form
  (`/mcp/`, `/mcp/sse/`) — the bare `/mcp` 308-redirects, which some registry validators
  and POST clients won't follow. Confirmed live: a proper `initialize` POST to
  `https://narrowhighway.com/mcp/` returns a valid MCP 200 (serverInfo `concordance`,
  protocol 2025-06-18). The artifact is ready for your authenticated `mcp-publisher publish`
  — only your GitHub login + go are missing.

## 3. Community lists — DRAFT (low-stakes PRs, your call)

Curated "awesome" lists are where many people browse for servers. Each is a one-line PR.

Proposed line (adjust category to each list's taxonomy):

> **[Concordance](https://narrowhighway.com/mcp.html)** — Deterministic verification
> engine. Check a claim or derivation; get a verdict, the worked trail, and a permanent
> re-checkable seal. Verifies, never generates (a false claim returns BROKEN). 146 tools
> across 71 verifier domains + a four-gate decision pipeline.

(Tool count drifts as tools are added — confirm the live number at `GET
https://narrowhighway.com/mcp-stats` the day you open the PR.)

Candidate lists (verify each is active/accepting before opening a PR):
- `punkpeye/awesome-mcp-servers`
- `wong2/awesome-mcp-servers`
- `modelcontextprotocol/servers` (the reference "Community Servers" section)

## 4. ChatGPT / OpenAI-tool agents — already exposed, optional well-known

- `GET /manifest` — OpenAI function-calling manifest (71 verifiers).
- `GET /openapi-actions.json` — curated schema for a ChatGPT Custom GPT Action.
- *Optional:* a `/.well-known/ai-plugin.json` for the (now legacy) plugin convention.
  **Held — it needs a contact email and a logo URL from you; I won't publish your
  personal email.** Say the word and give me a contact + logo and I'll wire it.

---

## What I will NOT do without your explicit go

- Publish to the official registry (it authenticates as you and is public + indexed).
- Open PRs against any external list.
- Put any personal contact info on a public discovery file.

## Honest note on reach

Listings help agents *find* a server; they don't make it good. The reason to be found is
the mission (reach agents, point to Christ), and the doctrine is stated up front in every
surface (`/identity`, the MCP instructions block, this server.json's description) so a
caller knows who the engine serves before the first tool call.
