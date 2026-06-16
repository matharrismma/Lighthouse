#!/usr/bin/env bash
# Back up the irreplaceable runtime substrate into a timestamped, rotated archive.
#
# What is irreplaceable and NOT in git (so a lost droplet = lost forever):
#   data/cas         -- the content-addressed seals / receipts (the "keeping").
#   ~/.concordance   -- the node's identity keys + physical token (SECRET; keep private).
# What is costly-but-rebuildable (full mode only -- the build scripts can regenerate it,
# but the throttled commentary fetches take hours and depend on external sources staying up):
#   lw/00_source     -- the Layer-0 databases (commentary, xrefs, scripture, lexicon, ...).
# Cards + almanac + codex are tracked in git already (off-machine backup exists); we include
# a small snapshot of codex/almanac for a coherent restore point, not as the primary copy.
#
# HONEST LIMITATION: these archives live on the SAME droplet by default -- that protects
# against accidental deletion and gives restore points, but NOT against losing the droplet.
# For true off-site safety, pull the latest archive elsewhere (see docs/BACKUP.md):
#   scp nh@nh-engine-1:'~/backups/substrate-*.tar.gz' ./offsite/
#
# Usage:  backup_substrate.sh [substrate|full]
#   substrate (default) -- small, fast; for the daily cron.
#   full                -- also archives lw/00_source (~hundreds of MB); for a weekly cron.
set -uo pipefail

ROOT="${NH_ROOT:-$HOME/Lighthouse}"
DEST="${NH_BACKUP_DIR:-$HOME/backups}"
KEEP="${NH_BACKUP_KEEP:-14}"
MODE="${1:-substrate}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$DEST"

# Build the include list from paths that actually exist (skip missing ones quietly).
ROOT_PATHS=()
for p in data/cas data/codex data/almanac; do
  [ -e "$ROOT/$p" ] && ROOT_PATHS+=("$p")
done
HOME_PATHS=()
for p in .concordance; do
  [ -e "$HOME/$p" ] && HOME_PATHS+=("$p")
done

if [ "$MODE" = "full" ]; then
  ARCHIVE="$DEST/full-$STAMP.tar.gz"
  [ -e "$ROOT/lw/00_source" ] && ROOT_PATHS+=("lw/00_source")
else
  ARCHIVE="$DEST/substrate-$STAMP.tar.gz"
fi

# Archive: root-relative paths from $ROOT, then home-relative paths from $HOME.
TAR_ARGS=( -czf "$ARCHIVE" )
[ ${#ROOT_PATHS[@]} -gt 0 ] && TAR_ARGS+=( -C "$ROOT" "${ROOT_PATHS[@]}" )
[ ${#HOME_PATHS[@]} -gt 0 ] && TAR_ARGS+=( -C "$HOME" "${HOME_PATHS[@]}" )
tar "${TAR_ARGS[@]}"
rc=$?
if [ $rc -ne 0 ] || [ ! -s "$ARCHIVE" ]; then
  echo "$(date -u +%FT%TZ) BACKUP FAILED ($MODE) rc=$rc" >&2
  exit 1
fi
chmod 600 "$ARCHIVE"   # contains node keys -- keep private

SIZE="$(du -h "$ARCHIVE" | cut -f1)"
echo "$(date -u +%FT%TZ) backup ok: $ARCHIVE ($SIZE) [${ROOT_PATHS[*]} ${HOME_PATHS[*]:-}]"

# Rotate: keep the most recent $KEEP of this mode's archives.
PREFIX="$([ "$MODE" = "full" ] && echo full || echo substrate)"
ls -1t "$DEST/$PREFIX"-*.tar.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f -- "$old" && echo "$(date -u +%FT%TZ) rotated out: $old"
done
