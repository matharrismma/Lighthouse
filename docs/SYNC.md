# Keeping GitHub in sync — and never rewriting `main` again

Two problems bit this repo:

1. **Drift** — the live site / desktop ran weeks ahead of GitHub, so the
   public repo (and anyone reading it, human or agent) saw stale code.
2. **History rewrite** — a manual push replaced `main`'s history instead of
   building on top of it, orphaning the previous commit line. The *content*
   survived, but the old commits became unreachable.

This is the system that prevents both. Layers 1–2 are the real fix (they make
the mistakes structurally impossible); layers 3–4 are day-to-day guardrails.

---

## 1. Make GitHub the source of truth for deploys (kills drift)

Right now the live site is deployed from the desktop, so "live" can run ahead
of GitHub. Flip it: deploy Railway **from GitHub `main`**. Then the only way to
change the live site is to push to `main` first — drift becomes impossible.

In the Railway dashboard:

1. Open the Concordance service → **Settings** → **Source**.
2. Connect the GitHub repo `matharrismma/Lighthouse`, branch **`main`**.
3. Enable **auto-deploy on push**.

`railway.toml` and `Dockerfile` in this repo already describe the build, so no
build changes are needed — Railway just needs to pull from `main` instead of
receiving a local push.

After this, the deploy flow is: **push to `main` → Railway redeploys.** The
repo can never be behind what's live again.

---

## 2. Protect `main` on GitHub (blocks force / history rewrite)

Turn on branch protection so a bad push is rejected by the server, not just by
a local hook:

1. GitHub → repo **Settings** → **Branches** → **Add branch ruleset** (or
   "Add rule") for `main`.
2. Enable:
   - **Restrict deletions**
   - **Block force pushes**
   - *(recommended)* **Require a pull request before merging**
   - *(recommended)* **Require status checks to pass** → select `test` / `lint`
     once CI is green.

With "Block force pushes" on, the exact rewrite that orphaned `main` is refused
by GitHub itself.

---

## 3. Local pre-push guard (defense in depth on the desktop)

A hook that refuses any non-fast-forward or delete push to `main`/`master`
before it ever leaves your machine. Install once, from the repo root:

```powershell
git config core.hooksPath scripts/hooks
```

That's it — `scripts/hooks/pre-push` is versioned in the repo. From then on a
history-rewriting push to `main` is blocked locally with an explanation. To
deliberately override (rare), use `git push --no-verify`.

---

## 4. The everyday command: `scripts/sync.ps1`

Stop doing manual `add` / `commit` / `push`. Use the script — it fetches,
commits local work, rebases so local and remote can't diverge, and does a
plain fast-forward push:

```powershell
./scripts/sync.ps1
# or with a message
./scripts/sync.ps1 -Message "wire up new verifier"
```

It also activates the pre-push guard automatically if it isn't already on.

---

## Quick reference

| Goal | Do this |
|---|---|
| Never be behind live again | Deploy Railway from `main` (§1) |
| Server refuses bad pushes | Branch protection on `main` (§2) |
| Machine refuses bad pushes | `git config core.hooksPath scripts/hooks` (§3) |
| Routine sync | `./scripts/sync.ps1` (§4) |
