# Concordance -- Diagnostics (run as Administrator)
# Tells you exactly what is broken and why

$ErrorActionPreference = "SilentlyContinue"
$Cloudflared = "C:\Concordance\cloudflared.exe"
$TunnelToken = "eyJhIjoiODc4NDllMzg0OWMxZGE2YmNmMWE3MGRiM2EwMjAzMTIiLCJ0IjoiNjM1NDRiMmYtYjE0Ni00MDUzLTk5ZGYtM2UxNTNhNDY5MzQ5IiwicyI6Ik5UQTVaREkxT0RFdE9UaGxZUzAwTkRsbUxXRXpOMkl0WVRrM05ESXdZak0wT0RabSJ9"

Write-Host ""
Write-Host "=== Concordance Diagnostics ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "--- cloudflared.exe ---" -ForegroundColor Yellow
if (Test-Path $Cloudflared) {
    $ver = & $Cloudflared --version 2>&1
    Write-Host "  FOUND: $Cloudflared" -ForegroundColor Green
    Write-Host "  Version: $ver" -ForegroundColor Green
} else {
    Write-Host "  MISSING: $Cloudflared" -ForegroundColor Red
    Write-Host "  Fix: run .\local\setup.ps1 as Administrator to download it" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "--- Cloudflared Windows Service ---" -ForegroundColor Yellow
$svc = Get-Service "Cloudflared" -ErrorAction SilentlyContinue
if ($null -eq $svc) {
    Write-Host "  NOT INSTALLED (no service named 'Cloudflared')" -ForegroundColor Red
} else {
    Write-Host "  Status:      $($svc.Status)" -ForegroundColor $(if ($svc.Status -eq "Running") {"Green"} else {"Red"})
    Write-Host "  StartType:   $($svc.StartType)" -ForegroundColor Gray
    Write-Host "  DisplayName: $($svc.DisplayName)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "--- Windows Event Log (cloudflared, last 5 errors) ---" -ForegroundColor Yellow
$events = Get-EventLog -LogName Application -Source "*cloudflared*" -EntryType Error,Warning -Newest 5 -ErrorAction SilentlyContinue
if ($events) {
    foreach ($e in $events) {
        Write-Host "  [$($e.TimeGenerated)] $($e.Message.Substring(0,[Math]::Min(120,$e.Message.Length)))" -ForegroundColor Red
    }
} else {
    Write-Host "  No cloudflared errors in Application log" -ForegroundColor Gray
}

Write-Host ""
Write-Host "--- Concordance-API Task Scheduler ---" -ForegroundColor Yellow
$task = Get-ScheduledTask "Concordance-API" -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "  NOT REGISTERED" -ForegroundColor Red
} else {
    $info = Get-ScheduledTaskInfo "Concordance-API" -ErrorAction SilentlyContinue
    Write-Host "  State:        $($task.State)" -ForegroundColor $(if ($task.State -eq "Running") {"Green"} else {"Yellow"})
    Write-Host "  LastRun:      $($info.LastRunTime)" -ForegroundColor Gray
    Write-Host "  LastResult:   $($info.LastTaskResult)" -ForegroundColor $(if ($info.LastTaskResult -eq 0) {"Green"} else {"Red"})
}

Write-Host ""
Write-Host "--- Port 8000 (API server) ---" -ForegroundColor Yellow
$port = netstat -ano 2>$null | Select-String ":8000"
if ($port) {
    Write-Host "  IN USE (API server is running):" -ForegroundColor Green
    $port | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
} else {
    Write-Host "  NOT IN USE (API server is NOT running)" -ForegroundColor Red
}

Write-Host ""
Write-Host "--- API Health (localhost:8000) ---" -ForegroundColor Yellow
$health = try { (Invoke-RestMethod http://localhost:8000/health -TimeoutSec 3).status } catch { "UNREACHABLE" }
Write-Host "  /health: $health" -ForegroundColor $(if ($health -eq "ok") {"Green"} else {"Red"})

Write-Host ""
Write-Host "--- C:\Concordance\ contents ---" -ForegroundColor Yellow
if (Test-Path "C:\Concordance") {
    Get-ChildItem "C:\Concordance" -Recurse | Select-Object FullName, Length | Format-Table -AutoSize | Out-String | Write-Host
} else {
    Write-Host "  MISSING: C:\Concordance does not exist" -ForegroundColor Red
    Write-Host "  Fix: run .\local\setup.ps1 as Administrator" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== End diagnostics ===" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"
