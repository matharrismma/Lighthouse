# setup_supervision.ps1 - Wire up bulletproof engine supervision in one shot.
#
# THE problem this fixes: the engine has gone down every few hours all
# project long. Root causes found 2026-05-20:
#   1. go_live.ps1 polled /health for only 30s; a 13s cold import balloons
#      past 30s under load, so the script declared false failure.
#   2. The Concordance-API + Concordance-Watchdog tasks used S4U logon,
#      which throws 0x80070520 ("logon session does not exist") on this box.
#   3. With no working task, nothing auto-restarted a crashed engine.
#
# This script registers BOTH tasks with INTERACTIVE logon (runs while the
# operator is logged in - always true on this single-operator desktop;
# no S4U, no logon-session errors, no stored password).
#
#   Concordance-API       - runs C:\Concordance\start_server.ps1 at logon;
#                           Task Scheduler restarts it 10x on crash.
#   Concordance-Watchdog  - runs local\watchdog.ps1; pings /health every 60s;
#                           after 3 fails, kills stale python and relaunches
#                           the engine (via the task, or directly if needed).
#
# Two independent layers: the task restarts fast crashes; the watchdog
# catches hangs the task can't see (process alive but not serving).
#
# RUN ONCE, ELEVATED PowerShell:
#   cd C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse
#   powershell -ExecutionPolicy Bypass -File .\local\setup_supervision.ps1
#
# Idempotent - safe to re-run anytime.

$ErrorActionPreference = 'Stop'

$REPO        = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$starter     = 'C:\Concordance\start_server.ps1'
$watchdog    = Join-Path $REPO 'local\watchdog.ps1'
$user        = "$env:USERDOMAIN\$env:USERNAME"

Write-Host ''
Write-Host '=== Concordance supervision setup ===' -ForegroundColor Cyan

# -- sanity --
if (-not (Test-Path $starter)) {
    Write-Host "WARNING: $starter not found." -ForegroundColor Yellow
    Write-Host "Run .\local\go_live.ps1 once first to write start_server.ps1, or" -ForegroundColor Yellow
    Write-Host "the Concordance-API task will have nothing to launch." -ForegroundColor Yellow
}
if (-not (Test-Path $watchdog)) { throw "watchdog script missing: $watchdog" }

# Shared interactive principal - no S4U, no elevation quirks at runtime
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

# ---- 1. Concordance-API ----------------------------------------------
$apiAction = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$starter`""
$apiTrigger = New-ScheduledTaskTrigger -AtLogOn
$apiSettings = New-ScheduledTaskSettingsSet `
    -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -StartWhenAvailable

$existing = Get-ScheduledTask -TaskName 'Concordance-API' -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName 'Concordance-API' -Confirm:$false }
Register-ScheduledTask -TaskName 'Concordance-API' `
    -Action $apiAction -Trigger $apiTrigger -Settings $apiSettings -Principal $principal `
    -Description 'Concordance engine (uvicorn on :8000). Restarts 10x on crash.' | Out-Null
Write-Host '[1/2] Concordance-API registered (Interactive logon)' -ForegroundColor Green

# ---- 2. Concordance-Watchdog -----------------------------------------
$wdAction = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchdog`""
$wdBoot  = New-ScheduledTaskTrigger -AtLogOn
$wdEvery = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$wdSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$existingW = Get-ScheduledTask -TaskName 'Concordance-Watchdog' -ErrorAction SilentlyContinue
if ($existingW) { Unregister-ScheduledTask -TaskName 'Concordance-Watchdog' -Confirm:$false }
Register-ScheduledTask -TaskName 'Concordance-Watchdog' `
    -Action $wdAction -Trigger @($wdBoot, $wdEvery) -Settings $wdSettings -Principal $principal `
    -Description 'Watchdog: pings /health every 60s; auto-restarts the engine after 3 fails.' | Out-Null
Write-Host '[2/2] Concordance-Watchdog registered (Interactive logon)' -ForegroundColor Green

# ---- 3. Start both ----------------------------------------------------
# Stop anything on port 8000 so the task owns it cleanly
$port = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
foreach ($p in ($port.OwningProcess | Sort-Object -Unique)) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 2

Start-ScheduledTask -TaskName 'Concordance-API'
Start-ScheduledTask -TaskName 'Concordance-Watchdog'
Write-Host ''
Write-Host 'Both tasks started.' -ForegroundColor Green

# ---- 4. Wait for health (180s window - cold import is ~13s, more under load) ----
Write-Host ''
Write-Host 'Waiting for /health (cold start ~15-40s; window 180s)...' -ForegroundColor Yellow
$ok = $false
for ($i = 1; $i -le 180; $i++) {
    Start-Sleep -Seconds 1
    if ($i % 15 -eq 0) { Write-Host "  ...$i s" -ForegroundColor DarkGray }
    try {
        $r = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 3
        if ($r.status -eq 'ok') { $ok = $true; break }
    } catch {}
}
Write-Host ''
if ($ok) {
    Write-Host "ENGINE LIVE - /health ok after $i s" -ForegroundColor Green
} else {
    Write-Host 'Engine did not answer in 180s. Check C:\Concordance\logs\server.log' -ForegroundColor Red
}

Write-Host ''
Write-Host '=== Supervision wired ===' -ForegroundColor Cyan
Write-Host '  Concordance-API      - engine; Task Scheduler restarts 10x on crash'
Write-Host '  Concordance-Watchdog - pings /health every 60s; restarts after 3 fails'
Write-Host '  Both: Interactive logon (no S4U logon-session errors), AtLogOn trigger'
Write-Host ''
Write-Host 'Watch the watchdog:  Get-Content C:\Concordance\logs\watchdog.log -Wait'
Write-Host 'Watch the engine:    Get-Content C:\Concordance\logs\server.log -Wait'
