# Concordance -- Repair cloudflared service (run as Administrator)
# Use this when "cloudflared service install" fails or the service won't start

$ErrorActionPreference = "SilentlyContinue"
$Cloudflared = "C:\Concordance\cloudflared.exe"
$TokenFile   = "C:\Concordance\tunnel.token"
if (-not (Test-Path $TokenFile)) {
    Write-Host ""
    Write-Host "ERROR: $TokenFile not found." -ForegroundColor Red
    Write-Host "Run .\local\rotate_tunnel_token.ps1 first to provision a fresh tunnel token." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}
$TunnelToken = (Get-Content $TokenFile -Raw).Trim()

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
