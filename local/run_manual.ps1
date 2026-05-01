# Concordance -- Manual startup (no Windows Service needed)
# Run this in a terminal window to bring up everything without installing services.
# Keep the window open -- closing it stops the tunnel and API.

$ErrorActionPreference = "Stop"
$RepoRoot    = Split-Path $PSScriptRoot -Parent
$Cloudflared = "C:\Concordance\cloudflared.exe"
$TunnelToken = "eyJhIjoiODc4NDllMzg0OWMxZGE2YmNmMWE3MGRiM2EwMjAzMTIiLCJ0IjoiNjM1NDRiMmYtYjE0Ni00MDUzLTk5ZGYtM2UxNTNhNDY5MzQ5IiwicyI6Ik5UQTVaREkxT0RFdE9UaGxZUzAwTkRsbUxXRXpOMkl0WVRrM05ESXdZak0wT0RabSJ9"

Write-Host ""
Write-Host "=== Concordance Manual Start ===" -ForegroundColor Cyan

# Verify cloudflared
if (-not (Test-Path $Cloudflared)) {
    Write-Host "ERROR: $Cloudflared not found. Run .\local\setup.ps1 first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Set environment
$env:LEDGER_PATH             = "C:\Concordance\data\ledger.jsonl"
$env:CONCORDANCE_SCHEMA_PATH = "$RepoRoot\schema\packet.schema.json"
$env:API_KEY                 = "lh_786b9711d66ebd502ebe1d4e6b9df64a428edbaad26d81c4"
$env:PORT                    = "8000"

# Start Cloudflare Tunnel in background window
Write-Host ""
Write-Host "[1/2] Starting Cloudflare Tunnel..." -ForegroundColor Yellow
Start-Process -FilePath $Cloudflared -ArgumentList "tunnel run --token $TunnelToken" -WindowStyle Normal

Start-Sleep -Seconds 3
Write-Host "  Tunnel process launched (separate window)" -ForegroundColor Green

# Start API server in this window
Write-Host ""
Write-Host "[2/2] Starting API server on port 8000..." -ForegroundColor Yellow
Write-Host "  (Keep this window open - Ctrl+C to stop)" -ForegroundColor DarkGray
Write-Host ""

Set-Location $RepoRoot

# Check if uvicorn is available
$uvicorn = try { (Get-Command uvicorn -ErrorAction Stop).Source } catch { $null }
if ($uvicorn) {
    Write-Host "  Running: uvicorn api.app:app --host 0.0.0.0 --port 8000" -ForegroundColor Green
    uvicorn api.app:app --host 0.0.0.0 --port 8000
} else {
    Write-Host "  uvicorn not found in PATH, trying python -m uvicorn..." -ForegroundColor Yellow
    python -m uvicorn api.app:app --host 0.0.0.0 --port 8000
}
