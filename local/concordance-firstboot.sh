#!/usr/bin/env bash
#
# concordance-firstboot.sh
# ─────────────────────────
# Runs ONCE on first Pi boot via systemd.
# Reads /boot/firmware/concordance.txt (or /boot/concordance.txt on older Pi OS).
# Configures WiFi, hostname, installs Concordance, starts service.
# Deletes itself after success so it never runs again.
#
# Do not run manually — managed by concordance-firstboot.service
#

set -euo pipefail
LOG=/var/log/concordance-firstboot.log
exec > >(tee -a "$LOG") 2>&1

echo "═══════════════════════════════════════════════"
echo "  Concordance First Boot  $(date -Iseconds)"
echo "═══════════════════════════════════════════════"

# ── FIND CONFIG FILE ─────────────────────────────────────────────────────
# Pi OS Bookworm mounts boot at /boot/firmware; Bullseye uses /boot
BOOT_DIRS=("/boot/firmware" "/boot")
CONFIG=""
for dir in "${BOOT_DIRS[@]}"; do
  if [ -f "$dir/concordance.txt" ]; then
    CONFIG="$dir/concordance.txt"
    break
  fi
done

if [ -z "$CONFIG" ]; then
  echo "WARN: concordance.txt not found on boot partition."
  echo "      WiFi must be pre-configured (e.g. via Pi Imager)."
  echo "      Continuing with defaults..."
  WIFI_SSID=""
  WIFI_PASS=""
  NODE_NAME="concordance"
  PORT="8000"
  WITNESS_URL="https://concordance.run"
  OFFLINE="0"
else
  echo "Config: $CONFIG"
  # Parse config — ignore comments and blank lines
  while IFS='=' read -r key val; do
    [[ "$key" =~ ^#.*$ || -z "$key" ]] && continue
    key=$(echo "$key" | tr -d ' ')
    val=$(echo "$val" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
    case "$key" in
      WIFI_SSID)    WIFI_SSID="$val"    ;;
      WIFI_PASS)    WIFI_PASS="$val"    ;;
      NODE_NAME)    NODE_NAME="$val"    ;;
      PORT)         PORT="$val"         ;;
      WITNESS_URL)  WITNESS_URL="$val"  ;;
      OFFLINE)      OFFLINE="$val"      ;;
      REPO_URL)     REPO_URL="$val"     ;;
    esac
  done < "$CONFIG"
fi

# Defaults
NODE_NAME="${NODE_NAME:-concordance}"
PORT="${PORT:-8000}"
WITNESS_URL="${WITNESS_URL:-https://concordance.run}"
OFFLINE="${OFFLINE:-0}"
REPO_URL="${REPO_URL:-https://github.com/matharrismma/Lighthouse.git}"

# ── HOSTNAME ──────────────────────────────────────────────────────────────
echo ""
echo "── Hostname: $NODE_NAME"
echo "$NODE_NAME" > /etc/hostname
hostname "$NODE_NAME"
sed -i "s/127.0.1.1.*/127.0.1.1\t$NODE_NAME/" /etc/hosts 2>/dev/null || \
  echo "127.0.1.1	$NODE_NAME" >> /etc/hosts

# ── WIFI ──────────────────────────────────────────────────────────────────
if [ -n "${WIFI_SSID:-}" ] && [ -n "${WIFI_PASS:-}" ]; then
  echo ""
  echo "── WiFi: $WIFI_SSID"

  # Try nmcli (NetworkManager — Bookworm default)
  if command -v nmcli &>/dev/null; then
    nmcli radio wifi on 2>/dev/null || true
    nmcli dev wifi connect "$WIFI_SSID" password "$WIFI_PASS" 2>/dev/null || true
  fi

  # Fallback: wpa_supplicant config
  BOOT_FS="${CONFIG%/*}"
  WPA_FILE="$BOOT_FS/wpa_supplicant.conf"
  if [ ! -f /etc/wpa_supplicant/wpa_supplicant.conf ] || \
     ! grep -q "$WIFI_SSID" /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null; then
    cat > /etc/wpa_supplicant/wpa_supplicant.conf <<WPAEOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PASS"
    key_mgmt=WPA-PSK
}
WPAEOF
    wpa_cli -i wlan0 reconfigure 2>/dev/null || true
  fi

  # Wait for network
  echo "   Waiting for network..."
  for i in $(seq 1 30); do
    if ping -c1 -W1 8.8.8.8 &>/dev/null 2>&1; then
      echo "   Network ready (${i}s)"
      break
    fi
    sleep 2
  done
fi

# ── SYSTEM PACKAGES ───────────────────────────────────────────────────────
echo ""
echo "── Packages"
apt-get update -qq
apt-get install -y -qq \
  git python3 python3-venv python3-pip \
  avahi-daemon avahi-utils libnss-mdns \
  curl

systemctl enable avahi-daemon
systemctl start avahi-daemon || true

# ── INSTALL CONCORDANCE ───────────────────────────────────────────────────
echo ""
echo "── Concordance install"

# Use our installer with env overrides
export CONCORDANCE_PORT="$PORT"
export CONCORDANCE_WITNESS="$WITNESS_URL"

if [ -x /usr/local/bin/install.sh ]; then
  # Pre-baked image: installer already present
  bash /usr/local/bin/install.sh
else
  # Fresh image: download and run
  curl -fsSL "https://raw.githubusercontent.com/matharrismma/Lighthouse/main/local/install.sh" | bash
fi

# ── OFFLINE MODE ──────────────────────────────────────────────────────────
if [ "$OFFLINE" = "1" ]; then
  echo ""
  echo "── Offline mode: disabling outbound witness calls"
  CONFIG_ENV=/etc/concordance/config.env
  if [ -f "$CONFIG_ENV" ]; then
    sed -i 's/CONCORDANCE_OFFLINE=0/CONCORDANCE_OFFLINE=1/' "$CONFIG_ENV"
    systemctl restart concordance || true
  fi
fi

# ── BLINK LED: SUCCESS ────────────────────────────────────────────────────
# Pi ACT LED: rapid blink 5x = done
LED=/sys/class/leds/ACT
if [ -d "$LED" ]; then
  for _ in 1 2 3 4 5; do
    echo 1 > "$LED/brightness" 2>/dev/null; sleep 0.2
    echo 0 > "$LED/brightness" 2>/dev/null; sleep 0.2
  done
fi

# ── DONE ──────────────────────────────────────────────────────────────────
IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "?")
echo ""
echo "═══════════════════════════════════════════════"
echo "  Concordance node ready"
echo "  http://$NODE_NAME.local:$PORT"
echo "  http://$IP:$PORT"
echo "  Log: $LOG"
echo "═══════════════════════════════════════════════"

# ── DISABLE SELF ──────────────────────────────────────────────────────────
# Mark firstboot done so this service never runs again
touch /var/lib/concordance/.firstboot_done
systemctl disable concordance-firstboot.service
rm -f /etc/systemd/system/concordance-firstboot.service
systemctl daemon-reload

# Remove the config file from boot (contains WiFi password)
# Keep a sanitized copy in /etc/concordance/ for reference
if [ -n "$CONFIG" ]; then
  grep -v "WIFI_PASS" "$CONFIG" > /etc/concordance/node.txt 2>/dev/null || true
  # Overwrite with zeros, then delete
  python3 -c "
import os
f = open('$CONFIG', 'r+b')
f.write(b'\\x00' * os.path.getsize('$CONFIG'))
f.close()
" 2>/dev/null || true
  rm -f "$CONFIG"
fi

echo "  First boot complete. WiFi password removed from SD card."
echo "═══════════════════════════════════════════════"
