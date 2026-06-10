# Concordance -- One-shot "go live" script.
# Run as Administrator from the Lighthouse folder:
#   cd C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse
#   powershell -ExecutionPolicy Bypass -File .\local\go_live.ps1
#
# What it does (idempotent):
#   1. Ensures C:\Concordance\data and C:\Concordance\logs exist
#   2. Writes a clean start_server.ps1 (UTF-8 logging, no PS error noise)
#   3. Re-registers the Concordance-API scheduled task
#        - runs as the current user (so it can read your OneDrive folder)
#        - LogonType S4U (no password needed, runs while you're logged in)
#        - RunLevel Limited (so you can query Get-ScheduledTaskInfo from a normal shell)
#        - restarts on crash, no time limit
#   4. Ensures the Cloudflared service is running
#   5. Stops any stray python on port 8000, starts the task
#   6. Hits /health locally AND through https://narrowhighway.com to confirm

$ErrorActionPreference = 'Stop'

# -- 0. Sanity --------------------------------------------------------------
$RepoRoot = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"
$LogDir   = "C:\Concordance\logs"
$DataDir  = "C:\Concordance\data"
$Python   = "C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$ApiKey   = "lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4"
$TaskName = "Concordance-API"

if (-not (Test-Path $RepoRoot))  { throw "Repo not found: $RepoRoot" }
if (-not (Test-Path $Python))    { throw "Python not found: $Python" }

Write-Host ""
Write-Host "=== Concordance go-live ===" -ForegroundColor Cyan

# -- 1. Folders -------------------------------------------------------------
New-Item -ItemType Directory -Path $LogDir,$DataDir -Force | Out-Null
Write-Host "[1/6] Folders ready" -ForegroundColor Green

# -- 2. Clean start_server.ps1 ---------------------------------------------
# Important: $ErrorActionPreference='Continue' + *>&1 + Out-File -Encoding utf8
# avoids PowerShell wrapping uvicorn's stderr lines as RemoteException records,
# and avoids the UTF-16 BOM that Tee-Object would otherwise emit.
$SchemaPath = Join-Path $RepoRoot 'schema\packet.schema.json'
$LedgerPath = Join-Path $DataDir  'ledger.jsonl'
$LogPath    = Join-Path $LogDir   'server.log'

$Script = @"
`$ErrorActionPreference = 'Continue'

`$env:LEDGER_PATH             = '$LedgerPath'
`$env:CONCORDANCE_SCHEMA_PATH = '$SchemaPath'
`$env:API_KEY                 = '$ApiKey'
`$env:PORT                    = '8000'

# Load secrets from repo .env (gitignored). Picks up any KEY=value
# lines: ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID,
# CONCORDANCE_PASSPHRASE, SECRET_KEY, etc. Hardcoded vars above win
# on conflict; .env adds, never overrides API_KEY/PORT/etc.
`$envFile = '$RepoRoot\.env'
if (Test-Path `$envFile) {
    Get-Content `$envFile -Encoding utf8 | ForEach-Object {
        `$line = `$_.Trim()
        if (`$line -and `$line -notmatch '^\s*#' -and `$line -match '^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)`$') {
            `$name = `$Matches[1]
            `$value = `$Matches[2].Trim()
            # Strip surrounding single or double quotes
            if (`$value -match '^"(.*)"`$' -or `$value -match "^'(.*)'`$") { `$value = `$Matches[1] }
            # Don't overwrite vars set above
            if (-not (Test-Path "env:`$name")) {
                Set-Item -Path "env:`$name" -Value `$value
            }
        }
    }
}

Set-Location '$RepoRoot'
if (-not (Test-Path '$LogDir')) { New-Item -ItemType Directory -Path '$LogDir' -Force | Out-Null }

"=== uvicorn start at `$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" |
    Out-File -FilePath '$LogPath' -Append -Encoding utf8

& '$Python' -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 1 *>&1 |
    Out-File -FilePath '$LogPath' -Append -Encoding utf8
"@

Set-Content -Path 'C:\Concordance\start_server.ps1' -Value $Script -Encoding utf8
Write-Host "[2/6] start_server.ps1 written (UTF-8, clean stderr capture)" -ForegroundColor Green

# -- 3. Re-register the scheduled task -------------------------------------
# RunLevel Limited so a non-elevated shell can still query Get-ScheduledTaskInfo.
# Port 8000 is unprivileged, so this is fine.
$Action    = New-ScheduledTaskAction -Execute 'powershell.exe' `
              -Argument '-NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Concordance\start_server.ps1'
$Trigger   = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$Settings  = New-ScheduledTaskSettingsSet `
              -RestartCount 10 `
              -RestartInterval (New-TimeSpan -Minutes 1) `
              -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
              -AllowStartIfOnBatteries `
              -DontStopIfGoingOnBatteries
$Principal = New-ScheduledTaskPrincipal `
              -UserId "$env:USERDOMAIN\$env:USERNAME" `
              -LogonType S4U `
              -RunLevel Limited

# Stop any existing instance before re-registering
try { Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue } catch {}
Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "[3/6] Task '$TaskName' registered (user-run, S4U, Limited)" -ForegroundColor Green

# -- 4. Cloudflared service ------------------------------------------------
$svc = Get-Service Cloudflared -ErrorAction SilentlyContinue
if ($null -eq $svc) {
    Write-Host "[4/6] WARNING: Cloudflared service is not installed." -ForegroundColor Yellow
    Write-Host "       Run .\local\install_services.ps1 (or .\local\repair_cloudflared.ps1)" -ForegroundColor Yellow
} else {
    if ($svc.Status -ne 'Running') {
        Start-Service Cloudflared
        Start-Sleep -Seconds 2
    }
    Write-Host "[4/6] Cloudflared service: $((Get-Service Cloudflared).Status)" -ForegroundColor Green
}

# -- 5. Free port 8000 and start the task ----------------------------------
$port = (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)
if ($port) {
    foreach ($p in ($port.OwningProcess | Sort-Object -Unique)) {
        try { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } catch {}
    }
    Start-Sleep -Seconds 1
}

Start-ScheduledTask -TaskName $TaskName
Write-Host "[5/6] Task started, waiting for /health ..." -ForegroundColor Yellow

$ok = $false
# Engine first cold-start takes ~60-120s (fastapi + pydantic imports + warmer
# initial pass). Polling for 180s avoids false-negative "NOT RESPONDING" reports.
# Print a heartbeat every 30s so the operator knows we're still waiting.
$elapsed = 0
for ($i = 0; $i -lt 180; $i++) {
    Start-Sleep -Seconds 1
    $elapsed++
    if ($elapsed % 30 -eq 0) {
        Write-Host "        ... still waiting ($elapsed s elapsed; cold-start can take up to 120s)" -ForegroundColor DarkGray
    }
    try {
        $r = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 2
        if ($r.status -eq 'ok') { $ok = $true; break }
    } catch {}
}
if ($ok) {
    Write-Host "        Local /health: ok (engine_available=$($r.engine_available); $elapsed s to bind)" -ForegroundColor Green
} else {
    Write-Host "        Local /health: NOT RESPONDING after 180s" -ForegroundColor Red
    Write-Host "        Check the log: $LogPath" -ForegroundColor Yellow
}

# -- 6. End-to-end check through Cloudflare --------------------------------
Write-Host "[6/6] Checking https://narrowhighway.com/health ..." -ForegroundColor Yellow
try {
    $public = Invoke-RestMethod 'https://narrowhighway.com/health' -TimeoutSec 8
    Write-Host "        Public  /health: $($public.status) (entries=$($public.ledger_entries))" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== LIVE: https://narrowhighway.com ===" -ForegroundColor Cyan
} catch {
    Write-Host "        Public /health: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "        If local /health worked but public didn't, the tunnel route" -ForegroundColor Yellow
    Write-Host "        in Cloudflare Zero Trust still needs narrowhighway.com -> http://localhost:8000." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Status anytime:" -ForegroundColor DarkGray
Write-Host "  Get-ScheduledTaskInfo $TaskName" -ForegroundColor DarkGray
Write-Host "  Get-Service Cloudflared" -ForegroundColor DarkGray
Write-Host "  Invoke-RestMethod http://localhost:8000/health" -ForegroundColor DarkGray
Write-Host "  Invoke-RestMethod https://narrowhighway.com/health" -ForegroundColor DarkGray
Write-Host ""
