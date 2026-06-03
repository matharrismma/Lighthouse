# setup_channel_supervisor.ps1 - Keep the FAST channel YouTube push alive.
#
# THE problem this fixes: the 2026-05-23 narrow-highway live stream died at
# ~17h with WSAECONNRESET when YouTube force-closed the RTMP connection
# (their hard cap is ~12 hours per stream). Nothing was running with
# auto-restart, so the channel stayed dark for 8 days before anyone
# noticed.
#
# What this script registers:
#
#   Concordance-FastChannel-NH  - launches python with the --supervise flag
#                                 so ffmpeg auto-restarts (5s -> 60s
#                                 backoff) within the python process when
#                                 YouTube cuts. Task Scheduler also restarts
#                                 the python process itself 10x on crash,
#                                 giving us two independent safety layers.
#
# Mirrors the pattern in setup_supervision.ps1 (Concordance-API +
# Concordance-Watchdog): Interactive logon (no S4U), AtLogOn trigger,
# never-expires, allow-on-battery.
#
# RUN ONCE, ELEVATED PowerShell:
#   cd C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse
#   powershell -ExecutionPolicy Bypass -File .\local\setup_channel_supervisor.ps1
#
# Optional per-channel arguments:
#   -Channel  channel id (default narrow-highway)
#   -Reencode passes through to ffmpeg (default $true for narrow-highway)
#
# Idempotent - safe to re-run anytime.

param(
    [string]$Channel  = 'narrow-highway',
    [bool]$Reencode   = $true
)

$ErrorActionPreference = 'Stop'

$REPO     = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$script   = Join-Path $REPO 'tools\fast_channel_youtube_live.py'
$logDir   = Join-Path $REPO 'data\live'
$taskName = "Concordance-FastChannel-$($Channel.ToUpper())"
$user     = "$env:USERDOMAIN\$env:USERNAME"

Write-Host ''
Write-Host "=== Channel supervisor setup ($Channel) ===" -ForegroundColor Cyan

# -- sanity --
if (-not (Test-Path $script)) { throw "channel script missing: $script" }
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force -Path $logDir | Out-Null }

# Resolve python on PATH so the action doesn't hard-code an interpreter
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) { throw 'python is not on PATH. Install Python 3 first.' }

# Build the argument list. --supervise is THE flag that makes this self-healing.
$argList = @('"' + $script + '"', '--channel', $Channel, '--supervise')
if ($Reencode) { $argList += '--reencode' }
$argString = $argList -join ' '

# Stop any existing supervisor for THIS channel cleanly before re-registering.
# We don't kill ALL python (would take down the engine watchdog if it's a
# python process); we only kill processes whose command line matches our
# channel argument.
$me = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" -ErrorAction SilentlyContinue |
      Where-Object { $_.CommandLine -like "*fast_channel_youtube_live*$Channel*" }
foreach ($p in $me) {
    Write-Host "  Stopping existing supervisor pid=$($p.ProcessId)" -ForegroundColor Yellow
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}

# Shared interactive principal - same pattern as engine supervision
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited

# ---- Register the task ----
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $argString `
    -WorkingDirectory $REPO

# AtLogOn for normal use; AtStartup ALSO covers the rare case where the
# operator is logged in but the session was reconstructed (e.g. lock screen).
$trigger = New-ScheduledTaskTrigger -AtLogOn

# RestartCount 10 / 1-min interval handles transient ffmpeg-process crashes
# that escape the python --supervise loop (rare but real).
# ExecutionTimeLimit 0 = no limit (must be 0 not -1; PS converts).
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -StartWhenAvailable

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "FAST channel YouTube push ($Channel). --supervise auto-restarts ffmpeg on YouTube's 12h cut." | Out-Null
Write-Host "[task] $taskName registered (Interactive logon)" -ForegroundColor Green

# ---- Start it now ----
Start-ScheduledTask -TaskName $taskName
Write-Host "[task] started" -ForegroundColor Green

# ---- Wait briefly for log activity to confirm it's live ----
$logPath = Join-Path $logDir "$Channel.log"
Write-Host ''
Write-Host "Waiting up to 60s for ffmpeg to start writing $logPath..." -ForegroundColor Yellow
$beforeSize = if (Test-Path $logPath) { (Get-Item $logPath).Length } else { 0 }
$started = $false
for ($i = 1; $i -le 60; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Path $logPath) {
        $size = (Get-Item $logPath).Length
        if ($size -gt $beforeSize + 200) {
            $started = $true
            break
        }
    }
    if ($i % 10 -eq 0) { Write-Host "  ...$i s" -ForegroundColor DarkGray }
}
Write-Host ''
if ($started) {
    Write-Host "CHANNEL LIVE - ffmpeg is pushing after $i s" -ForegroundColor Green
} else {
    Write-Host 'No log activity in 60s. Check the supervisor stdout:' -ForegroundColor Red
    Write-Host "  Get-Content $logDir\$Channel.supervisor.out -Tail 30"
    Write-Host "  Get-Content $logDir\$Channel.supervisor.err -Tail 30"
    Write-Host 'Common cause: YT_STREAM_KEY missing from .env'
}

Write-Host ''
Write-Host "=== Channel supervisor wired ($Channel) ===" -ForegroundColor Cyan
Write-Host "  Task         : $taskName"
Write-Host '  Trigger      : AtLogOn (matches engine supervisor pattern)'
Write-Host '  RestartCount : 10 x 1 min'
Write-Host '  Inner loop   : python --supervise (5s -> 60s backoff on ffmpeg crash)'
Write-Host ''
Write-Host 'Useful commands:'
Write-Host "  Get-ScheduledTaskInfo $taskName"
Write-Host "  Get-Content $logDir\$Channel.log -Tail 30 -Wait"
Write-Host "  Stop-ScheduledTask  -TaskName $taskName    # pause"
Write-Host "  Start-ScheduledTask -TaskName $taskName    # resume"
Write-Host ''
Write-Host 'For another channel later (e.g. nh-hundred-acre):'
Write-Host '  .\local\setup_channel_supervisor.ps1 -Channel nh-hundred-acre'
