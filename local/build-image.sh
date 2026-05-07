#!/usr/bin/env bash
#
# build-image.sh — Build a flashable Concordance Pi image
# ─────────────────────────────────────────────────────────
# Produces: concordance-node-<version>-arm64.img.xz
# Ready to flash with Raspberry Pi Imager or Balena Etcher.
# User drops concordance.txt on boot drive, inserts card, powers on. Done.
#
# Requirements (Linux / WSL / GitHub Actions):
#   sudo apt-get install -y qemu-user-static binfmt-support
#   sudo apt-get install -y kpartx e2fsprogs parted wget xz-utils
#
# Usage:
#   sudo bash local/build-image.sh
#   sudo bash local/build-image.sh --version 1.2.0
#   sudo bash local/build-image.sh --repo https://github.com/yourfork/Lighthouse.git
#

set -euo pipefail

# ── ARGS ─────────────────────────────────────────────────────────────────
VERSION="${VERSION:-$(date +%Y.%m.%d)}"
REPO_URL="${REPO_URL:-https://github.com/matharrismma/Lighthouse.git}"
OUT_NAME="concordance-node-${VERSION}-arm64"
WORK_DIR="${WORK_DIR:-/tmp/concordance-build}"
KEEP_WORK="${KEEP_WORK:-0}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --version) VERSION="$2"; shift 2 ;;
    --repo)    REPO_URL="$2"; shift 2 ;;
    --work)    WORK_DIR="$2"; shift 2 ;;
    --keep)    KEEP_WORK=1; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ── COLORS ───────────────────────────────────────────────────────────────
C_CYAN='\033[0;36m'; C_GREEN='\033[0;32m'; C_BOLD='\033[1m'; C_RESET='\033[0m'
log()  { echo -e "${C_CYAN}▸${C_RESET} $*"; }
ok()   { echo -e "${C_GREEN}✓${C_RESET} $*"; }
bold() { echo -e "${C_BOLD}$*${C_RESET}"; }

# ── ROOT CHECK ────────────────────────────────────────────────────────────
[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo bash $0"; exit 1; }

# ── TOOLS CHECK ───────────────────────────────────────────────────────────
for tool in wget xz kpartx losetup parted resize2fs e2fsck qemu-aarch64-static; do
  command -v "$tool" &>/dev/null || {
    echo "Missing: $tool"
    echo "Install: sudo apt-get install -y qemu-user-static binfmt-support kpartx parted e2fsprogs wget xz-utils"
    exit 1
  }
done

# ── WORK DIR ─────────────────────────────────────────────────────────────
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"
REPO_DIR="$WORK_DIR/repo"

bold ""
bold "  Concordance Node Image Builder"
bold "  Version : $VERSION"
bold "  Repo    : $REPO_URL"
bold "  Output  : ${OUT_NAME}.img.xz"
bold "  Work    : $WORK_DIR"
bold ""

# ── STEP 1: DOWNLOAD PI OS LITE ───────────────────────────────────────────
bold "1/8  Download Raspberry Pi OS Lite (arm64)"

IMG_XZ="raspios-lite-arm64.img.xz"
if [ ! -f "$IMG_XZ" ]; then
  log "Downloading (this is the large step — ~550MB)…"
  wget -q --show-progress \
    -O "$IMG_XZ" \
    "https://downloads.raspberrypi.com/raspios_lite_arm64_latest"
  ok "Downloaded"
else
  ok "Already downloaded (cached)"
fi

log "Extracting…"
IMG_FILE="${IMG_XZ%.xz}"
[ -f "$IMG_FILE" ] || xz -dk "$IMG_XZ"
cp "$IMG_FILE" "${OUT_NAME}.img"
ok "Image ready: ${OUT_NAME}.img"

# ── STEP 2: EXPAND IMAGE ──────────────────────────────────────────────────
bold "2/8  Expand image (add 2.5GB for Concordance)"
dd if=/dev/zero bs=1M count=2560 >> "${OUT_NAME}.img" status=progress
ok "Expanded"

# ── STEP 3: MOUNT ─────────────────────────────────────────────────────────
bold "3/8  Mount partitions"

LOOP=$(losetup -f --show "${OUT_NAME}.img")
log "Loop device: $LOOP"

partprobe "$LOOP"
sleep 1
kpartx -av "$LOOP" || partprobe "$LOOP"

# Map names
LOOP_BASE=$(basename "$LOOP")
BOOT_DEV="/dev/mapper/${LOOP_BASE}p1"
ROOT_DEV="/dev/mapper/${LOOP_BASE}p2"

# Resize root partition to fill the image
log "Resizing root partition…"
# Get partition start sector
ROOT_START=$(parted -ms "$LOOP" unit s print | awk -F: '/^2:/{gsub(/s/,"",$2); print $2}')
parted -s "$LOOP" resizepart 2 100%
e2fsck -f "$ROOT_DEV"
resize2fs "$ROOT_DEV"
ok "Root partition expanded"

MOUNT_ROOT="$WORK_DIR/mnt/root"
MOUNT_BOOT="$WORK_DIR/mnt/boot"
mkdir -p "$MOUNT_ROOT" "$MOUNT_BOOT"

mount "$ROOT_DEV" "$MOUNT_ROOT"
mount "$BOOT_DEV" "$MOUNT_BOOT"
ok "Mounted at $MOUNT_ROOT + $MOUNT_BOOT"

# ── CLEANUP TRAP ─────────────────────────────────────────────────────────
cleanup() {
  echo "Cleaning up mounts…"
  umount "$MOUNT_ROOT/boot/firmware" 2>/dev/null || true
  umount "$MOUNT_BOOT"               2>/dev/null || true
  umount "$MOUNT_ROOT"               2>/dev/null || true
  kpartx -dv "$LOOP"                 2>/dev/null || true
  losetup -d "$LOOP"                 2>/dev/null || true
}
trap cleanup EXIT

# Bind /boot/firmware into rootfs (Bookworm layout)
mkdir -p "$MOUNT_ROOT/boot/firmware"
mount --bind "$MOUNT_BOOT" "$MOUNT_ROOT/boot/firmware"

# ── STEP 4: QEMU SETUP ────────────────────────────────────────────────────
bold "4/8  QEMU ARM64 emulation"
cp /usr/bin/qemu-aarch64-static "$MOUNT_ROOT/usr/bin/"

# Mount pseudo-filesystems
mount -t proc  none "$MOUNT_ROOT/proc"
mount -t sysfs none "$MOUNT_ROOT/sys"
mount -o bind /dev "$MOUNT_ROOT/dev"
mount -t devpts devpts "$MOUNT_ROOT/dev/pts"
ok "QEMU ready"

# ── STEP 5: CLONE REPO ────────────────────────────────────────────────────
bold "5/8  Clone Concordance"

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only
else
  git clone --depth 1 "$REPO_URL" "$REPO_DIR"
fi

log "Copying repo into image…"
mkdir -p "$MOUNT_ROOT/opt/concordance"
rsync -a --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='lw/' --exclude='eval/' \
  "$REPO_DIR/" "$MOUNT_ROOT/opt/concordance/"
ok "Repo copied"

# ── STEP 6: INSTALL IN CHROOT ─────────────────────────────────────────────
bold "6/8  Install Python + dependencies in chroot"

chroot "$MOUNT_ROOT" /bin/bash <<'CHROOT'
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

echo "── apt update"
apt-get update -qq

echo "── core packages"
apt-get install -y -qq \
  python3 python3-venv python3-pip \
  git curl wget \
  avahi-daemon avahi-utils libnss-mdns \
  dnsutils

echo "── Python venv"
python3 -m venv /opt/concordance/.venv

echo "── pip deps"
/opt/concordance/.venv/bin/pip install -q --upgrade pip
/opt/concordance/.venv/bin/pip install -q \
  -r /opt/concordance/api/requirements.txt \
  requests

echo "── concordance system user"
id concordance &>/dev/null || \
  useradd --system --no-create-home \
    --shell /usr/sbin/nologin \
    --home-dir /opt/concordance \
    concordance

echo "── directories"
mkdir -p /var/lib/concordance /var/log/concordance /etc/concordance /run/concordance
chown -R concordance:concordance \
  /var/lib/concordance /var/log/concordance /run/concordance
chmod 750 /etc/concordance

echo "── node key (generated at runtime on first boot)"
echo "PLACEHOLDER" > /etc/concordance/.pending_key_gen

echo "── enable avahi"
systemctl enable avahi-daemon

echo "── avahi service advertisement"
cat > /etc/avahi/services/concordance.service <<'AVAHI'
<?xml version="1.0" standalone='no'?>
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
  <name replace-wildcards="yes">Concordance on %h</name>
  <service>
    <type>_http._tcp</type>
    <port>8000</port>
    <txt-record>description=Concordance Wisdom Node</txt-record>
  </service>
</service-group>
AVAHI

echo "Done in chroot"
CHROOT

ok "Python environment ready in image"

# ── STEP 7: SYSTEM SERVICES ───────────────────────────────────────────────
bold "7/8  Install services"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# firstboot script
install -m 755 "$SCRIPT_DIR/concordance-firstboot.sh" \
  "$MOUNT_ROOT/usr/local/bin/concordance-firstboot.sh"

# firstboot systemd service
install -m 644 "$SCRIPT_DIR/concordance-firstboot.service" \
  "$MOUNT_ROOT/etc/systemd/system/concordance-firstboot.service"

# main concordance systemd service
cat > "$MOUNT_ROOT/etc/systemd/system/concordance.service" <<'SVCEOF'
[Unit]
Description=Concordance Node — Wisdom Engine
After=network-online.target concordance-firstboot.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=concordance
Group=concordance
WorkingDirectory=/opt/concordance
EnvironmentFile=/etc/concordance/config.env
ExecStart=/opt/concordance/.venv/bin/python -m uvicorn api.app:app \
    --host ${CONCORDANCE_HOST} \
    --port ${CONCORDANCE_PORT} \
    --workers 1 \
    --log-level ${CONCORDANCE_LOG_LEVEL}
Restart=on-failure
RestartSec=5
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/var/lib/concordance /var/log/concordance /run/concordance /opt/concordance/data /opt/concordance/scripts

[Install]
WantedBy=multi-user.target
SVCEOF

# Write a placeholder config.env (firstboot will replace with real values)
cat > "$MOUNT_ROOT/etc/concordance/config.env" <<'CFGEOF'
# Generated on first boot — do not edit manually
CONCORDANCE_HOST=0.0.0.0
CONCORDANCE_PORT=8000
CONCORDANCE_WITNESS_URL=https://concordance.run
CONCORDANCE_NODE_ID=pending
CONCORDANCE_NODE_KEY=/etc/concordance/node_key.json
CONCORDANCE_DATA_DIR=/opt/concordance/data
CONCORDANCE_LOG_LEVEL=info
CONCORDANCE_OFFLINE=0
CFGEOF
chmod 640 "$MOUNT_ROOT/etc/concordance/config.env"

# Copy WiFi config example to boot partition (visible without SSH)
install -m 644 "$SCRIPT_DIR/concordance.txt.example" \
  "$MOUNT_BOOT/concordance.txt.example"

# Custom README on the boot drive
cat > "$MOUNT_BOOT/CONCORDANCE-SETUP.txt" <<'README'
════════════════════════════════════════════════
 Concordance Node — Quick Start
════════════════════════════════════════════════

1. Copy  concordance.txt.example  →  concordance.txt
2. Open concordance.txt and set your WiFi credentials:
     WIFI_SSID=YourNetworkName
     WIFI_PASS=YourPassword
3. Safely eject this drive
4. Insert the SD card into your Raspberry Pi
5. Power on — wait 3-5 minutes for first boot
6. Open this URL on any device on the same WiFi:
     http://concordance.local:8000

That's it. No SSH, no terminal, no setup wizard.

═══════════════════════════════════════════════
 Stuck? Logs at /var/log/concordance-firstboot.log
 GitHub: https://github.com/matharrismma/Lighthouse
════════════════════════════════════════════════
README

# Enable services in chroot
chroot "$MOUNT_ROOT" systemctl enable concordance-firstboot.service
chroot "$MOUNT_ROOT" systemctl enable concordance.service

# Fix ownership
chroot "$MOUNT_ROOT" chown -R concordance:concordance \
  /opt/concordance /var/lib/concordance /etc/concordance 2>/dev/null || true

ok "Services installed"

# ── STEP 8: UNMOUNT + COMPRESS ────────────────────────────────────────────
bold "8/8  Unmount and compress"

# Remove QEMU binary (not needed at runtime)
rm -f "$MOUNT_ROOT/usr/bin/qemu-aarch64-static"

# Unmount pseudo-filesystems
for fs in dev/pts dev sys proc; do
  umount "$MOUNT_ROOT/$fs" 2>/dev/null || true
done

# Unmount partitions
umount "$MOUNT_ROOT/boot/firmware" 2>/dev/null || true
umount "$MOUNT_BOOT"               2>/dev/null || true
umount "$MOUNT_ROOT"               2>/dev/null || true
kpartx -dv "$LOOP"                 2>/dev/null || true
losetup -d "$LOOP"                 2>/dev/null || true

# Remove trap (we already cleaned up)
trap - EXIT

log "Compressing image (this takes 5-10 minutes)…"
xz -9 --threads=0 "${OUT_NAME}.img"
ok "Image compressed: ${OUT_NAME}.img.xz"

# Checksum
sha256sum "${OUT_NAME}.img.xz" > "${OUT_NAME}.img.xz.sha256"
ok "SHA256: $(cat ${OUT_NAME}.img.xz.sha256 | awk '{print $1}')"

# ── DONE ─────────────────────────────────────────────────────────────────
SIZE=$(du -sh "${OUT_NAME}.img.xz" | cut -f1)

bold ""
bold "  ┌─────────────────────────────────────────────────┐"
bold "  │   Concordance Pi Image ready                    │"
echo "  │                                                 │"
echo "  │   File    : ${OUT_NAME}.img.xz"
echo "  │   Size    : $SIZE"
echo "  │   SHA256  : $(cut -c1-24 ${OUT_NAME}.img.xz.sha256)…"
echo "  │                                                 │"
echo "  │   Flash with Raspberry Pi Imager                │"
echo "  │   Drop concordance.txt on boot drive            │"
echo "  │   Power on → http://concordance.local:8000      │"
bold "  └─────────────────────────────────────────────────┘"
bold ""

[ "$KEEP_WORK" = "0" ] && rm -rf "$MOUNT_ROOT" "$MOUNT_BOOT" || true
