# Concordance - off-site backup
# Daily snapshot of the audit chain + content-addressed store + almanac.
#
# Why off-site: a hard drive failure, ransomware, or a stolen laptop
# would otherwise erase the engine's permanent record. Backblaze B2's
# free tier covers 10 GB of storage and 1 GB/day of egress - more than
# enough for our footprint (ledger ~ KB, CAS measured in MB).
#
# Pulls keys from C:\Concordance\.env (B2_KEY_ID, B2_APPLICATION_KEY,
# B2_BUCKET). All three must be set; if any is missing we exit 0 with
# a warning rather than failing - the engine should keep running even
# if backups are misconfigured.
#
# Schedule daily at 3am:
#   schtasks /Create /SC DAILY /TN "Concordance-Backup" /TR "powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse\local\backup_offsite.ps1" /ST 03:00

$ErrorActionPreference = 'Continue'
$RepoRoot   = Split-Path $PSScriptRoot -Parent
$BackupDir  = 'C:\Concordance\backups'
$Timestamp  = Get-Date -Format 'yyyyMMdd-HHmmss'
$ArchiveName = "concordance-backup-$Timestamp.tar.gz"
$ArchivePath = Join-Path $BackupDir $ArchiveName

if (-not (Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null }

# -- Load secrets from C:\Concordance\.env --------------------------------
$primaryEnv  = 'C:\Concordance\.env'
function Get-EnvValue {
    param([string]$Name)
    if (-not (Test-Path $primaryEnv)) { return $null }
    foreach ($line in (Get-Content $primaryEnv -Encoding utf8)) {
        $t = $line.Trim()
        if ($t -and $t -notmatch '^\s*#' -and $t -match "^$Name\s*=\s*(.*)$") {
            $v = $Matches[1].Trim()
            if ($v -match '^"(.*)"$' -or $v -match "^'(.*)'$") { $v = $Matches[1] }
            return $v
        }
    }
    return $null
}

$b2KeyId  = Get-EnvValue 'B2_KEY_ID'
$b2AppKey = Get-EnvValue 'B2_APPLICATION_KEY'
$b2Bucket = Get-EnvValue 'B2_BUCKET'

# -- Build archive --------------------------------------------------------
Write-Host "backup: building archive $ArchiveName"

$dataPaths = @(
    'data/ledger.jsonl',
    'data/cas',
    'data/almanac',
    'data/visits',
    'data/synthesis_patterns.jsonl',
    'data/axis_index.json',
    'data/packets',
    'data/trust_index'
)
$existing = $dataPaths | Where-Object { Test-Path (Join-Path $RepoRoot $_) }

if (-not $existing) {
    Write-Host 'backup: nothing to back up - skipping' -ForegroundColor Yellow
    exit 0
}

# Use tar.exe (built into Windows 10+). Run from RepoRoot so paths in
# the archive are relative.
Push-Location $RepoRoot
try {
    & tar.exe -czf $ArchivePath $existing 2>&1 | Out-Null
} finally {
    Pop-Location
}

if (-not (Test-Path $ArchivePath)) {
    Write-Host 'backup: tar.exe failed - bailing' -ForegroundColor Red
    exit 1
}

$size = (Get-Item $ArchivePath).Length
Write-Host ("backup: archive built {0} KB" -f [math]::Round($size/1KB,1))

# -- Upload to Backblaze B2 -----------------------------------------------
$b2Cmd = Get-Command b2.exe -ErrorAction SilentlyContinue
if (-not $b2Cmd) { $b2Cmd = Get-Command b2 -ErrorAction SilentlyContinue }

if (-not $b2Cmd) {
    Write-Host 'backup: b2 CLI not installed - keeping local archive only.' -ForegroundColor Yellow
    Write-Host '        Install with: pip install b2' -ForegroundColor DarkGray
} elseif (-not $b2KeyId -or -not $b2AppKey -or -not $b2Bucket) {
    Write-Host 'backup: B2 keys not set in C:\Concordance\.env - local-only.' -ForegroundColor Yellow
    Write-Host '        Add B2_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET to .env' -ForegroundColor DarkGray
} else {
    Write-Host "backup: uploading to b2://$b2Bucket/$ArchiveName"
    $env:B2_APPLICATION_KEY_ID = $b2KeyId
    $env:B2_APPLICATION_KEY    = $b2AppKey
    & $b2Cmd.Source authorize-account $b2KeyId $b2AppKey *>$null
    & $b2Cmd.Source upload-file $b2Bucket $ArchivePath $ArchiveName 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host 'backup: uploaded ok'
    } else {
        Write-Host "backup: upload failed (exit $LASTEXITCODE) - local archive kept" -ForegroundColor Yellow
    }
}

# -- Prune local archives (keep last 14) ----------------------------------
$archives = Get-ChildItem $BackupDir -Filter 'concordance-backup-*.tar.gz' |
    Sort-Object LastWriteTime -Descending
if ($archives.Count -gt 14) {
    $archives | Select-Object -Skip 14 | ForEach-Object {
        Write-Host ("backup: pruning local {0}" -f $_.Name)
        Remove-Item $_.FullName -Force
    }
}

Write-Host 'backup: done.'
