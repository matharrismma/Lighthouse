# Concordance -- Finish a token rotation that aborted partway.
#
# Use this when rotate_tunnel_token.ps1 succeeded in writing the new token
# to C:\Concordance\tunnel.token but failed during the cloudflared service
# reinstall (typically because PowerShell wrapped a stderr line as a
# terminating exception).
#
# Run as Administrator:
#   .\local\finish_rotation.ps1

# IMPORTANT: 'Continue' (not 'Stop'). Cloudflared writes informational
# messages to stderr; under ErrorActionPreference='Stop' those get wrapped
# as terminating errors and abort the script. We handle exit codes
# explicitly instead.
$ErrorActionPreference = 'Continue'

$Cloudflared = 'C:\Concordance\cloudflared.exe'
$TokenFile   = 'C:\Concordance\tunnel.token'

Write-Host ''
Write-Host '=== Finishing tunnel rotation ===' -ForegroundColor Cyan

# 0a. Must be elevated. cloudflared service install talks to SCManager,
#     which silently exits 1 from a non-admin shell.
$isAdmin = ([Security.Principal.WindowsPrincipal] `
            [Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host ''
    Write-Host 'ERROR: This script must run as Administrator.' -ForegroundColor Red
    Write-Host '       cloudflared service install requires admin to register a Windows service.' -ForegroundColor Yellow
    Write-Host ''
    Write-Host 'Open PowerShell as Administrator (Start menu -> right-click PowerShell ->' -ForegroundColor White
    Write-Host '"Run as administrator"), cd to this folder, and re-run this script.' -ForegroundColor White
    Write-Host ''
    exit 1
}

# 0b. Sanity
if (-not (Test-Path $Cloudflared)) { Write-Host "Missing $Cloudflared" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $TokenFile))   { Write-Host "Missing $TokenFile -- rotation didn't get far enough; rerun rotate_tunnel_token.ps1" -ForegroundColor Red; exit 1 }
$NewToken = (Get-Content $TokenFile -Raw).Trim()
if (-not $NewToken) { Write-Host "Token file is empty" -ForegroundColor Red; exit 1 }
Write-Host '[0/4] Admin ok, token file present' -ForegroundColor Green

# 1. Make sure no service is half-installed
Write-Host '[1/4] Stopping any existing cloudflared service ...' -ForegroundColor Yellow
$svc = Get-Service Cloudflared -ErrorAction SilentlyContinue
if ($svc) {
    if ($svc.Status -eq 'Running') {
        Stop-Service Cloudflared -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}
# Try a clean uninstall before reinstalling. Show output so any error is
# visible. Failure here is fine -- the service may already be gone.
Write-Host '        cloudflared service uninstall output:' -ForegroundColor DarkGray
& $Cloudflared service uninstall *>&1 | ForEach-Object { Write-Host "          $_" -ForegroundColor DarkGray }
Start-Sleep -Seconds 2
Write-Host '        Cleared' -ForegroundColor Green

# 2. Install with the new token. Show the output so errors are visible.
Write-Host '[2/4] Installing cloudflared service with new token ...' -ForegroundColor Yellow
Write-Host '        cloudflared service install output:' -ForegroundColor DarkGray
& $Cloudflared service install $NewToken *>&1 | ForEach-Object { Write-Host "          $_" -ForegroundColor DarkGray }
$installExit = $LASTEXITCODE
if ($installExit -ne 0) {
    Write-Host ''
    Write-Host "        cloudflared service install exited $installExit" -ForegroundColor Red
    Write-Host '        (output above should explain why)' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '        Common causes:' -ForegroundColor Yellow
    Write-Host '          - Service still partially registered. Try:' -ForegroundColor DarkGray
    Write-Host '              sc.exe delete Cloudflared' -ForegroundColor White
    Write-Host '            then re-run this script.' -ForegroundColor DarkGray
    Write-Host '          - Token contains stray whitespace. Token starts with eyJ?' -ForegroundColor DarkGray
    exit 1
}
Start-Service Cloudflared
Start-Sleep -Seconds 3
$status = (Get-Service Cloudflared).Status
Write-Host "        Service status: $status" -ForegroundColor $(if ($status -eq 'Running') { 'Green' } else { 'Red' })

# 3. Wait for the connector to reattach (poll Cloudflare-side via cloudflared)
Write-Host '[3/4] Waiting for connector to reach the edge ...' -ForegroundColor Yellow
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    # cloudflared tunnel info needs the cred file or a list call; instead
    # we just probe through the tunnel itself.
    try {
        $r = Invoke-WebRequest 'https://narrowhighway.com/health' -TimeoutSec 4 -UseBasicParsing
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch {}
}
if ($ready) {
    Write-Host '        narrowhighway.com is answering' -ForegroundColor Green
} else {
    Write-Host '        narrowhighway.com did not answer in 40s' -ForegroundColor Red
    Write-Host '        Cloudflare dashboard: tunnel concordance should show 1 healthy connector' -ForegroundColor Yellow
}

# 4. Final report
Write-Host '[4/4] Final state:' -ForegroundColor Yellow
try {
    $h = Invoke-RestMethod 'https://narrowhighway.com/health' -TimeoutSec 5
    Write-Host "        /health: $($h.status), engine_available=$($h.engine_available), entries=$($h.ledger_entries)" -ForegroundColor Green
} catch {
    Write-Host "        /health unreachable: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ''
Write-Host '=== Done ===' -ForegroundColor Cyan
Write-Host ''
Write-Host "Don't forget to revoke the API token at https://dash.cloudflare.com/profile/api-tokens" -ForegroundColor Yellow
Write-Host ''
