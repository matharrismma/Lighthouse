# setup_watchdog.ps1 — Register the watchdog as a scheduled task.
#
# Run once, elevated PowerShell:
#   .\local\setup_watchdog.ps1
#
# Effect:
#   * Registers `Concordance-Watchdog` scheduled task
#   * Runs at boot + every 5 minutes (re-launches if process dies)
#   * Runs as your user, S4U logon type (no password stored)
#   * The watchdog script itself loops forever; the 5-min schedule is
#     belt + suspenders in case the watchdog ever dies
#
# Stop: Get-ScheduledTask -TaskName 'Concordance-Watchdog' | Disable-ScheduledTask
# Remove: Unregister-ScheduledTask -TaskName 'Concordance-Watchdog' -Confirm:$false

$ErrorActionPreference = 'Stop'

$TaskName = 'Concordance-Watchdog'
$REPO = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$watchdogPath = Join-Path $REPO 'local\watchdog.ps1'

if (-not (Test-Path $watchdogPath)) {
    throw "watchdog script not found: $watchdogPath"
}

# Unregister existing task with the same name (idempotent setup)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed prior task $TaskName" -ForegroundColor Yellow
}

# Action: run powershell with the watchdog script
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$watchdogPath`""

# Triggers: at startup + every 5 minutes (latter is the "if the watchdog dies, restart it" safety net)
$boot = New-ScheduledTaskTrigger -AtStartup
$every5 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger @($boot, $every5) `
    -Settings $settings `
    -Principal $principal `
    -Description "Watchdog: pings /health every minute; auto-restarts Concordance-API after 3 consecutive failures."

Write-Host ""
Write-Host "=== Watchdog registered ===" -ForegroundColor Green
Write-Host "  Task name:  $TaskName"
Write-Host "  Script:     $watchdogPath"
Write-Host "  Logs:       C:\Concordance\logs\watchdog.log"
Write-Host ""
Write-Host "Start it now:" -ForegroundColor Yellow
Write-Host "  Start-ScheduledTask -TaskName $TaskName"
Write-Host ""
Write-Host "Watch the log:"
Write-Host "  Get-Content C:\Concordance\logs\watchdog.log -Wait"
Write-Host ""
Write-Host "Behavior:"
Write-Host "  * Pings http://localhost:8000/health every 60s"
Write-Host "  * After 3 consecutive fails (~3 min): kills stale python, restarts engine task, waits 180s for cold-start"
Write-Host "  * Logs every check + every restart"
Write-Host "  * Rotates log when it exceeds 10 MB"
