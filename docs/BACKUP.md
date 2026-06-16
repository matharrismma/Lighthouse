# Backups -- the keeping, kept safe

The engine writes state that is **not in git and cannot be rebuilt**. If the droplet is
lost with no backup, that state is gone. This is how we keep it.

## What is at risk

| State | Where | Rebuildable? | Backed up by |
|---|---|---|---|
| Seals / receipts (the "keeping") | `data/cas` | **No** -- runtime-written, content-addressed | this backup |
| Node identity keys + physical token | `~/.concordance` | **No** -- lose them, lose the node's identity | this backup |
| Codex / almanac snapshot | `data/codex`, `data/almanac` | almanac is also in git | this backup (coherent restore point) |
| Layer-0 databases | `lw/00_source` | Yes, but the throttled commentary fetches take **hours** and depend on external sources | this backup (`full` mode, weekly) |
| Cards | `data/cards` | -- | **git** (tracked; off-machine already) |

## How it works

`tools/backup_substrate.sh [substrate|full]` writes a timestamped, `chmod 600` archive to
`~/backups/` on the droplet and rotates to the most recent `NH_BACKUP_KEEP` (default 14).

- `substrate` (default) -- `data/cas` + `~/.concordance` + codex/almanac. Small (~3 MB), **daily**.
- `full` -- the above **plus** `lw/00_source` (~hundreds of MB). **Weekly.**

Installed crons (on the droplet, `crontab -l`):

```
30 4 * * *  .../backup_substrate.sh substrate   # daily 04:30 UTC
30 5 * * 0  .../backup_substrate.sh full         # weekly Sun 05:30 UTC
```

Log: `~/backups/backup.log`.

## The honest limitation -- and the off-site pull

Droplet-local archives protect against **accidental deletion** and give restore points.
They do **NOT** protect against losing the droplet. For true off-site safety, pull the
latest archive somewhere else. The substrate archive contains the node's **private keys**
-- keep it private (never git, never a cloud share without encryption):

```bash
# pull the newest substrate archive to a local, non-synced folder
LATEST=$(ssh nh@nh-engine-1 'ls -1t ~/backups/substrate-*.tar.gz | head -1')
scp "nh@nh-engine-1:$LATEST" ~/nh-backups/
```

A current off-site copy lives at `~/nh-backups/` on the operator's machine (outside the
git repo and outside cloud sync). Re-run the pull periodically, or wire it to a scheduled
job / encrypted object store when one is available.

## Restore

```bash
# inspect
tar -tzf substrate-YYYYMMDD-HHMMSS.tar.gz | head

# restore the keeping + node identity (from the archive root: data/..., .concordance)
tar -xzf substrate-YYYYMMDD-HHMMSS.tar.gz -C ~/Lighthouse data        # data/cas, data/codex, data/almanac
tar -xzf substrate-YYYYMMDD-HHMMSS.tar.gz -C ~       .concordance     # node keys + token (chmod 600 stays)

# restore the Layer-0 databases (from a full-* archive); or rebuild from tools/build_*_index.py
tar -xzf full-YYYYMMDD-HHMMSS.tar.gz -C ~/Lighthouse lw/00_source

# then restart
sudo systemctl restart nh-engine
```
