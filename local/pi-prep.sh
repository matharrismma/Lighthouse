#!/usr/bin/env bash
#
# Concordance Pi Prep
# ───────────────────
# Run this ON a freshly flashed Raspberry Pi OS Lite BEFORE the main installer.
# Sets hostname, enables mDNS, optimises for headless node operation.
#
# Usage (from the Pi, via SSH):
#   curl -fsSL https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/pi-prep.sh | bash
#   # Then reboot:
#   sudo reboot
#   # Then install Concordance:
#   curl -fsSL https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/install.sh | bash
#

set -euo pipefail

C_CYAN='\033[0;36m'; C_GREEN='\033[0;32m'; C_BOLD='\033[1m'; C_RESET='\033[0m'
log()  { echo -e "${C_CYAN}▸${C_RESET} $*"; }
ok()   { echo -e "${C_GREEN}✓${C_RESET} $*"; }
bold() { echo -e "${C_BOLD}$*${C_RESET}"; }

bold ""
bold "  Concordance · Pi Prep"
bold ""

# ── HOSTNAME ──────────────────────────────────────────────────────────────
NEW_HOSTNAME="${1:-concordance}"
CURRENT=$(hostname)

if [ "$CURRENT" != "$NEW_HOSTNAME" ]; then
  log "Setting hostname: $NEW_HOSTNAME"
  echo "$NEW_HOSTNAME" | sudo tee /etc/hostname >/dev/null
  sudo sed -i "s/127.0.1.1.*/127.0.1.1\t$NEW_HOSTNAME/g" /etc/hosts
  sudo hostnamectl set-hostname "$NEW_HOSTNAME" 2>/dev/null || true
  ok "Hostname → $NEW_HOSTNAME (takes effect after reboot)"
fi

# ── SYSTEM UPDATE ─────────────────────────────────────────────────────────
log "Updating package lists…"
sudo apt-get update -qq

log "Installing core packages…"
sudo apt-get install -y -qq \
  git python3 python3-venv python3-pip \
  avahi-daemon avahi-utils libnss-mdns \
  curl wget htop

# Enable mDNS in nsswitch if not already
if ! grep -q "mdns4_minimal" /etc/nsswitch.conf 2>/dev/null; then
  sudo sed -i 's/^hosts:.*/hosts:          files mdns4_minimal [NOTFOUND=return] dns/' \
    /etc/nsswitch.conf
  ok "mDNS enabled in nsswitch.conf"
fi

sudo systemctl enable avahi-daemon
sudo systemctl start avahi-daemon
ok "avahi-daemon running"

# ── SWAP (Pi Zero has 512MB RAM — bump swap to handle pip install) ─────────
if grep -q "CONF_SWAPSIZE=100" /etc/dphys-swapfile 2>/dev/null; then
  log "Increasing swap to 512MB (needed for pip on Pi Zero)…"
  sudo dphys-swapfile swapoff
  sudo sed -i 's/CONF_SWAPSIZE=100/CONF_SWAPSIZE=512/' /etc/dphys-swapfile
  sudo dphys-swapfile setup
  sudo dphys-swapfile swapon
  ok "Swap → 512MB"
fi

# ── GPU MEMORY (headless — give RAM back from GPU) ────────────────────────
if [ -f /boot/config.txt ] && ! grep -q "^gpu_mem=" /boot/config.txt; then
  echo "gpu_mem=16" | sudo tee -a /boot/config.txt >/dev/null
  ok "GPU memory → 16MB (headless)"
fi

# ── DISABLE BLUETOOTH + WIFI POWER SAVE (stability) ──────────────────────
if ! grep -q "dtoverlay=disable-bt" /boot/config.txt 2>/dev/null; then
  echo -e "\n# Concordance node tweaks\ndtoverlay=disable-bt" | \
    sudo tee -a /boot/config.txt >/dev/null
fi

# Disable WiFi power management
if [ -f /etc/rc.local ]; then
  grep -q "iwconfig.*power off" /etc/rc.local || \
    sudo sed -i '/^exit 0/i iwconfig wlan0 power off 2>/dev/null || true' /etc/rc.local
fi
ok "WiFi power save disabled"

# ── SUMMARY ───────────────────────────────────────────────────────────────
echo ""
bold "  Pi is ready for Concordance."
echo ""
echo "  Hostname  : $NEW_HOSTNAME"
echo "  mDNS      : $NEW_HOSTNAME.local"
echo ""
echo "  Reboot now, then run the installer:"
echo ""
echo "    sudo reboot"
echo "    # (SSH back in after ~30 seconds)"
echo "    curl -fsSL https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/install.sh | bash"
echo ""
