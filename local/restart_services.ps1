# Concordance -- Restart all services (run as Administrator)
$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "=== Restarting Concordance Services ===" -ForegroundColor Cyan

Write-Host ""
Write-Host "[1/2] Cloudflare Tunnel (cloudflared service)..." -ForegroundColor Yellow
$svc = Get-Service "Cloudflared" -ErrorAction SilentlyContinue
if ($null -eq $svc) {
    Write-Host "  ERROR: Cloudflared service not found." -ForegroundColor Red
    Write-Host "  Run .\local\install_services.ps1 as Administrator first." -ForegroundColor Red
} else {
    if ($svc.Status -eq "Running") {
        Restart-Service "Cloudflared" -Force
        Write-Host "  Restarted (was running)" -ForegroundColor Green
    } else {
        Start-Service "Cloudflared"
        Write-Host "  Started (was stopped)" -ForegroundColor Green
    }
    Start-Sleep -Seconds 2
    $status = (Get-Service "Cloudflared").Status
    Write-Host "  Status: $status" -ForegroundColor $(if ($status -eq "Running") { "Green" } else { "Red" })
}

Write-Host ""
Write-Host "[2/2] API Server (Concordance-API task)..." -ForegroundColor Yellow
$task = Get-ScheduledTask "Concordance-API" -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "  ERROR: Concordance-API task not found." -ForegroundColor Red
    Write-Host "  Run .\local\install_services.ps1 as Administrator first." -ForegroundColor Red
} else {
    $taskState = $task.State
    if ($taskState -eq "Running") {
        Stop-ScheduledTask "Concordance-API" -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
    Start-ScheduledTask "Concordance-API"
    Write-Host "  Task started" -ForegroundColor Green
}

Write-Host ""
Write-Host "Waiting 6s for API to come up..." -ForegroundColor DarkGray
Start-Sleep -Seconds 6

$health = try {
    $r = Invoke-RestMethod http://localhost:8000/health -TimeoutSec 5
    $r.status
} catch {
    "not responding yet"
}

Write-Host ""
if ($health -eq "ok") {
    Write-Host "  API health: $health" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== All services running ===" -ForegroundColor Cyan
    Write-Host "  narrowhighway.com should be live within 30 seconds." -ForegroundColor Green
} else {
    Write-Host "  API health: $health" -ForegroundColor Yellow
    Write-Host "  API is still starting up, or port 8000 is blocked." -ForegroundColor Yellow
    Write-Host "  Check logs: C:\Concordance\logs\server.log" -ForegroundColor DarkGray
}

Write-Host ""
Read-Host "Press Enter to exit"
