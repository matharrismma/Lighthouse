#requires -Version 5.0
<#
.SYNOPSIS
    Phase 2 benchmark runner — Concordance Engine vs the 722-claim dataset.

.DESCRIPTION
    Right-click → "Run with PowerShell" from Windows Explorer, OR from a
    PowerShell prompt:
        powershell -ExecutionPolicy Bypass -File .\run_benchmark.ps1

    Steps:
      1. Confirm Python 3.10+ is on PATH
      2. Install sympy / scipy / numpy if missing
      3. Run run_benchmark.py with this folder as CWD
      4. Leave the window open so you can read the summary

    Outputs land in this folder:
      benchmark_results.jsonl     (one record per claim)
      benchmark_summary.json      (aggregate metrics)

.NOTES
    Wall time: ~30-60 seconds. The 20 T5.3 complexity claims add ~10-20s
    because they require live timing.
#>

$ErrorActionPreference = "Stop"
# Allow $LASTEXITCODE checks instead of auto-throwing on non-zero native exit codes
if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$here = $PSScriptRoot
if (-not $here) { $here = Split-Path -Parent $MyInvocation.MyCommand.Definition }
Set-Location -LiteralPath $here

function Write-Step {
    param([int]$Step, [string]$Message)
    Write-Host ""
    Write-Host "[$Step/4] $Message" -ForegroundColor Cyan
}

function Pause-AndExit {
    param([int]$Code = 0)
    Write-Host ""
    Read-Host "Press Enter to close"
    exit $Code
}

# ---- 1/4 Python check -----------------------------------------------------
Write-Step 1 "Checking Python..."
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "ERROR: Python is not on PATH." -ForegroundColor Red
    Write-Host "Install Python 3.10+ from https://python.org and re-run." -ForegroundColor Red
    Pause-AndExit 2
}
$pyVer = & python --version 2>&1
Write-Host "  $pyVer"

# ---- 2/4 Dependencies -----------------------------------------------------
Write-Step 2 "Ensuring required packages (sympy, scipy, numpy)..."
& python -c "import sympy, scipy, numpy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installing missing packages (this may take a minute)..." -ForegroundColor Yellow
    & python -m pip install --quiet sympy scipy numpy
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: pip install failed." -ForegroundColor Red
        Pause-AndExit 3
    }
    Write-Host "  Installed." -ForegroundColor Green
} else {
    Write-Host "  All present." -ForegroundColor Green
}

# ---- 3/4 Run benchmark ----------------------------------------------------
Write-Step 3 "Running benchmark (~30-60 seconds; T5.3 complexity adds ~10-20s)..."
Write-Host ""
& python run_benchmark.py
$rc = $LASTEXITCODE

# ---- 4/4 Summary ----------------------------------------------------------
Write-Step 4 "Done. Exit code: $rc"
Write-Host ""
Write-Host "Outputs in this folder:" -ForegroundColor Cyan
Write-Host "  benchmark_results.jsonl  (per-claim records)"
Write-Host "  benchmark_summary.json   (aggregate metrics)"
Write-Host ""
Write-Host "Next: open RESULTS.md and paste the values from benchmark_summary.json"
Write-Host "into the placeholder fields. Then we have a real evidence file for the repo."
Pause-AndExit $rc
