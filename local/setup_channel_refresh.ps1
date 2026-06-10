# setup_channel_refresh.ps1 -- register the FAST-channel refresh as a Windows
# scheduled task that runs every 3 hours, so the channel keeps widening on its
# own as the encoder finishes more content.
#
# Run this ONCE, elevated (Run as administrator):
#   powershell -NoProfile -ExecutionPolicy Bypass -File "<this file>"
#
# To stop it later:
#   Unregister-ScheduledTask -TaskName "NarrowHighway-ChannelRefresh"

$ErrorActionPreference = "Stop"

$refresh = Join-Path $PSScriptRoot "refresh_channel.ps1"
if (-not (Test-Path $refresh)) {
    Write-Host "ERROR: refresh_channel.ps1 not found next to this script." -ForegroundColor Red
    exit 1
}

$taskName = "NarrowHighway-ChannelRefresh"

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument ('-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{0}"' -f $refresh)

# Fire once shortly from now, then repeat every 3 hours, indefinitely.
$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(3)) `
    -RepetitionInterval (New-TimeSpan -Hours 3)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description ("Regenerate the Narrow Highway FAST-channel concat list and restart the " +
                  "YouTube push so the channel keeps widening as the encoder finishes content.") `
    -Force | Out-Null

Write-Host ""
Write-Host "Registered scheduled task '$taskName'." -ForegroundColor Green
Write-Host "  Runs every 3 hours. First run in ~3 minutes." -ForegroundColor Cyan
Write-Host "  It only restarts the push when there is genuinely more content," -ForegroundColor Cyan
Write-Host "  so most runs are a silent no-op with no stream blip." -ForegroundColor Cyan
Write-Host "  Log: data\live\refresh.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "Stop it later with:" -ForegroundColor DarkGray
Write-Host ("  Unregister-ScheduledTask -TaskName " + '"' + $taskName + '"') -ForegroundColor DarkGray
