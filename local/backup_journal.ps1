# Concordance — Journal/data backup
#
# Snapshots the engine's stateful data to a date-stamped folder under
# C:\Concordance\backups\, then keeps the last 30 dailies and prunes
# older ones. Idempotent — safe to run from cron, scheduled task, or
# by hand.
#
# Backed up:
#   data/                                  — journal, keeping log,
#                                            trust_index, CAS, swarm
#                                            config, grid connections
#   lw/journal/  lw/keeping/  lw/quarantine/ — legacy stores (if any)
#   ledger.jsonl                           — top-level audit chain
#   data/swarm_trainer_state.json          — cooldown persistence
#
# Run as the same user the engine runs as (no admin needed).
# Default schedule: daily at 03:00 — install via
#   schtasks /create /TN "Concordance-Backup" /SC DAILY /ST 03:00 ^
#            /TR "powershell -ExecutionPolicy Bypass -File C:\...\backup_journal.ps1"

$ErrorActionPreference = 'Stop'

# -- 0. Paths ---------------------------------------------------------
$RepoRoot   = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$BackupRoot = 'C:\Concordance\backups'
$KeepDays   = 30

if (-not (Test-Path $RepoRoot)) {
    Write-Host "[!] Repo not found: $RepoRoot" -ForegroundColor Red
    exit 1
}

# Date-stamped folder; if it already exists today, append a time tag
$Stamp = Get-Date -Format 'yyyy-MM-dd'
$DestDir = Join-Path $BackupRoot $Stamp
if (Test-Path $DestDir) {
    $Stamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
    $DestDir = Join-Path $BackupRoot $Stamp
}
New-Item -ItemType Directory -Path $DestDir -Force | Out-Null

Write-Host ""
Write-Host "=== Concordance backup ===" -ForegroundColor Cyan
Write-Host "Source : $RepoRoot"
Write-Host "Dest   : $DestDir"
Write-Host ""

# -- 1. Snapshot data/ ------------------------------------------------
$Data = Join-Path $RepoRoot 'data'
if (Test-Path $Data) {
    $size = (Get-ChildItem $Data -Recurse -File | Measure-Object Length -Sum).Sum
    Write-Host ("[1/4] data/             {0:N1} MB" -f ($size / 1MB)) -ForegroundColor Green
    Copy-Item -Path $Data -Destination (Join-Path $DestDir 'data') -Recurse -Force
} else {
    Write-Host "[1/4] data/             (not present, skipped)" -ForegroundColor Yellow
}

# -- 2. Legacy lw/ stores (if present) -------------------------------
$LwBacked = $false
foreach ($sub in @('journal','keeping','quarantine')) {
    $src = Join-Path $RepoRoot ('lw\' + $sub)
    if (Test-Path $src) {
        if (-not $LwBacked) {
            New-Item -ItemType Directory -Path (Join-Path $DestDir 'lw') -Force | Out-Null
            $LwBacked = $true
        }
        Copy-Item -Path $src -Destination (Join-Path $DestDir ('lw\' + $sub)) -Recurse -Force
    }
}
if ($LwBacked) {
    Write-Host "[2/4] lw/{journal,keeping,quarantine}  copied" -ForegroundColor Green
} else {
    Write-Host "[2/4] lw/...            (not present, skipped)" -ForegroundColor Yellow
}

# -- 3. Top-level ledger.jsonl + key configs --------------------------
$Singles = @(
    'ledger.jsonl',
    'case_store.db',
    'data\swarm_trainer_state.json',
    'data\swarm_config.json',
    'data\grid_connections.jsonl'
)
$copied = 0
foreach ($rel in $Singles) {
    $src = Join-Path $RepoRoot $rel
    if (Test-Path $src) {
        $relDir = Split-Path $rel -Parent
        if ($relDir) {
            $destSub = Join-Path $DestDir $relDir
            New-Item -ItemType Directory -Path $destSub -Force | Out-Null
        }
        Copy-Item -Path $src -Destination (Join-Path $DestDir $rel) -Force
        $copied++
    }
}
Write-Host "[3/4] singletons        $copied/$($Singles.Count) copied" -ForegroundColor Green

# -- 4. Compress + checksum --------------------------------------------
$Zip = "$DestDir.zip"
Compress-Archive -Path "$DestDir\*" -DestinationPath $Zip -CompressionLevel Optimal -Force
$ZipSize = (Get-Item $Zip).Length
$Hash = (Get-FileHash -Path $Zip -Algorithm SHA256).Hash
Write-Host ("[4/4] archive           {0}   {1:N1} MB" -f (Split-Path $Zip -Leaf), ($ZipSize / 1MB)) -ForegroundColor Green
Write-Host "       sha256          $Hash"

# Drop the unzipped folder once compressed (saves space)
Remove-Item $DestDir -Recurse -Force

# -- 5. Rotate — keep last $KeepDays archives -------------------------
$archives = Get-ChildItem $BackupRoot -Filter '*.zip' | Sort-Object LastWriteTime -Descending
$kept = $archives | Select-Object -First $KeepDays
$pruned = $archives | Select-Object -Skip $KeepDays
foreach ($p in $pruned) { Remove-Item $p.FullName -Force }

Write-Host ""
Write-Host "Retained : $($kept.Count) archives" -ForegroundColor Cyan
Write-Host "Pruned   : $($pruned.Count) archives" -ForegroundColor Cyan
$totalSize = ($archives | Measure-Object Length -Sum).Sum
Write-Host ("Total    : {0:N1} MB on disk" -f ($totalSize / 1MB)) -ForegroundColor Cyan
Write-Host ""
Write-Host "OK" -ForegroundColor Green
