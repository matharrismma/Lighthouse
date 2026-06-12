# Concordance -- Rotate the Cloudflare tunnel secret without deleting the tunnel.
#
# Run AS ADMINISTRATOR with your Cloudflare API token:
#   .\local\rotate_tunnel_token.ps1 -CloudflareApiToken '<your_api_token>'
#
# What it does:
#   1. PATCHes the tunnel with a freshly generated 32-byte base64 secret
#      via Cloudflare API. This invalidates the old token immediately.
#   2. Fetches the new connector token (derived from the new secret).
#   3. Saves the new token to C:\Concordance\tunnel.token (chmod-ish via ACL).
#   4. Uninstalls + reinstalls the cloudflared Windows service with the new token.
#   5. Confirms the connector is healthy and https://narrowhighway.com/health still answers.
#
# Why an API token (not your dashboard password)?
#   You can scope a token to exactly "Account → Cloudflare Tunnel → Edit" and
#   delete it the moment this script finishes. It never touches Claude's context.
#
# How to create the API token (one-time):
#   1. https://dash.cloudflare.com/profile/api-tokens
#   2. "Create Token" → "Custom token" with these permissions:
#        - Account → Cloudflare Tunnel → Edit
#      Account Resources: Include → your specific account
#   3. Continue → Create → copy the token, paste it as the -CloudflareApiToken arg.
#   4. After this script reports SUCCESS, revoke the token from the same page.

param(
    [Parameter(Mandatory = $true)]
    [string] $CloudflareApiToken,

    # Account ID is read from the CF_ACCOUNT_ID environment variable so it stays out of source control.
    [string] $AccountId  = $env:CF_ACCOUNT_ID,
    [string] $TunnelName = 'concordance',
    [string] $TokenFile  = 'C:\Concordance\tunnel.token'
)

$ErrorActionPreference = 'Stop'
if (-not $AccountId) { throw "Set CF_ACCOUNT_ID (your Cloudflare account ID) in the environment before running this script." }
$Cloudflared = 'C:\Concordance\cloudflared.exe'
$Headers = @{
    Authorization  = "Bearer $CloudflareApiToken"
    'Content-Type' = 'application/json'
}
$ApiBase = 'https://api.cloudflare.com/client/v4'

function Invoke-CF {
    param(
        [Parameter(Mandatory = $true)][string] $Method,
        [Parameter(Mandatory = $true)][string] $Path,
        [string] $Body
    )
    $args = @{
        Uri     = "$ApiBase$Path"
        Method  = $Method
        Headers = $Headers
    }
    if ($Body) { $args.Body = $Body }
    $resp = Invoke-RestMethod @args
    if (-not $resp.success) {
        $errMsg = ($resp.errors | ForEach-Object { "$($_.code): $($_.message)" }) -join '; '
        throw "Cloudflare API call failed [$Method $Path]: $errMsg"
    }
    return $resp.result
}

Write-Host ''
Write-Host '=== Concordance tunnel token rotation ===' -ForegroundColor Cyan

# -- 0. Sanity --------------------------------------------------------------
if (-not (Test-Path $Cloudflared)) {
    throw "cloudflared.exe not found at $Cloudflared. Run .\local\setup.ps1 first."
}
New-Item -ItemType Directory -Path (Split-Path $TokenFile) -Force | Out-Null

# -- 1. Find tunnel by name ------------------------------------------------
Write-Host '[1/7] Finding tunnel ...' -ForegroundColor Yellow
$tunnels = Invoke-CF -Method GET -Path "/accounts/$AccountId/cfd_tunnel?name=$TunnelName&is_deleted=false"
$tunnel  = $tunnels | Where-Object { $_.name -eq $TunnelName } | Select-Object -First 1
if (-not $tunnel) { throw "No tunnel named '$TunnelName' found in account $AccountId" }
$TunnelId = $tunnel.id
Write-Host "        Tunnel ID: $TunnelId" -ForegroundColor Green

# -- 2. Generate a new 32-byte secret --------------------------------------
Write-Host '[2/7] Generating new 32-byte tunnel secret ...' -ForegroundColor Yellow
$bytes  = New-Object byte[] 32
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
$NewSecret = [Convert]::ToBase64String($bytes)
Write-Host '        New secret generated (kept in memory only)' -ForegroundColor Green

# -- 3. PATCH tunnel with new secret ---------------------------------------
# This invalidates the old connector token immediately.
Write-Host '[3/7] Patching tunnel secret via Cloudflare API ...' -ForegroundColor Yellow
$body = (@{ tunnel_secret = $NewSecret } | ConvertTo-Json -Compress)
Invoke-CF -Method PATCH -Path "/accounts/$AccountId/cfd_tunnel/$TunnelId" -Body $body | Out-Null
Write-Host '        Old token is now invalid' -ForegroundColor Green

# -- 4. Fetch the new connector token --------------------------------------
Write-Host '[4/7] Fetching new connector token ...' -ForegroundColor Yellow
$NewToken = Invoke-CF -Method GET -Path "/accounts/$AccountId/cfd_tunnel/$TunnelId/token"
if (-not $NewToken -or $NewToken.Length -lt 50) {
    throw 'New token came back empty or suspiciously short'
}

# Persist to a single file. Lock it down to current user only.
$NewToken | Out-File -FilePath $TokenFile -Encoding ascii -NoNewline
$acl = Get-Acl $TokenFile
$acl.SetAccessRuleProtection($true, $false)  # disable inheritance
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "$env:USERDOMAIN\$env:USERNAME",
    'FullControl',
    'Allow'
)
$acl.AddAccessRule($rule)
$adminRule = New-Object System.Security.AccessControl.FileSystemAccessRule(
    'BUILTIN\Administrators',
    'FullControl',
    'Allow'
)
$acl.AddAccessRule($adminRule)
Set-Acl -Path $TokenFile -AclObject $acl
Write-Host "        New token saved to $TokenFile (private to your user)" -ForegroundColor Green

# -- 5. Reinstall cloudflared service with new token -----------------------
# Switch ErrorActionPreference to Continue for the native cloudflared calls:
# cloudflared writes informational lines like "INF Uninstalling cloudflared
# agent service..." to stderr, and under 'Stop' PowerShell would treat each
# of those as a terminating error and abort the rotation mid-way.
Write-Host '[5/7] Reinstalling cloudflared service ...' -ForegroundColor Yellow
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    Stop-Service -Name 'Cloudflared' -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    & $Cloudflared service uninstall *>&1 | Out-Null
    Start-Sleep -Seconds 2
    & $Cloudflared service install $NewToken *>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "cloudflared service install failed (exit $LASTEXITCODE). Run as Administrator?"
    }
    Start-Service -Name 'Cloudflared'
} finally {
    $ErrorActionPreference = $prevEAP
}
Write-Host '        Service reinstalled and started' -ForegroundColor Green

# -- 6. Wait for connector to reconnect ------------------------------------
Write-Host '[6/7] Waiting for connector to reattach ...' -ForegroundColor Yellow
$connected = $false
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Seconds 2
    try {
        $conns = Invoke-CF -Method GET -Path "/accounts/$AccountId/cfd_tunnel/$TunnelId/connections"
        if ($conns -and $conns.Count -gt 0) { $connected = $true; break }
    } catch {}
}
if ($connected) {
    Write-Host "        Connector active (count=$($conns.Count))" -ForegroundColor Green
} else {
    Write-Host '        Connector did not report active in 40s — check Cloudflare dashboard' -ForegroundColor Red
}

# -- 7. End-to-end probe ---------------------------------------------------
Write-Host '[7/7] Probing https://narrowhighway.com/health ...' -ForegroundColor Yellow
try {
    $h = Invoke-RestMethod 'https://narrowhighway.com/health' -TimeoutSec 8
    Write-Host "        Public /health: $($h.status), engine_available=$($h.engine_available)" -ForegroundColor Green
} catch {
    Write-Host "        Public /health failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host '        Tunnel is rotated, but the API server may need to be running too.' -ForegroundColor Yellow
}

# Scrub the token from this session's variable
$NewToken = $null
[GC]::Collect()

Write-Host ''
Write-Host '=== ROTATION COMPLETE ===' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Now do these two things by hand:' -ForegroundColor Yellow
Write-Host "  1. Revoke the API token you just used at" -ForegroundColor White
Write-Host "       https://dash.cloudflare.com/profile/api-tokens" -ForegroundColor DarkGray
Write-Host "  2. Run .\local\refactor_local_scripts.ps1 to update install_services.ps1," -ForegroundColor White
Write-Host "     diagnose.ps1, repair_cloudflared.ps1, and run_manual.ps1 to read the" -ForegroundColor White
Write-Host "     token from $TokenFile instead of having it baked in." -ForegroundColor White
Write-Host ''
