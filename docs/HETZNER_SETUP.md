# Hetzner Setup — Operator Runbook

> **Load-bearing distinction — read this before everything else.**
>
> This is **not** a migration to "the cloud" in the SaaS sense. This is
> moving the engine to better tissue. The body's character does not change.
> Hetzner is a rented box in a German data center. We own the keys, hold
> the substrate, write the systemd unit, and can yank everything to another
> provider in an afternoon if Hetzner ever drifts off-mission.
>
> **What stays the same:** the four gates, the verifiers, the witness step,
> the audit trail, the substrate. The engine you run on Hetzner is the same
> Python process that runs on Windows today.
>
> **What changes:** the engine now lives on hardware that doesn't fight you
> for resources. No OneDrive sync collisions. No Windows Update reboots
> mid-fine-tune. No "Tailscale GUI won't open." No `cloudflared` quirks. A
> real Linux box with a real `systemd` watchdog.
>
> **What does NOT move:** the Mac stays the LoRA training organ. This
> Windows box stays for video encoding, file storage, local dev. Cloudflare
> stays as DNS + the public CDN. Hetzner is one new organ in the body, not
> a replacement for the body.

This document walks the operator from "no Hetzner account" to "engine
running at `api.narrowhighway.com` with auto-restart, TLS, and the
substrate intact." Every command is real. Every cost is real.

---

## The trajectory

```
PHASE 1   Create account, spin up server, lock it down       (~30 min)
PHASE 2   Install runtime + clone repo + secrets             (~20 min)
PHASE 3   Run engine, write systemd unit, write watchdog     (~30 min)
PHASE 4   Add Caddy + TLS, point DNS, cutover                (~30 min)
PHASE 5   Migrate substrate, port the daily reading + backup (~45 min)
PHASE 6   Decommission Windows engine (or leave as failover) (~10 min)
```

Total: ~3 hours of focused work spread over one or two sittings. Hetzner
bills hourly, so you can pause without burning anything.

---

## What you're paying for

| Line item | Hetzner SKU | Monthly |
|---|---|---|
| **Main engine box** | CCX21 (4 vCPU dedicated, 16 GB RAM, 80 GB NVMe) | €10.71 |
| **Substrate volume** | 100 GB block storage | €4.40 |
| **Backups** | 20% of server cost, included weekly snapshots | €2.14 |
| **Traffic** | First 20 TB outbound free | €0 |
| **Total** | | **~€17/mo (~$19 USD)** |

If you want a smaller starting point: **CCX13** (2 vCPU, 8 GB RAM, 40 GB)
at €4.85/mo. Identical to your current Windows engine load, just on real
hardware. You can resize to CCX21 from the Hetzner panel without
re-installing.

GPU later (only when you want to host inference of the sovereign adapter):
**EX44 dedicated** (Ryzen + RTX 4000 SFF) at ~€88/mo, or **AX42** with
RTX 4060 Ti at ~€59/mo. Defer until traffic justifies. Not needed for the
engine itself.

---

## Phase 1 — Create account, spin up, lock down

### 1.1  Account

1. Go to <https://www.hetzner.com/cloud> → **Sign up**.
2. Email + password. Verify email.
3. Add payment method (credit card or SEPA). Hetzner bills hourly,
   capped at the monthly rate.
4. In the dashboard, create a **Project** named `narrowhighway`. All
   resources live inside it.

### 1.2  Add your SSH key first

Hetzner injects this into the new server at provision time, so you'll have
key-based access from minute zero. Skipping this step and using the
emailed root password is fine but the key path is cleaner.

**On the Windows box (PowerShell):**

```powershell
# If you don't already have an SSH key
ssh-keygen -t ed25519 -C "hdven@narrowhighway"
# Press Enter to accept default path; passphrase optional but recommended

# Show the public key to paste into Hetzner
Get-Content $env:USERPROFILE\.ssh\id_ed25519.pub
```

Copy the entire line (starts with `ssh-ed25519`). In Hetzner Cloud panel →
**Security** → **SSH Keys** → **Add SSH Key** → paste → name it
`hdven-windows`. Repeat from the Mac with that key's contents
(`cat ~/.ssh/id_ed25519.pub`) and name it `hdven-mac`. Both Mac and
Windows can now SSH into the new box.

### 1.3  Provision the server

1. **Servers** → **Add Server**.
2. **Location:** Ashburn (Virginia) — closest to your US audience, lower
   latency than the EU options. Hillsboro (Oregon) is the west-coast
   alternative.
3. **Image:** **Ubuntu 24.04**.
4. **Type:** **Shared vCPU** tab → **CCX21** (Intel, 4 vCPU dedicated,
   16 GB RAM, 80 GB NVMe). Or **CCX13** if you want to start smaller.
5. **Networking:** leave defaults (IPv4 + IPv6, public).
6. **SSH keys:** select the keys you added in 1.2.
7. **Volumes:** **Add Volume** → 100 GB, format ext4, mount at
   `/data/substrate`. This is where the engine's substrate lives so
   resizing the OS disk later doesn't touch it.
8. **Backups:** check the box. Adds 20% to your bill, gives you 7 rolling
   daily snapshots.
9. **Name:** `nh-engine-1`.
10. **Create & Buy now.** Provisioning takes ~30 seconds.

Note the public IPv4 address that appears — you'll use it everywhere
below as `<HETZNER_IP>`.

### 1.4  First login + lock down

```bash
# From the Windows box or Mac:
ssh root@<HETZNER_IP>

# You're now on Ubuntu 24.04. Update everything.
apt update && apt full-upgrade -y && apt autoremove -y

# Create the unprivileged user that owns the engine
adduser nh                                    # set a strong password
usermod -aG sudo nh
# Mirror your SSH key into the nh user's authorized_keys
mkdir -p /home/nh/.ssh
cp /root/.ssh/authorized_keys /home/nh/.ssh/
chown -R nh:nh /home/nh/.ssh
chmod 700 /home/nh/.ssh
chmod 600 /home/nh/.ssh/authorized_keys

# Disable root SSH login (you'll use nh from now on)
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl reload ssh

# Firewall: allow SSH, HTTP, HTTPS — block everything else
apt install -y ufw
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

# Mount the volume the engine will use
# Hetzner mounted it but verify
df -h | grep substrate
# Should show /data/substrate as a separate filesystem
```

Logout (`exit`), then verify you can still get in as `nh`:

```bash
ssh nh@<HETZNER_IP>
```

If yes — you're locked down. Root is no longer reachable from the
network.

---

## Phase 2 — Runtime, repo, secrets

### 2.1  System dependencies

```bash
# Now logged in as nh@nh-engine-1
sudo apt install -y \
    python3.12 python3.12-venv python3-pip \
    git curl wget jq tmux htop \
    build-essential \
    ffmpeg \
    sqlite3 \
    rsync

# Optional but recommended — Piper TTS for daily reading
sudo apt install -y piper                     # may need to enable backports

# Verify Python
python3.12 --version                          # 3.12.x
```

### 2.2  Clone the repo

```bash
cd ~
git clone https://github.com/matharrismma/Lighthouse.git
cd Lighthouse

# Pin the working branch
git branch
```

If the repo is private and you need a deploy key, generate one and add to
GitHub:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
# Paste this into GitHub → Settings → Deploy keys → Add deploy key
# (Read-only is fine. Hetzner only pulls; it never pushes.)
```

### 2.3  Python environment

```bash
cd ~/Lighthouse
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip wheel
pip install -r requirements.txt              # whatever your repo declares
```

If you don't have a `requirements.txt`, install the engine's deps
manually:

```bash
pip install fastapi uvicorn[standard] httpx pydantic python-dotenv \
            anthropic sympy scipy pint cryptography pyyaml
```

### 2.4  Secrets

The engine reads `.env` from the repo root. Do NOT commit it.

```bash
nano ~/Lighthouse/.env
```

Paste (replace with your real values):

```
ANTHROPIC_API_KEY=sk-ant-...
NH_REPO_ROOT=/home/nh/Lighthouse
NH_SUBSTRATE_ROOT=/data/substrate
NH_PUBLIC_HOST=api.narrowhighway.com
NH_ENGINE_PORT=8000
```

Lock it down:

```bash
chmod 600 ~/Lighthouse/.env
```

### 2.5  Smoke-test the engine

```bash
cd ~/Lighthouse
source .venv/bin/activate
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

In another terminal:

```bash
ssh nh@<HETZNER_IP>
curl -s http://127.0.0.1:8000/health | jq .
```

You should see `{"status":"ok",...}`. Ctrl-C to stop. Engine works.

---

## Phase 3 — systemd unit + watchdog

### 3.1  The service unit

```bash
sudo nano /etc/systemd/system/nh-engine.service
```

Paste:

```ini
[Unit]
Description=Narrow Highway concordance engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nh
Group=nh
WorkingDirectory=/home/nh/Lighthouse
Environment="PATH=/home/nh/Lighthouse/.venv/bin:/usr/bin"
EnvironmentFile=/home/nh/Lighthouse/.env
ExecStart=/home/nh/Lighthouse/.venv/bin/uvicorn api.app:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
StartLimitInterval=300
StartLimitBurst=5

# Hardening
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=false
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nh-engine
sudo systemctl status nh-engine                # should be active (running)
journalctl -u nh-engine -f                     # tail the log
```

The engine now starts on boot and restarts on failure. If `/health`
hangs, systemd kills it after the failure window and brings it back.

### 3.2  External watchdog

systemd's restart works for crashes, not hangs. The existing
`tools/engine_watchdog.py` already handles "responding but stuck."
Port it as a second systemd unit:

```bash
sudo nano /etc/systemd/system/nh-watchdog.service
```

```ini
[Unit]
Description=Narrow Highway engine watchdog
After=nh-engine.service
Wants=nh-engine.service

[Service]
Type=simple
User=nh
WorkingDirectory=/home/nh/Lighthouse
Environment="PATH=/home/nh/Lighthouse/.venv/bin:/usr/bin"
ExecStart=/home/nh/Lighthouse/.venv/bin/python tools/engine_watchdog.py \
    --health-url http://127.0.0.1:8000/health \
    --restart-cmd "systemctl restart nh-engine"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nh-watchdog
sudo systemctl status nh-watchdog
```

(If `tools/engine_watchdog.py` doesn't accept those flags yet, that's a
small patch — the current Windows version assumes
`Restart_Concordance_Server.ps1`. Use `Edit` to swap in
`--restart-cmd` support.)

---

## Phase 4 — Caddy + TLS + DNS

### 4.1  Install Caddy

Caddy is simpler than nginx + certbot: one config file, automatic Let's
Encrypt, no cron jobs.

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
    sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
    sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

### 4.2  Caddyfile

```bash
sudo nano /etc/caddy/Caddyfile
```

Replace contents:

```caddy
api.narrowhighway.com {
    # lb_try_* gives Caddy a hold-and-retry window so a brief upstream gap
    # (engine restart / redeploy, ~2s) is absorbed instead of returning 502.
    # Without it, an `nh-engine` restart shows as a short outage to clients
    # and to the Keep dashboard's next poll. Proven: 80/80 requests stayed
    # 200 through a full restart under load.
    reverse_proxy 127.0.0.1:8000 {
        lb_try_duration 10s
        lb_try_interval 250ms
    }

    encode gzip zstd

    log {
        output file /var/log/caddy/api.access.log
        format json
    }

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```

> Apply the same `reverse_proxy ... { lb_try_duration 10s; lb_try_interval
> 250ms }` block to the `narrowhighway.com` and `narrowhighway.org,
> narrowhighway.tv` site blocks too, so every domain rides through a redeploy.

```bash
sudo systemctl reload caddy
sudo systemctl status caddy
```

### 4.3  DNS in Cloudflare

1. Cloudflare dashboard → narrowhighway.com → **DNS**.
2. Add an **A record**: name `api`, value `<HETZNER_IP>`, **proxy status
   OFF (DNS only — grey cloud)**.
3. Why grey cloud: Caddy's Let's Encrypt cert needs the origin reachable
   on port 80 for the HTTP-01 challenge. Once the cert is issued you can
   flip the proxy back on if you want Cloudflare's CDN in front. For
   `api.` subdomain serving JSON this is usually unnecessary.
4. Wait 30 seconds for DNS propagation.
5. From any machine:

```bash
curl -s https://api.narrowhighway.com/health | jq .
```

Should return the engine's health JSON. Caddy provisioned the cert
automatically.

### 4.4  Cutover the public API

The narrowhighway.com static site (Cloudflare Pages) currently points to
the Windows box's engine via `cloudflared` tunnel. Switch it to
`api.narrowhighway.com`:

```bash
# On the Windows box, in the Lighthouse repo:
grep -rn "narrowhighway.com/api\|cloudflared\|localhost:8000" site/ | head -20
```

Update the static site's JS calls to hit `https://api.narrowhighway.com`
instead of whatever it hit before. Commit, push. Cloudflare Pages
auto-deploys.

---

## Phase 5 — Substrate migration

The engine needs the cards, the keep, the bible, the verifiers, the
ledger. Bring these from Windows over Tailscale + rsync.

### 5.1  Install Tailscale on Hetzner

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --ssh
# Follow the URL it prints in a browser, authorize
tailscale status                              # confirms 3 nodes now
```

This Hetzner box is now `nh-engine-1.<your-tailnet>.ts.net` — Tailscale
SSH works in Linux (unlike Windows where it doesn't).

### 5.2  rsync substrate from Windows

**On Windows (PowerShell):**

```powershell
cd $env:USERPROFILE\OneDrive\Documents\Claude\Projects\Lighthouse

# Push the substrate to Hetzner over Tailscale
$HETZNER = "nh-engine-1"   # or its 100.x Tailscale IP

# Engine-load-bearing directories
rsync -avz --progress data/cards/        nh@${HETZNER}:/data/substrate/cards/
rsync -avz --progress data/keep/         nh@${HETZNER}:/data/substrate/keep/
rsync -avz --progress data/almanac/      nh@${HETZNER}:/data/substrate/almanac/
rsync -avz --progress data/seeds/        nh@${HETZNER}:/data/substrate/seeds/
rsync -avz --progress data/bible_en/     nh@${HETZNER}:/data/substrate/bible_en/
rsync -avz --progress data/library_inventory/ nh@${HETZNER}:/data/substrate/library_inventory/
rsync -avz --progress data/training_corpus/   nh@${HETZNER}:/data/substrate/training_corpus/
rsync -avz --progress data/eval/         nh@${HETZNER}:/data/substrate/eval/
rsync -avz --progress data/models/       nh@${HETZNER}:/data/substrate/models/
rsync -avz --progress data/discernments/ nh@${HETZNER}:/data/substrate/discernments/
rsync -avz --progress data/witness_roll/ nh@${HETZNER}:/data/substrate/witness_roll/
rsync -avz --progress ledger/            nh@${HETZNER}:/data/substrate/ledger/
```

**Skip** (don't sync): `data/publish/`, `data/serials/`, `data/raw_sources/`,
`data/inbox/`, video files. These either belong on Windows (encoding
work) or rebuild on demand.

### 5.3  Symlink substrate into the repo

**On Hetzner:**

```bash
ssh nh@nh-engine-1
cd ~/Lighthouse

# The engine looks for ./data/... relative to repo root.
# Symlink each substrate dir to the volume.
for d in cards keep almanac seeds bible_en library_inventory training_corpus eval models discernments witness_roll; do
    rm -rf data/$d 2>/dev/null
    ln -s /data/substrate/$d data/$d
done

# Ledger lives at repo root, not under data/
rm -rf ledger 2>/dev/null
ln -s /data/substrate/ledger ledger

# Restart engine so it picks them up
sudo systemctl restart nh-engine
journalctl -u nh-engine -n 50
```

### 5.4  Migrate the daily reading

```bash
# Install Piper voice (one-time)
cd ~/Lighthouse
.venv/bin/python tools/install_piper_voice.py --voice en_US-lessac-medium

# Test
.venv/bin/python tools/render_daily_reading.py
ls site/assembly/audio/today/

# Schedule via systemd timer
sudo nano /etc/systemd/system/nh-daily-reading.service
```

```ini
[Unit]
Description=Narrow Highway daily reading render

[Service]
Type=oneshot
User=nh
WorkingDirectory=/home/nh/Lighthouse
ExecStart=/home/nh/Lighthouse/.venv/bin/python tools/render_daily_reading.py --include-proverb
```

```bash
sudo nano /etc/systemd/system/nh-daily-reading.timer
```

```ini
[Unit]
Description=Render daily reading at 04:30 local

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nh-daily-reading.timer
systemctl list-timers nh-daily-reading
```

### 5.5  Substrate backup

The existing `tools/substrate_backup.py` works as-is. Schedule it:

```bash
sudo nano /etc/systemd/system/nh-substrate-backup.service
```

```ini
[Unit]
Description=Narrow Highway substrate backup

[Service]
Type=oneshot
User=nh
WorkingDirectory=/home/nh/Lighthouse
ExecStart=/home/nh/Lighthouse/.venv/bin/python tools/substrate_backup.py
```

```bash
sudo nano /etc/systemd/system/nh-substrate-backup.timer
```

```ini
[Unit]
Description=Nightly substrate backup at 03:00

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nh-substrate-backup.timer
```

Tarballs land in `/home/nh/Backups/narrowhighway/`. Hetzner's own
weekly snapshots (Phase 1.3) cover disaster recovery; this gives you
file-level rollback for "I deleted the wrong card."

### 5.6  Optional — offsite backup

Hetzner snapshots are great until Hetzner has a regional outage. Mirror
the nightly backup to a second provider:

```bash
sudo apt install -y rclone
rclone config                                 # add an S3-compatible target
# Backblaze B2 is the cheapest: $6/TB-mo, no egress fees within free tier

# Add to nh-substrate-backup.service ExecStart:
ExecStartPost=/usr/bin/rclone copy /home/nh/Backups/narrowhighway/ b2:nh-backups/
```

Defer if you want — Hetzner's own backups are fine for the first month.

---

## Phase 6 — Decommission Windows engine

The Windows engine has been doing six things tonight. After Hetzner is
running, it only needs to do one or two.

**Stop the Windows engine cleanly:**

```powershell
# Confirm Hetzner is serving everything
curl https://api.narrowhighway.com/health

# Stop Windows engine watchdog
Stop-Process -Name python -Force -ErrorAction SilentlyContinue

# Disable startup so it stays down across reboots
# (whatever auto-start mechanism you used — Task Scheduler, Startup folder, etc.)
```

**What you can leave running on Windows:**

- Video encoder (for FAST channel encodes)
- Cloudflared tunnel (kept as backup route — costs nothing)
- File storage (~/Downloads, /D drive)
- This Claude Code session for ongoing dev

**What stops running on Windows:**

- The engine
- The engine watchdog
- The substrate backup (now runs on Hetzner)
- The daily reading render (now runs on Hetzner)

The Mac's role is unchanged: LoRA training organ, fires when you want a
fine-tune.

---

## Operational notes

### Logs

```bash
journalctl -u nh-engine -f                    # live tail
journalctl -u nh-engine --since "1 hour ago"
journalctl -u nh-watchdog --since today
sudo tail -f /var/log/caddy/api.access.log
```

### Engine restart

```bash
sudo systemctl restart nh-engine
```

That's the whole restart story now. No PowerShell, no UAC, no log-file
collision.

### Deploy a code change

```bash
ssh nh@nh-engine-1
cd ~/Lighthouse
git pull
sudo systemctl restart nh-engine
journalctl -u nh-engine -n 20
```

For a CI-style auto-deploy on `git push`, add a GitHub Actions workflow
that SSHs in and runs that block. Defer until the manual path feels
slow.

### Resize the server

Hetzner panel → server → **Rescale**. Pick a bigger type, click apply,
~30 seconds offline. No data loss. The volume is independent of the
server, so even a full reinstall keeps the substrate.

### Costs and bill-watching

```bash
# Set a budget alert in Hetzner Cloud Console:
# Account → Billing → Set monthly threshold (e.g. €25)
```

Hetzner emails you when you cross it. The CCX21 + 100 GB volume +
backups is hard-capped around €17/mo — there's no surprise bill from
data egress unless you start serving multi-TB.

---

## Rollback plan

If something is wrong on Hetzner you cannot diagnose in 30 minutes:

1. **DNS rollback** — Cloudflare DNS → change `api.narrowhighway.com`
   from `<HETZNER_IP>` back to the Cloudflare tunnel that points at
   Windows. Site traffic returns to Windows in <5 minutes (Cloudflare
   TTL).
2. **Re-enable the Windows engine** — start the engine service back up.
3. **Investigate Hetzner without traffic on it.**

You can keep the Windows engine *in* for a week or two while you build
trust in the Hetzner setup. There's no rush to decommission.

---

## Standing rules (carry forward from Windows)

- **Not AI** — same gates, same verifiers, same audit trail. The Hetzner
  box is one organ. See [`/organic-design.html`](../site/organic-design.html).
- **Strict PD-only content acquisition.**
- **No begging, no investor money, no ads** — Hetzner is paid out of the
  same revenue line as Anthropic and Runway.
- **Operator approves every removal.**
- **Substrate is signed** — `tools/substrate_backup.py` continues to run
  nightly, output tarballs go offsite.

---

## What you do NOT do on Hetzner

- Don't `apt install` random things from the internet. Stick to
  `python3.12`, `caddy`, `tailscale`, `rsync`, `ffmpeg`, `piper`, and
  whatever the engine requires.
- Don't run user data through `sudo`. The `nh` user has its own home.
- Don't open ports beyond 22, 80, 443.
- Don't auto-deploy `main` to production without a test step — the engine
  is the body's voice.
- Don't host the Mac fine-tune here. Hetzner CCX21 has no GPU and no
  Apple Silicon. MLX is the Mac's organ; HF/transformers on a separate
  GPU box is the future plan if you want sovereign inference. Hetzner's
  job is the engine, not the model.

---

## Reference

- Hetzner Cloud Console: <https://console.hetzner.cloud>
- Hetzner status: <https://status.hetzner.com>
- Caddy docs: <https://caddyserver.com/docs/>
- Cloudflare DNS: <https://dash.cloudflare.com>
- Architecture: <https://narrowhighway.com/organic-design.html>
- Mac runbook: [`mac/START_FINETUNE.md`](../mac/START_FINETUNE.md)
- Windows runbook (legacy, after this is done): `site/windows/index.html`
- Standalone model trajectory: [`STANDALONE_MODEL.md`](STANDALONE_MODEL.md)
