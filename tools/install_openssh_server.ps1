# install_openssh_server.ps1
# Installs and configures Windows OpenSSH Server on port 22.
# Runs as Administrator. Idempotent — safe to re-run.

$ErrorActionPreference = 'Stop'

Write-Host "================================================================"
Write-Host "  OpenSSH Server install — Narrow Highway"
Write-Host "================================================================"
Write-Host ""

# --- 1. Install the Windows capability ---
Write-Host "[1/5] Installing OpenSSH Server capability ..."
$cap = Get-WindowsCapability -Online -Name OpenSSH.Server*
if ($cap.State -eq 'Installed') {
    Write-Host "      Already installed."
} else {
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0 | Out-Null
    Write-Host "      Installed."
}

# --- 2. Service: start + auto-start ---
Write-Host "[2/5] Configuring sshd service ..."
Set-Service -Name sshd -StartupType Automatic
if ((Get-Service sshd).Status -ne 'Running') {
    Start-Service sshd
}
Write-Host "      sshd: $((Get-Service sshd).Status), StartType: $((Get-Service sshd).StartType)"

# --- 3. Firewall rule on port 22 ---
Write-Host "[3/5] Configuring firewall ..."
$rule = Get-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -Name 'OpenSSH-Server-In-TCP' `
        -DisplayName 'OpenSSH Server (sshd)' `
        -Enabled True -Direction Inbound -Protocol TCP `
        -Action Allow -LocalPort 22 | Out-Null
    Write-Host "      Rule created."
} else {
    if (-not $rule.Enabled) {
        Enable-NetFirewallRule -Name 'OpenSSH-Server-In-TCP'
        Write-Host "      Rule enabled."
    } else {
        Write-Host "      Rule already exists and enabled."
    }
}

# --- 4. Default shell = PowerShell (not cmd) ---
Write-Host "[4/5] Setting default SSH shell to PowerShell ..."
$psPath = "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
$regPath = "HKLM:\SOFTWARE\OpenSSH"
if (-not (Test-Path $regPath)) {
    New-Item -Path $regPath -Force | Out-Null
}
New-ItemProperty -Path $regPath -Name DefaultShell `
    -Value $psPath -PropertyType String -Force | Out-Null
Write-Host "      DefaultShell -> $psPath"

# --- 5. Verify port 22 is listening ---
Write-Host "[5/5] Verifying port 22 ..."
$test = Test-NetConnection -ComputerName 127.0.0.1 -Port 22 -InformationLevel Quiet -WarningAction SilentlyContinue
if ($test) {
    Write-Host "      OK — port 22 is listening locally." -ForegroundColor Green
} else {
    Write-Host "      WARNING: port 22 didn't respond locally. Check 'Get-Service sshd'." -ForegroundColor Yellow
}

# --- Tailscale IP for Mac to point at ---
Write-Host ""
Write-Host "================================================================"
Write-Host "  Done. Connect from the Mac with:"
Write-Host ""
$tsIp = (& 'tailscale' ip -4 2>$null | Select-Object -First 1)
if ($tsIp) {
    Write-Host "      ssh hdven@$tsIp"
    Write-Host "      ssh hdven@harrismotors    (MagicDNS, if enabled)"
} else {
    Write-Host "      ssh hdven@<this-machine-Tailscale-IP-or-name>"
}
Write-Host ""
Write-Host "  First connection will prompt for your Windows password."
Write-Host "  To skip the password prompt every time, add the Mac's public"
Write-Host "  SSH key to:"
Write-Host "      C:\ProgramData\ssh\administrators_authorized_keys"
Write-Host "  (admin accounts use that path, NOT ~\.ssh\authorized_keys)"
Write-Host "================================================================"
Write-Host ""
Write-Host "Press any key to close this window..."
$null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
