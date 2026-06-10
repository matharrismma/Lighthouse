# setup_channel_daily.ps1 - Register the daily FAST-channel rebuild task.
#
# THE problem this fixes: the channel went dark for ~3 days (2026-05-18 ->
# 2026-05-21). Root cause: fast_channel_daily.py is meant to run "once each
# morning" to rebuild the schedule + HLS day, but nothing ran it. There was
# no scheduled task for it, so a couple of missed mornings (power outage)
# left the channel with a stale schedule and a frozen HLS feed.
#
# This registers ONE task:
#   Concordance-Channel-Daily - runs tools/fast_channel_daily.py at 4:00 AM
#     daily. Rebuilds schedule + HLS day + MRSS + EPG + now.json for every
#     channel. StartWhenAvailable means a missed run (box off at 4 AM)
#     fires as soon as the box is back - so an outage no longer darkens
#     the channel for days.
#
# Interactive logon (same as the supervision tasks) - no S4U logon-session
# errors on this single-operator box.
#
# RUN ONCE, ELEVATED PowerShell:
#   cd C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse
#   powershell -ExecutionPolicy Bypass -File .\local\setup_channel_daily.ps1
#
# Idempotent - safe to re-run anytime.

$ErrorActionPreference = 'Stop'

$REPO   = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$python = 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$script = 'tools\fast_channel_daily.py'
$user   = "$env:USERDOMAIN\$env:USERNAME"

Write-Host ''
Write-Host '=== Concordance daily channel-rebuild setup ===' -ForegroundColor Cyan

# -- sanity --
if (-not (Test-Path $python)) { throw "python not found: $python" }
if (-not (Test-Path (Join-Path $REPO $script))) { throw "script not found: $script" }

# Interactive principal - matches the supervision tasks; no S4U quirks.
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

$action = New-ScheduledTaskAction -Execute $python -Argument $script -WorkingDirectory $REPO

# 4:00 AM daily. StartWhenAvailable: a missed run (box off) fires on return.
$trigger = New-ScheduledTaskTrigger -Daily -At 4:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew

$existing = Get-ScheduledTask -TaskName 'Concordance-Channel-Daily' -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName 'Concordance-Channel-Daily' -Confirm:$false }
Register-ScheduledTask -TaskName 'Concordance-Channel-Daily' `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Rebuilds the FAST channel schedule + HLS day + MRSS/EPG each morning (4 AM).' | Out-Null
Write-Host 'Concordance-Channel-Daily registered (Interactive logon, 4:00 AM daily)' -ForegroundColor Green

Write-Host ''
Write-Host 'Run it once now to confirm it works (rebuilds today, ~5-10 min):' -ForegroundColor Yellow
Write-Host '  Start-ScheduledTask -TaskName Concordance-Channel-Daily'
Write-Host ''
Write-Host '=== Daily channel rebuild wired ===' -ForegroundColor Cyan
Write-Host '  The channel will no longer go dark from a missed morning.'
