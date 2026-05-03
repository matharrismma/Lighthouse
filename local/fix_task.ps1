# Concordance -- Fix Concordance-API scheduled task
# Run as Administrator

$ErrorActionPreference = "Stop"
$RepoRoot = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"
$LogDir   = "C:\Concordance\logs"
$Python   = "C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe"

# Verify python exists at expected path
if (-not (Test-Path $Python)) {
    Write-Host "ERROR: Python not found at $Python" -ForegroundColor Red
    Write-Host "Run: python -c `"import sys; print(sys.executable)`" and update this script." -ForegroundColor Yellow
    exit 1
}

# Write corrected start_server.ps1 with hardcoded Python path
$Script = @"
`$env:LEDGER_PATH             = 'C:\Concordance\data\ledger.jsonl'
`$env:CONCORDANCE_SCHEMA_PATH = '$RepoRoot\schema\packet.schema.json'
`$env:API_KEY                 = 'lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4'
`$env:PORT                    = '8000'
Set-Location '$RepoRoot'

if (-not (Test-Path '$LogDir')) {
    New-Item -ItemType Directory -Path '$LogDir' -Force | Out-Null
}

"Starting uvicorn at `$(Get-Date)" | Tee-Object -FilePath '$LogDir\server.log' -Append
& '$Python' -m uvicorn api.app:app --host 0.0.0.0 --port 8000 --workers 1 2>&1 | Tee-Object -FilePath '$LogDir\server.log' -Append
"@

Set-Content -Path "C:\Concordance\start_server.ps1" -Value $Script -Encoding UTF8
Write-Host "  start_server.ps1 updated (Python: $Python)" -ForegroundColor Green

# Re-register the task
$Action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NonInteractive -WindowStyle Hidden -File C:\Concordance\start_server.ps1"
$Trigger   = New-ScheduledTaskTrigger -AtStartup
$Settings  = New-ScheduledTaskSettingsSet -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$Principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\hdven" -LogonType S4U -RunLevel Highest

Register-ScheduledTask -TaskName "Concordance-API" -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force | Out-Null
Write-Host "  Task re-registered" -ForegroundColor Green

# Start it
Start-ScheduledTask -TaskName "Concordance-API"
Start-Sleep -Seconds 8

$info = Get-ScheduledTaskInfo -TaskName "Concordance-API"
Write-Host "  LastTaskResult: $($info.LastTaskResult)" -ForegroundColor $(if ($info.LastTaskResult -eq 0) { 'Green' } else { 'Red' })

$health = try { (Invoke-RestMethod http://localhost:8000/health).status } catch { "not responding" }
Write-Host "  Health: $health" -ForegroundColor $(if ($health -eq 'ok') { 'Green' } else { 'Red' })
