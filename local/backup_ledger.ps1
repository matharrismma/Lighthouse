# Concordance — Hourly ledger backup to GitHub
# Registered by install_services.ps1 as Concordance-LedgerBackup (runs as SYSTEM)

$ErrorActionPreference = "SilentlyContinue"
$RepoRoot   = Split-Path $PSScriptRoot -Parent
$LedgerSrc  = "C:\Concordance\data\ledger.jsonl"
$LedgerDest = "$RepoRoot\data\ledger.jsonl"
$LogFile    = "C:\Concordance\logs\backup.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $LogFile -Append | Out-Null
}

Log "=== Ledger backup started ==="

# Ensure data/ directory exists in repo
New-Item -ItemType Directory -Force -Path "$RepoRoot\data" | Out-Null

# Copy ledger into repo
if (Test-Path $LedgerSrc) {
    Copy-Item -Path $LedgerSrc -Destination $LedgerDest -Force
    $lines = (Get-Content $LedgerDest | Measure-Object -Line).Lines
    Log "Copied ledger ($lines entries) → $LedgerDest"
} else {
    Log "No ledger found at $LedgerSrc — skipping"
    exit 0
}

# Git commit and push
Set-Location $RepoRoot
$changed = git status --porcelain data/ledger.jsonl
if (-not $changed) {
    Log "No changes — nothing to commit"
    exit 0
}

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
git add data/ledger.jsonl 2>&1 | ForEach-Object { Log $_ }
git commit -m "ledger: auto-backup $timestamp" 2>&1 | ForEach-Object { Log $_ }
git push 2>&1 | ForEach-Object { Log $_ }

if ($LASTEXITCODE -eq 0) {
    Log "Push succeeded"
} else {
    Log "Push failed (exit $LASTEXITCODE) — will retry next hour"
}

Log "=== Backup complete ==="
