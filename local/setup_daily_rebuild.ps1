# setup_daily_rebuild.ps1 — Wire daily MRSS/EPG/schedule rebuild into Windows Task Scheduler.
#
# Runs every morning at 04:00 local time:
#   1. python tools/duration_cache.py --warm  (refresh duration cache; fast after first warm)
#   2. python tools/fast_channel_schedule.py --channel content/channels/narrow_highway.json
#      → produces today's schedule + epg.xml + now.json + mrss.xml + roku_feed.json
#   3. python tools/roku_submission_package.py  (refresh roku_feed.json)
#
# Output: daily rotation of tomorrow's schedule, EPG that Plex/Roku/Jellyfin
# pull every morning, and a fresh now-playing manifest.
#
# Logs: C:\Concordance\logs\daily_rebuild_<YYYYMMDD>.log
#
# Run once, elevated PowerShell:
#   .\local\setup_daily_rebuild.ps1

$ErrorActionPreference = 'Stop'

# Where the repo lives — adjust if you ever move it
$REPO = 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'
$PY   = 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$LOGDIR = 'C:\Concordance\logs'
$TASK_NAME = 'NarrowHighway-DailyRebuild'

if (-not (Test-Path $LOGDIR)) {
    New-Item -ItemType Directory -Path $LOGDIR -Force | Out-Null
}

# Write the runner script — this is what the scheduled task actually invokes
$runnerPath = 'C:\Concordance\daily_rebuild.ps1'
$runnerBody = @'
$ErrorActionPreference = 'Continue'
$stamp = Get-Date -Format 'yyyy-MM-dd'
$log = "C:\Concordance\logs\daily_rebuild_$stamp.log"
"=== Daily rebuild starting $(Get-Date) ===" | Out-File -FilePath $log -Append -Encoding utf8

Set-Location 'C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse'

# 1. Refresh duration cache (fast after first warm)
"-- step 1: duration cache --" | Out-File $log -Append -Encoding utf8
& 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools\duration_cache.py --warm *>&1 |
    Out-File $log -Append -Encoding utf8

# 2. Rebuild today's schedule + EPG + now.json
"-- step 2: fast_channel_schedule --" | Out-File $log -Append -Encoding utf8
$today = Get-Date -Format 'yyyy-MM-dd'
& 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools\fast_channel_schedule.py `
    --channel content\channels\narrow_highway.json --date $today *>&1 |
    Out-File $log -Append -Encoding utf8

# 3. Refresh the Roku JSON feed
"-- step 3: roku_submission_package --" | Out-File $log -Append -Encoding utf8
& 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools\roku_submission_package.py *>&1 |
    Out-File $log -Append -Encoding utf8

# 4. Rebuild the per-card sitemap so new witness-passed cards become crawlable
"-- step 4: build_full_sitemap --" | Out-File $log -Append -Encoding utf8
& 'C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe' tools\build_full_sitemap.py *>&1 |
    Out-File $log -Append -Encoding utf8

"=== Daily rebuild finished $(Get-Date) ===" | Out-File $log -Append -Encoding utf8
'@

Set-Content -Path $runnerPath -Value $runnerBody -Encoding utf8
Write-Host "Wrote runner: $runnerPath"

# Unregister an existing task with the same name (idempotent setup)
$existing = Get-ScheduledTask -TaskName $TASK_NAME -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TASK_NAME -Confirm:$false
    Write-Host "Removed prior task $TASK_NAME"
}

# Register the new task
$action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runnerPath`""

$trigger = New-ScheduledTaskTrigger -Daily -At 04:00

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TASK_NAME `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Narrow Highway: rebuild daily schedule, EPG, MRSS, Roku JSON feed every morning at 04:00."

Write-Host ""
Write-Host "=== Task scheduled: $TASK_NAME ==="
Write-Host "  Runs daily at 04:00 local time"
Write-Host "  Runner script: $runnerPath"
Write-Host "  Logs:          $LOGDIR\daily_rebuild_YYYY-MM-DD.log"
Write-Host ""
Write-Host "To run it now (test):"
Write-Host "  Start-ScheduledTask -TaskName $TASK_NAME"
Write-Host ""
Write-Host "To see status:"
Write-Host "  Get-ScheduledTaskInfo -TaskName $TASK_NAME"
