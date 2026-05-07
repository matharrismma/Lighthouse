#!/data/data/com.termux/files/usr/bin/bash
#
# termux-setup.sh — Turn an old Android phone into a Concordance node
# ─────────────────────────────────────────────────────────────────────
# One command. Phone becomes a fully self-contained Concordance terminal.
#
# Prerequisites on the phone:
#   1. Install Termux from F-Droid (NOT the Play Store version — it's outdated)
#      https://f-droid.org/en/packages/com.termux/
#   2. Run this script:
#      curl -fsSL https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/termux-setup.sh | bash
#   3. Install the Concordance Launcher APK (see GitHub Releases)
#   4. Settings → set as home screen → done
#
# The node starts automatically on Termux launch and listens on localhost:8000.
# The launcher auto-connects to it (no configuration needed).
#

set -euo pipefail

C_CYAN='\033[0;36m'
C_GREEN='\033[0;32m'
C_BOLD='\033[1m'
C_RESET='\033[0m'
log()  { echo -e "${C_CYAN}▸${C_RESET} $*"; }
ok()   { echo -e "${C_GREEN}✓${C_RESET} $*"; }
bold() { echo -e "${C_BOLD}$*${C_RESET}"; }

bold ""
bold "  Concordance — Android Node Setup"
bold "  Turning this phone into a wisdom terminal"
bold ""

# ── STEP 1: Termux packages ────────────────────────────────────────────────
bold "1/5  Installing packages"
pkg update -y -q
pkg install -y -q \
  python git curl openssh termux-services

# termux-services handles background daemons via runit
sv-enable sshd 2>/dev/null || true
ok "Packages ready"

# ── STEP 2: Clone / update Concordance ────────────────────────────────────
bold "2/5  Concordance engine"

INSTALL_DIR="$HOME/concordance"
REPO_URL="${REPO_URL:-https://github.com/matharrismma/Lighthouse.git}"

if [ -d "$INSTALL_DIR/.git" ]; then
  log "Updating existing install…"
  git -C "$INSTALL_DIR" pull --ff-only -q
else
  log "Cloning from $REPO_URL…"
  git clone --depth 1 -q "$REPO_URL" "$INSTALL_DIR"
fi
ok "Engine at $INSTALL_DIR"

# ── STEP 3: Python venv + deps ────────────────────────────────────────────
bold "3/5  Python environment"

python -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install -q \
  -r "$INSTALL_DIR/api/requirements.txt" \
  requests cryptography
ok "Dependencies installed"

# ── STEP 4: Node identity ─────────────────────────────────────────────────
bold "4/5  Node identity"

CONFIG_DIR="$HOME/.concordance"
mkdir -p "$CONFIG_DIR"
KEY_FILE="$CONFIG_DIR/node_key.json"

if [ ! -f "$KEY_FILE" ]; then
  log "Generating Ed25519 signing key…"
  python3 "$INSTALL_DIR/local/node-init.py" --out "$KEY_FILE"
  ok "Key generated: $KEY_FILE"
else
  ok "Key exists (skipping)"
fi

# Write config
cat > "$CONFIG_DIR/config.env" <<CFGEOF
CONCORDANCE_HOST=127.0.0.1
CONCORDANCE_PORT=8000
CONCORDANCE_DATA_DIR=$INSTALL_DIR/data
CONCORDANCE_NODE_KEY=$KEY_FILE
CONCORDANCE_LOG_LEVEL=warning
CONCORDANCE_OFFLINE=0
CONCORDANCE_WITNESS_URL=https://concordance.run
CFGEOF
NODE_ID=$(python3 -c "import json; d=json.load(open('$KEY_FILE')); print(d['node_id'])" 2>/dev/null || echo "unknown")
echo "CONCORDANCE_NODE_ID=$NODE_ID" >> "$CONFIG_DIR/config.env"
ok "Config: $CONFIG_DIR/config.env"

# ── STEP 5: Auto-start service ────────────────────────────────────────────
bold "5/5  Auto-start on Termux launch"

# Write the start script
cat > "$HOME/start-concordance.sh" <<'STARTEOF'
#!/data/data/com.termux/files/usr/bin/bash
# Start Concordance node (called from .bashrc on Termux open)
CONFIG="$HOME/.concordance/config.env"
[ -f "$CONFIG" ] && export $(grep -v '^#' "$CONFIG" | xargs)

INSTALL_DIR="$HOME/concordance"
LOG_FILE="$HOME/.concordance/concordance.log"

# Check if already running
if pgrep -f "uvicorn api.app:app" > /dev/null 2>&1; then
  echo "▸ Concordance already running on :${CONCORDANCE_PORT:-8000}"
  exit 0
fi

echo "▸ Starting Concordance node…"
cd "$INSTALL_DIR"
nohup "$INSTALL_DIR/.venv/bin/python" -m uvicorn api.app:app \
  --host "${CONCORDANCE_HOST:-127.0.0.1}" \
  --port "${CONCORDANCE_PORT:-8000}" \
  --workers 1 \
  --log-level "${CONCORDANCE_LOG_LEVEL:-warning}" \
  >> "$LOG_FILE" 2>&1 &

# Wait for startup
sleep 2
if curl -sf "http://127.0.0.1:${CONCORDANCE_PORT:-8000}/health" > /dev/null 2>&1; then
  echo "✓ Concordance node ready at http://localhost:${CONCORDANCE_PORT:-8000}"
else
  echo "  Starting… check log: tail $LOG_FILE"
fi
STARTEOF
chmod +x "$HOME/start-concordance.sh"

# Hook into .bashrc so it starts automatically when Termux opens
BASHRC="$HOME/.bashrc"
if ! grep -q "start-concordance" "$BASHRC" 2>/dev/null; then
  cat >> "$BASHRC" <<'RCEOF'

# ── Concordance node (auto-start) ─────────────────────────────────────────
if [ -f "$HOME/start-concordance.sh" ]; then
  bash "$HOME/start-concordance.sh"
fi
RCEOF
  ok "Added to .bashrc — starts on every Termux launch"
else
  ok ".bashrc already configured"
fi

# ── LAUNCH NOW ────────────────────────────────────────────────────────────
bold ""
bold "  Starting node now…"
bash "$HOME/start-concordance.sh"

# ── DONE ──────────────────────────────────────────────────────────────────
NODE_SHORT="${NODE_ID:0:12}"

bold ""
bold "  ┌─────────────────────────────────────────────────────┐"
bold "  │   Concordance node is running                       │"
echo "  │                                                     │"
echo "  │   Endpoint : http://localhost:8000                  │"
echo "  │   Node ID  : ${NODE_SHORT}…"
echo "  │   Config   : ~/.concordance/config.env              │"
echo "  │   Logs     : ~/.concordance/concordance.log         │"
echo "  │                                                     │"
echo "  │   NEXT: Install the Concordance Launcher APK        │"
echo "  │   (see GitHub Releases — concordance-launcher.apk)  │"
echo "  │   Set it as your home screen — you're done.         │"
bold "  └─────────────────────────────────────────────────────┘"
bold ""
echo "  To stop:    pkill -f 'uvicorn api.app:app'"
echo "  To restart: bash ~/start-concordance.sh"
echo "  To update:  git -C ~/concordance pull && bash ~/start-concordance.sh"
bold ""
