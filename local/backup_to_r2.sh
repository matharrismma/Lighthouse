#!/usr/bin/env bash
# Private, encrypted offsite backup of the Narrow Highway substrate -> Cloudflare R2.
#
# Why: the full card substrate (data/cards, ~11K files) and the seal/ledger store
# live ONLY on the node + the operator's machine -- if the node is lost, they are
# gone. This is the "can't get lost" insurance. It is PRIVATE (encrypted, a private
# bucket) -- the moat stays off public GitHub; only the code/canons/docs are public.
#
# Runs on the node (nh@nh-engine-1). No secrets in this file.
#
# ONE-TIME SETUP (operator does this; nothing here touches your keys):
#   1. Create a PRIVATE R2 bucket, e.g. "nh-backup".
#   2. Install rclone:            curl https://rclone.org/install.sh | sudo bash
#   3. Configure an R2 remote named "r2":   rclone config
#        new remote -> name: r2 -> type: s3 -> provider: Cloudflare
#        access_key_id / secret_access_key:  from an R2 API token
#        endpoint:  https://<ACCOUNT_ID>.r2.cloudflarestorage.com
#   4. Put an encryption passphrase in ~/.nh_backup_pass  (chmod 600; NOT in git).
#   5. Schedule it:   crontab -e
#        0 3 * * *  /home/nh/Lighthouse/local/backup_to_r2.sh >> /home/nh/backup.log 2>&1
#
# Restore:  rclone copy r2:nh-backup/daily/<file>.enc .  &&  \
#           openssl enc -d -aes-256-cbc -pbkdf2 -pass pass:"$(cat ~/.nh_backup_pass)" \
#             -in <file>.enc -out restore.tar.gz  &&  tar -xzf restore.tar.gz

set -euo pipefail

DATA="${NH_DATA:-/home/nh/Lighthouse/data}"
BUCKET="${NH_BUCKET:-r2:nh-backup}"
PASS_FILE="${NH_BACKUP_PASS_FILE:-$HOME/.nh_backup_pass}"
STAMP="$(date -u +%Y%m%d)"

[ -f "$PASS_FILE" ] || { echo "FATAL: passphrase file $PASS_FILE missing (see setup step 4)"; exit 1; }
command -v rclone >/dev/null || { echo "FATAL: rclone not installed (see setup step 2)"; exit 1; }
PASS="$(cat "$PASS_FILE")"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
ARCHIVE="$TMP/nh-substrate-$STAMP.tar.gz"

# Back up what lives ONLY here / is hard to regenerate: the card substrate, the
# corpus, the codex, and the seal/ledger store. Missing items are skipped, not fatal.
TARGETS=()
for d in cards almanac codex packets trust_index archetypes protocols body herbs apothecary_compounds science mind; do
  [ -e "$DATA/$d" ] && TARGETS+=("$d")
done
for f in case_store.db ledger.jsonl axis_index.json; do
  [ -e "$DATA/$f" ] && TARGETS+=("$f")
done
[ "${#TARGETS[@]}" -gt 0 ] || { echo "FATAL: nothing found under $DATA"; exit 1; }

tar -czf "$ARCHIVE" -C "$DATA" "${TARGETS[@]}"
openssl enc -aes-256-cbc -salt -pbkdf2 -pass pass:"$PASS" -in "$ARCHIVE" -out "$ARCHIVE.enc"

SIZE="$(du -h "$ARCHIVE.enc" | cut -f1)"
rclone copy "$ARCHIVE.enc" "$BUCKET/daily/"
# keep ~30 daily snapshots, prune older
rclone delete --min-age 30d "$BUCKET/daily/" || true

echo "$(date -u +%FT%TZ) backup ok: nh-substrate-$STAMP.tar.gz.enc ($SIZE) -> $BUCKET/daily/ [$(IFS=,; echo "${TARGETS[*]}")]"
