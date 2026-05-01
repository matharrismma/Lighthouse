# Concordance -- Install all auto-start services (run as Administrator after setup.ps1)
#
# What this does:
#   1. Installs cloudflared as a Windows Service (tunnel: concordance -> narrowhighway.com)
#   2. Registers the API server (uvicorn) as a Task Scheduler task (starts on boot)
#   3. Registers an hourly ledger backup task
#
# Tunnel "concordance" was created 2026-04-30 in Cloudflare Zero Trust.

$ErrorActionPreference = "Stop"
$RepoRoot    = Split-Path $PSScriptRoot -Parent
$LogDir      = "C:\Concordance\logs"
$Cloudflared = "C:\Concordance\cloudflared.exe"

# Tunnel token -- keep this file private
$TunnelToken = "eyJhIjoiODc4NDllMzg0OWMxZGE2YmNmMWE3MGRiM2EwMjAzMTIiLCJ0IjoiNjM1NDRiMmYtYjE0Ni00MDUzLTk5ZGYtM2UxNTNhNDY5MzQ5IiwicyI6Ik5UQTVaREkxT0RFdE9UaGxZUzAwTkRsbUxXRXpOMkl0WVRrM05ESXdZak0wT0RabSJ9"

Write-Host ""
Write-Host "=== Installing Concordance Services ===" -ForegroundColor Cyan

# Verify cloudflared was downloaded by setup.ps1
if (-not (Test-Path $Cloudflared)) {
    Write-Host "ERROR: $Cloudflared not found. Run .\local\setup.ps1 first." -ForegroundColor Red
    exit 1
}

# -- 1. Cloudflare Tunnel (Windows Service) --
Write-Host ""
Write-Host "[1/3] Installing Cloudflare Tunnel service..." -ForegroundColor Yellow
& $Cloudflared service install $TunnelToken
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: cloudflared service install failed (exit $LASTEXITCODE)." -ForegroundColor Red
    exit 1
}
Start-Service -Name "Cloudflared"
Write-Host "  Service 'Cloudflared' installed and started" -ForegroundColor Green
Write-Host "  Tunnel: concordance -> narrowhighway.com" -ForegroundColor Green

# -- 2. API Server (Task Scheduler, starts on boot) --
Write-Host ""
Write-Host "[2/3] Registering API server task..." -ForegroundColor Yellow

# NOTE: Do NOT use (Get-Command python).Source here -- on some systems that resolves
# to the Windows Store stub which has no packages. Instead write a script that
# discovers a working Python at runtime.
$ApiLauncher = @"
`$env:LEDGER_PATH             = 'C:\Concordance\data\ledger.jsonl'
`$env:CONCORDANCE_SCHEMA_PATH = '$RepoRoot\schema\packet.schema.json'
`$env:API_KEY                 = 'lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4'
`$env:PORT                    = '8000'
Set-Location '$RepoRoot'

# Ensure log directory exists
if (-not (Test-Path '$LogDir')) {
    New-Item -ItemType Directory -Path '$LogDir' -Force | Out-Null
}

# Find python with uvicorn - try PATH first, then common locations
`$python = `$null
foreach (`$candidate in @('python', 'python3', 'py')) {
    try {
        `$ver = & `$candidate --version 2>&1
        `$uvCheck = & `$candidate -c "import uvicorn" 2>&1
        if (`$LASTEXITCODE -eq 0) { `$python = `$candidate; break }
    } catch {}
}

if (-not `$python) {
    "ERROR: No python with uvicorn found" | Tee-Object -FilePath '$LogDir\server.log' -Append
    exit 1
}

"Starting uvicorn with `$python at `$(Get-Date)" | Tee-Object -FilePath '$LogDir\server.log' -Append
& `$python -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 1 2>&1 | Tee-Object -FilePath '$LogDir\server.log' -Append
"@
Set-Content -Path "C:\Concordance\start_server.ps1" -Value $ApiLauncher -Encoding UTF8

$Action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NonInteractive -WindowStyle Hidden -File C:\Concordance\start_server.ps1"
$Trigger   = New-ScheduledTaskTrigger -AtStartup
$Settings  = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName "Concordance-API" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "  Task 'Concordance-API' registered (SYSTEM, restarts on crash)" -ForegroundColor Green

Start-ScheduledTask -TaskName "Concordance-API"
Start-Sleep -Seconds 4
$health = try { (Invoke-RestMethod http://localhost:8000/health).status } catch { "starting..." }
Write-Host "  Health: $health" -ForegroundColor Green

# -- 3. Ledger Backup (hourly) --
Write-Host ""
Write-Host "[3/3] Registering ledger backup task..." -ForegroundColor Yellow

$BackupAction   = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NonInteractive -WindowStyle Hidden -File '$RepoRoot\local\backup_ledger.ps1'"
$BackupTrigger  = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Hours 1) -Once -At (Get-Date)
$BackupSettings = New-ScheduledTaskSettingsSet

Register-ScheduledTask -TaskName "Concordance-LedgerBackup" -Action $BackupAction -Trigger $BackupTrigger -Settings $BackupSettings -Principal $Principal -Force | Out-Null
Write-Host "  Task 'Concordance-LedgerBackup' registered (every hour)" -ForegroundColor Green

# -- Done --
Write-Host ""
Write-Host "=== All services installed ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Status:" -ForegroundColor White
Write-Host "  Get-Service Cloudflared" -ForegroundColor DarkGray
Write-Host "  Get-ScheduledTask Concordance-API" -ForegroundColor DarkGray
Write-Host "  Invoke-RestMethod http://localhost:8000/health" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Logs: C:\Concordance\logs\" -ForegroundColor DarkGray
Write-Host ""
Write-Host "REMINDER: finish the route in Cloudflare dashboard if not done yet." -ForegroundColor Yellow
Write-Host "  Zero Trust -> Networks -> Connectors -> concordance" -ForegroundColor DarkGray
Write-Host "  Public Hostnames -> Add: narrowhighway.com -> HTTP -> localhost:8000" -ForegroundColor DarkGray
