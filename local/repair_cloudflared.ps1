# Concordance -- Repair cloudflared service (run as Administrator)
# Use this when "cloudflared service install" fails or the service won't start

$ErrorActionPreference = "SilentlyContinue"
$Cloudflared = "C:\Concordance\cloudflared.exe"
$TunnelToken = "eyJhIjoiODc4NDllMzg0OWMxZGE2YmNmMWE3MGRiM2EwMjAzMTIiLCJ0IjoiNjM1NDRiMmYtYjE0Ni00MDUzLTk5ZGYtM2UxNTNhNDY5MzQ5IiwicyI6Ik5UQTVaREkxT0RFdE9UaGxZUzAwTkRsbUxXRXpOMkl0WVRrM05ESXdZak0wT0RabSJ9"

Write-Host ""
Write-Host "=== Repairing Cloudflared Service ===" -ForegroundColor Cyan

if (-not (Test-Path $Cloudflared)) {
    Write-Host ""
    Write-Host "ERROR: $Cloudflared not found." -ForegroundColor Red
    Write-Host "Downloading cloudflared..." -ForegroundColor Yellow
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $Cloudflared
    Write-Host "  Downloaded to $Cloudflared" -ForegroundColor Green
}

Write-Host ""
Write-Host "[1/4] Stopping existing Cloudflared service..." -ForegroundColor Yellow
Stop-Service "Cloudflared" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "[2/4] Uninstalling existing service (clears broken state)..." -ForegroundColor Yellow
$uninstallOutput = & $Cloudflared service uninstall 2>&1
Write-Host "  $uninstallOutput" -ForegroundColor Gray
Start-Sleep -Seconds 2

Write-Host "[3/4] Installing service with tunnel token..." -ForegroundColor Yellow
$installOutput = & $Cloudflared service install $TunnelToken 2>&1
Write-Host "  $installOutput" -ForegroundColor Gray

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Service install failed (exit $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "  This may happen if not running as Administrator." -ForegroundColor Yellow
    Write-Host "  Right-click PowerShell -> Run as Administrator, then retry." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Alternatively, run the tunnel manually (no service needed):" -ForegroundColor Cyan
    Write-Host "  .\local\run_manual.ps1" -ForegroundColor White
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[4/4] Starting Cloudflared service..." -ForegroundColor Yellow
Start-Service "Cloudflared" -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

$status = (Get-Service "Cloudflared" -ErrorAction SilentlyContinue).Status
Write-Host ""
if ($status -eq "Running") {
    Write-Host "=== Cloudflared service is RUNNING ===" -ForegroundColor Green
    Write-Host ""
    Write-Host "Tunnel is active. If narrowhighway.com still doesn't resolve," -ForegroundColor White
    Write-Host "make sure the API server is also running:" -ForegroundColor White
    Write-Host "  Start-ScheduledTask 'Concordance-API'" -ForegroundColor DarkGray
    Write-Host "  (or run: .\local\run_manual.ps1)" -ForegroundColor DarkGray
} else {
    Write-Host "  Service status: $status" -ForegroundColor Red
    Write-Host ""
    Write-Host "  Service still not running. Check the Windows Event Log:" -ForegroundColor Yellow
    Write-Host "  Get-EventLog -LogName System -Source '*cloudflare*' -Newest 5" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Fallback -- run the tunnel manually instead:" -ForegroundColor Cyan
    Write-Host "  .\local\run_manual.ps1" -ForegroundColor White
}

Write-Host ""
Read-Host "Press Enter to exit"
