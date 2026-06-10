# Concordance — Configure the cloudflared tunnel's public-hostname ingress
# via the Cloudflare API.
#
# Why we need this: the tunnel is HEALTHY but has no public hostname rules
# attached, so Cloudflare's edge doesn't know to send narrowhighway.com
# traffic to the tunnel. This script PUTs the ingress configuration that
# routes the whole domain to localhost:8000 (where the FastAPI engine
# serves both the static site AND the API).
#
# Run AS ADMINISTRATOR — well, doesn't strictly need admin for the API
# call, but matches the existing local-script convention.
#
# Usage:
#   .\local\configure_tunnel_ingress.ps1 -CloudflareApiToken '<token>'
#   .\local\configure_tunnel_ingress.ps1 -CloudflareApiToken '<token>' -DryRun
#
# Token scope: same as rotate_tunnel_token.ps1
#   Account -> Cloudflare Tunnel -> Edit
#   Account Resources -> Include -> Mharris.wcs@icloud.com's Account
#
# After SUCCESS, delete the API token at:
#   https://dash.cloudflare.com/profile/api-tokens

param(
    [string] $CloudflareApiToken,

    [string] $AccountId = '87849e3849c1da6bcf1a70db3a020312',
    [string] $TunnelName = 'concordance',
    [string] $Hostname = 'narrowhighway.com',
    [string] $LocalService = 'http://localhost:8000',
    [switch] $DryRun
)

$ErrorActionPreference = 'Stop'

# If no token passed on the command line, prompt for it as a SecureString so
# the value never appears in the terminal scrollback or in command history.
if (-not $CloudflareApiToken) {
    Write-Host ''
    Write-Host 'Paste your Cloudflare API token (input is hidden):' -ForegroundColor Yellow
    $secure = Read-Host -AsSecureString
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        $CloudflareApiToken = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    } finally {
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    if (-not $CloudflareApiToken) { throw 'No token provided.' }
}
$Headers = @{
    Authorization  = "Bearer $CloudflareApiToken"
    'Content-Type' = 'application/json'
}
$ApiBase = 'https://api.cloudflare.com/client/v4'

function Invoke-CF {
    param(
        [Parameter(Mandatory)][string] $Method,
        [Parameter(Mandatory)][string] $Path,
        [string] $Body
    )
    $params = @{
        Uri     = "$ApiBase$Path"
        Method  = $Method
        Headers = $Headers
    }
    if ($Body) { $params.Body = $Body }
    $resp = Invoke-RestMethod @params
    if (-not $resp.success) {
        $msg = ($resp.errors | ForEach-Object { "$($_.code): $($_.message)" }) -join '; '
        throw "Cloudflare API [$Method $Path] failed: $msg"
    }
    return $resp.result
}

Write-Host ''
Write-Host '=== Concordance tunnel ingress configuration ===' -ForegroundColor Cyan

# -- 1. Find the tunnel --------------------------------------------------
Write-Host '[1/4] Finding tunnel ...' -ForegroundColor Yellow
$tunnels  = Invoke-CF -Method GET -Path "/accounts/$AccountId/cfd_tunnel?name=$TunnelName&is_deleted=false"
$tunnel   = $tunnels | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1
if (-not $tunnel) { throw "Tunnel '$TunnelName' not found in account $AccountId." }
$TunnelId = $tunnel.id
Write-Host "       Tunnel ID: $TunnelId" -ForegroundColor Green

# -- 2. Read current ingress config (diagnostic) -------------------------
Write-Host '[2/4] Reading current ingress configuration ...' -ForegroundColor Yellow
$current = Invoke-CF -Method GET -Path "/accounts/$AccountId/cfd_tunnel/$TunnelId/configurations"
$currentIngress = $current.config.ingress
if ($currentIngress) {
    Write-Host "       Current ingress rules ($(($currentIngress | Measure-Object).Count)):" -ForegroundColor Gray
    $currentIngress | ForEach-Object {
        $h = if ($_.hostname) { $_.hostname } else { '(catch-all)' }
        $p = if ($_.path) { $_.path } else { '' }
        $s = if ($_.service) { $_.service } else { '?' }
        Write-Host "         - hostname=$h  path=$p  service=$s" -ForegroundColor Gray
    }
} else {
    Write-Host '       No ingress rules currently configured.' -ForegroundColor Gray
}

# -- 3. Build the new ingress config -------------------------------------
# Route the whole domain to the local engine; the FastAPI engine serves
# both the static site AND the API, so one rule covers everything.
$newIngress = @(
    @{
        hostname = $Hostname
        service  = $LocalService
        # Optional originRequest knobs commented; keep defaults
    },
    @{
        service = 'http_status:404'
    }
)
$configBody = @{
    config = @{
        ingress = $newIngress
        # We don't set warp-routing here — leave whatever was there
    }
}
$bodyJson = $configBody | ConvertTo-Json -Depth 8 -Compress

Write-Host ''
Write-Host '[3/4] New ingress rules to apply:' -ForegroundColor Yellow
foreach ($r in $newIngress) {
    $h = if ($r.hostname) { $r.hostname } else { '(catch-all)' }
    $s = $r.service
    Write-Host "       - hostname=$h  service=$s" -ForegroundColor White
}

if ($DryRun) {
    Write-Host ''
    Write-Host '[DRY RUN] Not writing anything. Re-run without -DryRun to apply.' -ForegroundColor Yellow
    return
}

# Apply
Invoke-CF -Method PUT -Path "/accounts/$AccountId/cfd_tunnel/$TunnelId/configurations" -Body $bodyJson | Out-Null
Write-Host '       Applied.' -ForegroundColor Green

# -- 4. Probe public /health to confirm ----------------------------------
Write-Host ''
Write-Host '[4/4] Waiting 8s for Cloudflare to propagate, then probing https://' -NoNewline -ForegroundColor Yellow
Write-Host "$Hostname" -NoNewline -ForegroundColor Cyan
Write-Host '/health ...' -ForegroundColor Yellow
Start-Sleep -Seconds 8

$probed = $false
for ($i = 0; $i -lt 6; $i++) {
    try {
        $r = Invoke-RestMethod "https://$Hostname/health" -TimeoutSec 8
        if ($r.status -eq 'ok') {
            Write-Host ''
            Write-Host '=== INGRESS CONFIGURED ===' -ForegroundColor Green
            Write-Host "  Public /health: $($r.status), engine_available=$($r.engine_available)" -ForegroundColor Green
            $probed = $true
            break
        }
    } catch {
        # Keep retrying — propagation can take 30-60s
        Start-Sleep -Seconds 5
    }
}

if (-not $probed) {
    Write-Host ''
    Write-Host 'Ingress rule was written, but public /health did not come back ok within 38s.' -ForegroundColor Yellow
    Write-Host 'Possible causes:' -ForegroundColor Yellow
    Write-Host '  1. Cloudflare propagation still in progress — retry in 30-60s:' -ForegroundColor Gray
    Write-Host "       curl https://$Hostname/health" -ForegroundColor DarkGray
    Write-Host '  2. Cloudflare Pages is still bound to the same domain and winning at the edge.' -ForegroundColor Gray
    Write-Host '     Fix: dash.cloudflare.com -> Workers & Pages -> your Pages project ->' -ForegroundColor Gray
    Write-Host '          Custom domains -> remove the narrowhighway.com binding.' -ForegroundColor Gray
    Write-Host '          (The local engine already serves the static site, so removing Pages is safe.)' -ForegroundColor Gray
    Write-Host '  3. Local engine on port 8000 is not actually running.' -ForegroundColor Gray
    Write-Host '     Check: Invoke-RestMethod http://localhost:8000/health' -ForegroundColor DarkGray
}

Write-Host ''
Write-Host 'Now go delete the API token you used at:' -ForegroundColor Yellow
Write-Host '  https://dash.cloudflare.com/profile/api-tokens' -ForegroundColor DarkGray
Write-Host ''
