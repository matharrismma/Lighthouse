# Deploying Narrow Highway

How code becomes live on narrowhighway.com. Written as a handoff runbook.
Facts established by inspection are marked ✅; things the operator must
confirm are marked ⚠️ CONFIRM.

---

## 1. Topology — what runs where

- **Origin:** a Hetzner server. ✅ DNS `A narrowhighway.com → 5.78.186.55`
  (Hetzner range). The box is up.
- **App:** the FastAPI app in `api/app.py`, served by **uvicorn** (see
  `Dockerfile` CMD: `uvicorn api.app:app --host 0.0.0.0 --port 8000`). It also
  serves the static `site/` files and mounts the MCP server at `/mcp`.
- **Data:** persistent state lives under a mounted volume (`/data` in the
  Dockerfile: `LEDGER_PATH`, `CASE_STORE_PATH`), plus repo-relative
  `data/` (contributors, activity, visits, almanac, trust_index). ⚠️ CONFIRM
  where each actually persists on the box — **deploys must not wipe it.**
- **Not in the path:** ✅ **No Cloudflare** proxy (no `cf-ray`; DNS points
  straight at Hetzner). `railway.toml` exists but the live origin is Hetzner,
  so Railway is **not** the production path — treat `railway.toml` as
  vestigial unless the operator says otherwise.

---

## 2. How a change goes live

The deploy trigger is **push to `main`**. The operator confirmed "you've
deployed dozens of times from here," i.e. pushing to GitHub `main` is what
ships. Concretely:

1. Merge the change to `main` (via PR) or push to `main`.
2. The Hetzner box takes the new `main` and restarts the app.

⚠️ **CONFIRM the mechanism of step 2** — this is the single most important
unknown. It is one of:
- **Auto (webhook / CI):** a GitHub webhook or a poller on the box runs
  `git pull` + rebuild/restart on push to `main`. If so, nothing else is
  needed; give it a minute.
- **Manual:** the operator SSHes in and pulls. If so, the deploy step is §3.

Goal state: make it auto so "push = deploy" (see §7).

---

## 3. The deploy step on the box (if manual)

⚠️ CONFIRM whether the box runs the app under **Docker** or **bare
uvicorn/systemd**, then use the matching path.

**Docker (matches the repo's `Dockerfile`):**
```bash
cd /path/to/Lighthouse
git pull origin main
docker compose build && docker compose up -d      # or: docker build + docker run
```

**Bare uvicorn under systemd:**
```bash
cd /path/to/Lighthouse
git pull origin main
pip install -e ".[mcp]"        # only if dependencies changed
sudo systemctl restart <service-name>              # e.g. concordance / narrowhighway
```

Preserve `/data` and the repo `data/` directory across either path.

---

## 4. Verify the deploy landed

Run these against the live host after deploying:

1. **Version / health:** `GET /version` and `GET /health/lite` respond 200.
2. **Functional proof (best signal):** verify the claim `0.1 + 0.2 == 0.3`.
   - Old code returns **BROKEN** (IEEE-754 residue).
   - Current `main` returns **HOLDS** (the float-tolerance fix).
   A HOLDS here proves the running code is at least merge `86fe33c`.
3. **New surface:** `GET /community/first-fruits` returns JSON;
   `/first-fruits.html` renders.

On the box itself, `git log --oneline -1` should show the deployed commit.

---

## 5. Rollback

`main` deploys, so rolling back = putting the previous good commit on `main`
and redeploying:
```bash
git revert <bad-merge-sha>      # e.g. revert the merge commit, keeps history
git push origin main            # redeploys
```
Do **not** force-push `main` to roll back — that is the history-rewrite that
already bit this repo once (see `docs/SYNC.md`).

---

## 6. Domains and the host allowlist

The operator holds **narrowhighway.com**, **.org**, and **.tv**.

⚠️ **The blocker to know about:** the origin rejects unknown hostnames with
`403 — "Host not in allowlist"` (header `x-deny-reason: host_not_allowed`).
This allowlist lives in the box's reverse proxy / app front (it is **not** in
this repo). To serve **any** new hostname, it must be **added to that
allowlist** — otherwise `.org` / `.tv` will 403 even after DNS is pointed.

Recommended role split (matches the two-plane model in
`docs/SEALED_CONVERSATION.md`):

| Domain | Role |
|---|---|
| `.com` | the shepherd — the app, the private conversation |
| `.org` | the public/community plane — the keeping, First Fruits, the ledger, docs |
| `.tv` | the voice/media surface — spoken teachings, audiobooks, episodes |

For now: point all three at `5.78.186.55`, add them to the host allowlist,
and redirect `.org`/`.tv` → `.com` until distinct surfaces are built. The app
already routes by `Host`, so splitting them later is a config change, not a
rebuild.

---

## 7. Cloudflare decision (do this deliberately)

Cloudflare is **not** currently in front. Before adding it, note the tension
with the no-tracking design (`docs/SEALED_CONVERSATION.md` §4): **a Cloudflare
proxy terminates TLS and sees all plaintext**, making it a third party inside
the trust boundary.

Recommendation:
- **DNS-only Cloudflare** (grey cloud) for the private app/sync path — CF as
  registrar/DNS only, TLS terminates on the Hetzner box (Caddy / Let's
  Encrypt). No outside party in the conversation path.
- Reserve any CF **proxy** (orange cloud) for a purely public marketing
  surface, never the shepherd/sync path.

---

## 8. Make "push = deploy" (close the loop)

To stop drift and manual steps, wire one of:
- **GitHub webhook → box:** a small endpoint/daemon on the box that, on push
  to `main`, runs `git pull` + rebuild/restart. Simplest.
- **GitHub Actions → SSH deploy:** an Actions job on push to `main` that SSHes
  to the box and runs the §3 commands (deploy key in Actions secrets).
- **systemd path unit / poller:** the box polls `origin/main` and redeploys on
  change.

Pair with branch protection on `main` (block force pushes) so a bad push can't
rewrite history (`docs/SYNC.md` §2–3).

---

## 9. Secrets & env (never commit)

The app reads keys from a `.env` on the box (gitignored): e.g.
`ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, plus
`LEDGER_PATH` / `CASE_STORE_PATH` / `CONCORDANCE_SCHEMA_PATH`. Keep these on
the box only; never place secret **values** in this repo, in CI logs, or in a
chat. Rotate anything that has been exposed.

---

## 10. Exposing the engine to AI clients — Claude connector + custom GPT

**Goal:** anyone can reach the engine's tools from Claude (a custom connector)
and from a custom GPT (Actions), without installing anything. The app already
serves both surfaces; the blocker is deploy/edge config, not code.

**Claude custom connector (MCP).** ✅ Already mounted:
- Streamable HTTP (recommended): `https://narrowhighway.com/mcp/`
- SSE (older clients): `https://narrowhighway.com/mcp/sse/`
- Discovery: `https://narrowhighway.com/.well-known/mcp.json`
- Add in Claude: **Settings → Connectors → Add custom connector → paste the
  `/mcp/` URL.** In Claude Code: `claude mcp add --transport http concordance
  https://narrowhighway.com/mcp/`.
- The app's FastMCP `allowed_hosts` already lists `narrowhighway.com`
  (`api/app.py`). The remaining blocker is the **edge host allowlist** (§6):
  until the connector's host is admitted, external clients get
  `403 host_not_allowed`. Local stdio (`concordance-mcp`) works today and
  bypasses the edge entirely.

**Custom GPT (OpenAI Actions).** GPTs don't speak MCP — they consume an
**OpenAPI schema**:
- FastAPI auto-generates it at `https://narrowhighway.com/openapi.json`
  (`/docs` for the human view). The site also advertises `/manifest` as an
  OpenAI-compatible tool list.
- In the GPT builder: **Configure → Actions → Import from URL →
  `https://narrowhighway.com/openapi.json`.**
- Same prerequisites as the connector: reachable host (past the allowlist),
  valid TLS.

**Prerequisites for both (deploy checklist):**
1. Host is in the edge allowlist (§6) so the endpoint doesn't 403.
2. Valid public TLS on the serving host.
3. Endpoints reachable: `/mcp/` and `/openapi.json` return 200 to an outside
   client.

**Identity note (for later, not launch):** both surfaces are currently
anonymous — every caller looks the same to the server, so there is no
per-user thread. For the "one conversation across devices" story
(`docs/SEALED_CONVERSATION.md`), the connector/GPT would need **OAuth (or a
per-user key)** mapping the authenticated principal to an identity. Ship the
anonymous tool access first; add auth-to-identity when the sealed-conversation
layer lands.

---

## Open items for the operator / CI chat to confirm

1. ⚠️ Deploy mechanism on the Hetzner box: auto (webhook/poller) or manual?
2. ⚠️ Runtime: Docker (per `Dockerfile`) or bare uvicorn + systemd? Service name?
3. ⚠️ Where the host allowlist is configured (reverse proxy? app front?) — to
   add `.org` / `.tv`, **and to admit the connector/GPT host so `/mcp/` and
   `/openapi.json` stop returning 403.**
4. ⚠️ Where persistent `data/` + `/data` live, to guarantee deploys don't wipe
   the ledger/contributors.
5. ⚠️ Connector + GPT: decide when to add OAuth-to-identity (needed for
   per-user threads; not needed for anonymous tool access).
