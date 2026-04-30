# Concordance — One-time setup (run first, as Administrator)
# cd C:\path\to\Lighthouse
# .\local\setup.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent

Write-Host "`n=== Concordance Local Setup ===" -ForegroundColor Cyan

# 1. Python check
Write-Host "`n[1/4] Checking Python..." -ForegroundColor Yellow
try { $py = python --version 2>&1 } catch {}
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found. Install 3.11+ from https://python.org then re-run."
}
Write-Host "  $py" -ForegroundColor Green

# 2. Create persistent directories
Write-Host "`n[2/4] Creating directories..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "C:\Concordance\data" | Out-Null
New-Item -ItemType Directory -Force -Path "C:\Concordance\logs"  | Out-Null
Write-Host "  C:\Concordance\data\  (ledger lives here — never delete)" -ForegroundColor Green
Write-Host "  C:\Concordance\logs\  (server logs)" -ForegroundColor Green

# 3. Install Python dependencies
Write-Host "`n[3/4] Installing Python packages..." -ForegroundColor Yellow
Set-Location $RepoRoot
pip install -e ".[mcp]" -q
pip install -r api/requirements.txt -q
Write-Host "  Done" -ForegroundColor Green

# 4. Download cloudflared.exe
Write-Host "`n[4/4] Downloading cloudflared..." -ForegroundColor Yellow
$CloudflaredPath = "C:\Concordance\cloudflared.exe"
if (-not (Test-Path $CloudflaredPath)) {
    $url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $CloudflaredPath
    Write-Host "  Saved to $CloudflaredPath" -ForegroundColor Green
} else {
    Write-Host "  Already downloaded — skipping" -ForegroundColor Green
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next: run  .\local\install_services.ps1" -ForegroundColor Yellow
