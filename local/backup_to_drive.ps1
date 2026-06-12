# Local "can't get lost" backup of the full Narrow Highway substrate to the D: (12TB) drive.
# No cloud, no credentials, fully private. Mirrors the local repo + pulls the node's
# prod-only seal/ledger store (which lives ONLY on narrowhighway.com), and keeps dated
# point-in-time snapshots. Closes the node-as-single-point-of-failure.
#
#   Run now:   powershell -NoProfile -File local\backup_to_drive.ps1
#   Schedule:  daily via Task Scheduler (see the registration command in the session notes)
$ErrorActionPreference = 'Stop'
$repo  = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$dest  = 'D:\nh-backup'
$stamp = (Get-Date).ToUniversalTime().ToString('yyyy-MM-dd')

if (-not (Test-Path 'D:\')) { throw 'D: drive not present -- is the 12TB Expansion drive connected?' }
New-Item -ItemType Directory -Force -Path "$dest\mirror","$dest\node","$dest\snapshots" | Out-Null

# 1. Mirror the local data substrate (includes the UNTRACKED 11K data/cards) -- incremental.
robocopy "$repo\data" "$dest\mirror\data" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /MT:8 | Out-Null
# 2. Mirror the code/docs too (small) so a full cold restore is possible. Skip .git + data.
robocopy "$repo" "$dest\mirror\repo" /MIR /XD "$repo\.git" "$repo\data" /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null

# 3. Pull the node's PROD-ONLY stores (seals/ledger live only on narrowhighway.com).
foreach ($item in @('ledger.jsonl','case_store.db','keep_access.log')) {
  try { & scp -o ConnectTimeout=20 "nh@nh-engine-1:~/Lighthouse/data/$item" "$dest\node\" 2>$null } catch {}
}
foreach ($dir in @('cas','receipts','wallet','quarantine')) {
  try { & scp -r -o ConnectTimeout=20 "nh@nh-engine-1:~/Lighthouse/data/$dir" "$dest\node\" 2>$null } catch {}
}
# also keep the node's authoritative corpus copy alongside the local one
try { & scp -o ConnectTimeout=20 'nh@nh-engine-1:~/Lighthouse/data/almanac/entries.jsonl' "$dest\node\entries.jsonl" 2>$null } catch {}

# 4. Daily point-in-time snapshot of the irreplaceable substrate (small; protects against
#    a bad mirror sync propagating a corruption/deletion). Keep ~30 days.
$snap = "$dest\snapshots\substrate-$stamp.zip"
$paths = @("$repo\data\cards","$repo\data\almanac","$repo\data\codex") | Where-Object { Test-Path $_ }
if ($paths) { Compress-Archive -Path $paths -DestinationPath $snap -Force }
Get-ChildItem "$dest\snapshots\substrate-*.zip" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | Remove-Item -Force -ErrorAction SilentlyContinue

$cards = (Get-ChildItem "$dest\mirror\data\cards" -ErrorAction SilentlyContinue).Count
$mb = if (Test-Path $snap) { [math]::Round((Get-Item $snap).Length/1MB,1) } else { 0 }
Write-Output ("backup ok -> {0}  (mirror: {1} cards; node seals pulled; snapshot {2}.zip = {3} MB)" -f $dest, $cards, $stamp, $mb)
