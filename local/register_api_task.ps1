# register_api_task.ps1 - Register the Concordance-API scheduled task.
#
# Uses Interactive logon (not S4U) so it can be registered WITHOUT
# elevation. An Interactive task runs whenever the user is logged in,
# which on this single-operator desktop is always. Trade-off vs S4U:
# the task does not run when no one is logged on - acceptable here.
#
# This gives the watchdog a real restart target.
#
# Run: powershell -ExecutionPolicy Bypass -File .\local\register_api_task.ps1

$ErrorActionPreference = 'Stop'
$TaskName = 'Concordance-API'

$Action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument '-NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File C:\Concordance\start_server.ps1'
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -RestartCount 10 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew

# Interactive principal - no elevation needed to register
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName `
    -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null

$t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($t) {
    Write-Host "OK: Concordance-API task registered (state=$($t.State), logon=Interactive)" -ForegroundColor Green
} else {
    Write-Host "FAILED: task not found after registration." -ForegroundColor Red
}
