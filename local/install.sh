#!/usr/bin/env bash
#
# Concordance Node Installer
# ──────────────────────────
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/install.sh | bash
#
# Supports: Raspberry Pi OS (arm64/armv7l), Debian 11+, Ubuntu 20.04+, macOS 12+
# Installs: /opt/concordance  (app + packets)
# Data:     /var/lib/concordance
# Config:   /etc/concordance/config.env
# Service:  systemd (Linux) / launchd (macOS)
# Access:   http://concordance.local:8000
#

set -euo pipefail
IFS=$'\n\t'

# ── COLORS ─────────────────────────────────────────────────────────────
C_CYAN='\033[0;36m'; C_GREEN='\033[0;32m'; C_YELLOW='\033[0;33m'
C_RED='\033[0;31m'; C_BOLD='\033[1m'; C_RESET='\033[0m'

log()  { echo -e "${C_CYAN}▸${C_RESET} $*"; }
ok()   { echo -e "${C_GREEN}✓${C_RESET} $*"; }
warn() { echo -e "${C_YELLOW}⚠${C_RESET} $*"; }
die()  { echo -e "${C_RED}✗ $*${C_RESET}" >&2; exit 1; }
bold() { echo -e "${C_BOLD}$*${C_RESET}"; }

# ── CONSTANTS ───────────────────────────────────────────────────────────
REPO_URL="https://github.com/matharrismma/Lighthouse.git"
INSTALL_DIR="/opt/concordance"
DATA_DIR="/var/lib/concordance"
CONFIG_DIR="/etc/concordance"
LOG_DIR="/var/log/concordance"
RUN_DIR="/run/concordance"
SERVICE_USER="concordance"
PORT="${CONCORDANCE_PORT:-8000}"
WITNESS_URL="${CONCORDANCE_WITNESS:-https://concordance.run}"
PYTHON_MIN_MAJOR=3
PYTHON_MIN_MINOR=10

# ── DETECT ENVIRONMENT ──────────────────────────────────────────────────
OS=$(uname -s)
ARCH=$(uname -m)
IS_PI=false
IS_MAC=false
IS_LINUX=false
HAS_SYSTEMD=false

case "$OS" in
  Linux)
    IS_LINUX=true
    grep -qi "raspberry" /proc/cpuinfo 2>/dev/null && IS_PI=true || true
    [ -d /run/systemd/system ] && HAS_SYSTEMD=true || true
    ;;
  Darwin)
    IS_MAC=true
    INSTALL_DIR="$HOME/.concordance"
    DATA_DIR="$HOME/.concordance/data"
    CONFIG_DIR="$HOME/.concordance/etc"
    LOG_DIR="$HOME/.concordance/log"
    ;;
  *)
    die "Unsupported OS: $OS. Run on Linux (Raspberry Pi, Ubuntu, Debian) or macOS."
    ;;
esac

need_sudo() { [ "$IS_LINUX" = true ] && [ "$(id -u)" -ne 0 ]; }

# ── BANNER ──────────────────────────────────────────────────────────────
echo ""
bold "  ┌─────────────────────────────────────┐"
bold "  │   Concordance  ·  Node Installer    │"
bold "  └─────────────────────────────────────┘"
echo ""
echo "  OS       : $OS $ARCH"
[ "$IS_PI" = true ]      && echo "  Device   : Raspberry Pi ✓"
echo "  Install  : $INSTALL_DIR"
echo "  Data     : $DATA_DIR"
echo "  Port     : $PORT"
echo "  Witness  : $WITNESS_URL"
echo ""

# ── SUDO CHECK ──────────────────────────────────────────────────────────
if need_sudo; then
  warn "Not running as root. Will use sudo for system operations."
  sudo -v || die "sudo access required for Linux install."
  SUDO="sudo"
else
  SUDO=""
fi

# ── STEP 1: SYSTEM PACKAGES ─────────────────────────────────────────────
bold "1/7  System packages"

install_pkg() {
  if command -v apt-get &>/dev/null; then
    $SUDO apt-get install -y -qq "$@"
  elif command -v dnf &>/dev/null; then
    $SUDO dnf install -y -q "$@"
  elif command -v brew &>/dev/null; then
    brew install "$@" 2>/dev/null || true
  else
    warn "Cannot auto-install packages. Please install manually: $*"
  fi
}

# Git
if ! command -v git &>/dev/null; then
  log "Installing git…"
  install_pkg git
fi

# Python 3.10+
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "0")
    major=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null || echo "0")
    if [ "$major" -ge "$PYTHON_MIN_MAJOR" ] && [ "$ver" -ge "$PYTHON_MIN_MINOR" ]; then
      PYTHON="$candidate"
      break
    fi
  fi
done

if [ -z "$PYTHON" ]; then
  log "Installing Python 3.11…"
  if command -v apt-get &>/dev/null; then
    $SUDO apt-get install -y -qq python3.11 python3.11-venv python3-pip
    PYTHON=python3.11
  else
    die "Python 3.10+ not found. Install it first: https://python.org/downloads"
  fi
fi
ok "Python: $($PYTHON --version)"

# avahi-daemon for mDNS (concordance.local) — Linux only
if [ "$IS_LINUX" = true ]; then
  if ! command -v avahi-daemon &>/dev/null; then
    log "Installing avahi-daemon (mDNS — concordance.local)…"
    install_pkg avahi-daemon avahi-utils libnss-mdns 2>/dev/null || \
      warn "avahi not installed. Node will be reachable by IP only."
  fi
fi

# ── STEP 2: CLONE / UPDATE REPO ─────────────────────────────────────────
bold "2/7  Repository"

if [ -d "$INSTALL_DIR/.git" ]; then
  log "Updating existing install…"
  $SUDO git -C "$INSTALL_DIR" pull --ff-only
  ok "Updated"
else
  log "Cloning Concordance…"
  $SUDO git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  ok "Cloned to $INSTALL_DIR"
fi

# Fix ownership if sudo
if [ -n "$SUDO" ]; then
  $SUDO chown -R "$(id -u):$(id -g)" "$INSTALL_DIR" 2>/dev/null || true
fi

# ── STEP 3: PYTHON VIRTUALENV + DEPS ────────────────────────────────────
bold "3/7  Python environment"

VENV="$INSTALL_DIR/.venv"

if [ ! -d "$VENV" ]; then
  log "Creating virtualenv…"
  $PYTHON -m venv "$VENV"
fi

log "Installing dependencies…"
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -r "$INSTALL_DIR/api/requirements.txt"
# Optional: requests for ingestion scripts
"$VENV/bin/pip" install -q requests 2>/dev/null || true
ok "Dependencies installed"

# ── STEP 4: DIRECTORIES + SERVICE USER ──────────────────────────────────
bold "4/7  Node setup"

if [ "$IS_LINUX" = true ]; then
  # Create directories
  $SUDO mkdir -p "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR" "$RUN_DIR"

  # Create system user if not exists
  if ! id "$SERVICE_USER" &>/dev/null; then
    log "Creating system user: $SERVICE_USER"
    $SUDO useradd --system --no-create-home \
      --shell /usr/sbin/nologin \
      --home-dir "$INSTALL_DIR" \
      "$SERVICE_USER"
  fi

  # Ownership
  $SUDO chown -R "$SERVICE_USER:$SERVICE_USER" \
    "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR" "$RUN_DIR"
  $SUDO chmod 750 "$CONFIG_DIR"

  # Symlink the repo's data/ into the data dir so the app finds its packets
  if [ ! -L "$INSTALL_DIR/data" ] && [ -d "$INSTALL_DIR/data" ]; then
    $SUDO mv "$INSTALL_DIR/data" "$DATA_DIR/packets-seed" 2>/dev/null || true
  fi
  # App writes data relative to its working dir — point DATA_DIR into the repo
  $SUDO ln -sfn "$DATA_DIR" "$INSTALL_DIR/data-node" 2>/dev/null || true

else
  # macOS — current user owns everything
  mkdir -p "$DATA_DIR" "$CONFIG_DIR" "$LOG_DIR"
fi

ok "Directories ready"

# ── STEP 5: NODE IDENTITY + CONFIG ──────────────────────────────────────
bold "5/7  Node identity"

CONFIG_FILE="$CONFIG_DIR/config.env"

# Generate node identity (Ed25519 key pair) via the engine's own keygen
NODE_KEY_FILE="$CONFIG_DIR/node_key.json"

if [ ! -f "$NODE_KEY_FILE" ]; then
  log "Generating node identity…"
  "$VENV/bin/python" - <<'PYEOF'
import json, os, pathlib, sys
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)

key   = Ed25519PrivateKey.generate()
pub   = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
priv  = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
import socket, hashlib
hostname = socket.gethostname()
node_id  = hashlib.sha256(bytes.fromhex(pub)).hexdigest()[:20]

out = pathlib.Path(sys.argv[1])
out.write_text(json.dumps({
    "node_id":   node_id,
    "hostname":  hostname,
    "public_key":  pub,
    "private_key": priv,
}, indent=2))
print(f"  node_id : {node_id}")
print(f"  hostname: {hostname}")
PYEOF
  "$VENV/bin/python" "$INSTALL_DIR/local/node-init.py" "$NODE_KEY_FILE" 2>/dev/null || \
  "$VENV/bin/python" - "$NODE_KEY_FILE" <<'PYEOF'
import json, socket, hashlib, sys, pathlib
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption
)
key    = Ed25519PrivateKey.generate()
pub    = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
priv   = key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()
hn     = socket.gethostname()
nid    = hashlib.sha256(bytes.fromhex(pub)).hexdigest()[:20]
out    = pathlib.Path(sys.argv[1])
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"node_id":nid,"hostname":hn,"public_key":pub,"private_key":priv},indent=2))
print(f"  node_id : {nid}\n  hostname: {hn}")
PYEOF
  ok "Node identity generated"
else
  NID=$(python3 -c "import json; d=json.load(open('$NODE_KEY_FILE')); print(d['node_id'])" 2>/dev/null || echo "existing")
  ok "Node identity exists ($NID)"
fi

# Write config.env
if [ ! -f "$CONFIG_FILE" ]; then
  NODE_ID=$(python3 -c "import json; d=json.load(open('$NODE_KEY_FILE')); print(d['node_id'])" 2>/dev/null || echo "unknown")
  cat > /tmp/concordance_config.env <<CFGEOF
# Concordance Node Configuration
# Edit and then: systemctl restart concordance

CONCORDANCE_HOST=0.0.0.0
CONCORDANCE_PORT=$PORT
CONCORDANCE_WITNESS_URL=$WITNESS_URL
CONCORDANCE_NODE_ID=$NODE_ID
CONCORDANCE_NODE_KEY=$NODE_KEY_FILE
CONCORDANCE_DATA_DIR=$INSTALL_DIR/data
CONCORDANCE_LOG_LEVEL=info

# Set to 1 to disable outbound witnessing (fully offline)
CONCORDANCE_OFFLINE=0
CFGEOF
  $SUDO mv /tmp/concordance_config.env "$CONFIG_FILE"
  $SUDO chmod 640 "$CONFIG_FILE"
  [ -n "$SUDO" ] && $SUDO chown "$SERVICE_USER:$SERVICE_USER" "$CONFIG_FILE" 2>/dev/null || true
  ok "Config written: $CONFIG_FILE"
fi

# ── STEP 6: SYSTEMD SERVICE ──────────────────────────────────────────────
bold "6/7  System service"

if [ "$IS_LINUX" = true ] && [ "$HAS_SYSTEMD" = true ]; then

  $SUDO tee /etc/systemd/system/concordance.service >/dev/null <<SVCEOF
[Unit]
Description=Concordance Node — Wisdom Engine
Documentation=https://github.com/matharrismma/Lighthouse
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$CONFIG_FILE
ExecStart=$VENV/bin/python -m uvicorn api.app:app \\
    --host \${CONCORDANCE_HOST} \\
    --port \${CONCORDANCE_PORT} \\
    --workers 1 \\
    --log-level \${CONCORDANCE_LOG_LEVEL}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=concordance

# Hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=$DATA_DIR $LOG_DIR $RUN_DIR $INSTALL_DIR/data $INSTALL_DIR/scripts

[Install]
WantedBy=multi-user.target
SVCEOF

  # mDNS advertisement (concordance.local)
  if command -v avahi-daemon &>/dev/null; then
    $SUDO tee /etc/avahi/services/concordance.service >/dev/null <<AVAHIEOF
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">Concordance on %h</name>
  <service>
    <type>_http._tcp</type>
    <port>$PORT</port>
    <txt-record>path=/</txt-record>
    <txt-record>description=Concordance Wisdom Node</txt-record>
  </service>
</service-group>
AVAHIEOF
    $SUDO systemctl restart avahi-daemon 2>/dev/null || true
    ok "mDNS registered (concordance.local)"
  fi

  $SUDO systemctl daemon-reload
  $SUDO systemctl enable concordance
  $SUDO systemctl restart concordance
  ok "Service started (concordance.service)"

elif [ "$IS_MAC" = true ]; then

  PLIST="$HOME/Library/LaunchAgents/run.concordance.plist"
  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>          <string>run.concordance</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV/bin/python</string>
        <string>-m</string>   <string>uvicorn</string>
        <string>api.app:app</string>
        <string>--host</string><string>0.0.0.0</string>
        <string>--port</string><string>$PORT</string>
        <string>--workers</string><string>1</string>
    </array>
    <key>WorkingDirectory</key><string>$INSTALL_DIR</string>
    <key>RunAtLoad</key>      <true/>
    <key>KeepAlive</key>      <true/>
    <key>StandardOutPath</key><string>$LOG_DIR/concordance.log</string>
    <key>StandardErrorPath</key><string>$LOG_DIR/concordance.err</string>
</dict>
</plist>
PLISTEOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  ok "LaunchAgent registered and started"

else
  warn "No systemd or launchd found. Start manually:"
  echo "  $VENV/bin/python -m uvicorn api.app:app --host 0.0.0.0 --port $PORT"
fi

# ── STEP 7: VERIFY ───────────────────────────────────────────────────────
bold "7/7  Verify"

sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "200" ]; then
  ok "Engine responding on port $PORT"
else
  warn "Engine not responding yet (HTTP $HTTP_CODE). Check: journalctl -u concordance -n 30"
fi

# ── DONE ─────────────────────────────────────────────────────────────────
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ipconfig getifaddr en0 2>/dev/null || echo "?")
HOSTNAME=$(hostname)

echo ""
bold "  ┌─────────────────────────────────────────────────┐"
bold "  │   Concordance node is running                   │"
echo "  │                                                 │"
echo "  │   Local     http://localhost:$PORT               │"
echo "  │   Network   http://$LOCAL_IP:$PORT            │"
[ "$IS_LINUX" = true ] && \
echo "  │   mDNS      http://concordance.local:$PORT       │"
echo "  │                                                 │"
echo "  │   Logs      journalctl -u concordance -f        │"
echo "  │   Config    $CONFIG_FILE   │"
echo "  │   Restart   systemctl restart concordance       │"
bold "  └─────────────────────────────────────────────────┘"
echo ""
echo "  To use as an MCP server, add to Claude Code .mcp.json:"
echo ""
echo '  "concordance": {'
echo '    "command": "concordance-mcp",'
echo "    \"env\": { \"CONCORDANCE_API_URL\": \"http://localhost:$PORT\" }"
echo '  }'
echo ""
