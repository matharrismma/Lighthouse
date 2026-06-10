# watchdog.ps1 - Keep the Concordance engine alive.
#
# Runs in an infinite loop. Every 60 seconds:
#   1. Hit http://localhost:8000/health
#   2. If down for 3 consecutive checks (3 minutes), kill any stale python and
#      restart the engine via Start-ScheduledTask 'Concordance-API'
#   3. Log every check + every restart to C:\Concordance\logs\watchdog.log
#
# Tolerant of cold-starts: a single failed check doesn't restart (fastapi cold
# import can take 60-120s, and we don't want to thrash). Three consecutive
# misses = real failure.
#
# Install: run local/setup_watchdog.ps1 once (elevated) to register this as
# a scheduled task that runs on boot + every 5 minutes.
#
# Stop: Get-ScheduledTask -TaskName 'Concordance-Watchdog' | Stop-ScheduledTask

$ErrorActionPreference = 'Continue'
$logDir = 'C:\Concordance\logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
$logPath = Join-Path $logDir 'watchdog.log'

function Log-Line {
    param([string]$line, [ConsoleColor]$color = 'Gray')
    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $msg = "[$stamp] $line"
    try { Add-Content -Path $logPath -Value $msg -Encoding utf8 } catch {}
    try { Write-Host $msg -ForegroundColor $color } catch {}
}

Log-Line "watchdog starting (PID $PID)" 'Cyan'

# Trim log file if it gets bigger than 10 MB (rotates by losing oldest 50%)
function Trim-Log {
    try {
        if ((Get-Item $logPath -ErrorAction SilentlyContinue).Length -gt 10MB) {
            $lines = Get-Content $logPath
            $half = [Math]::Floor($lines.Count / 2)
            $lines[$half..($lines.Count - 1)] | Set-Content $logPath -Encoding utf8
            Log-Line "log rotated (kept tail half)" 'Yellow'
        }
    } catch {}
}

$consecutive_fails = 0
$check_interval_sec = 60
$fails_before_restart = 3

while ($true) {
    Trim-Log

    $ok = $false
    try {
        $r = Invoke-RestMethod 'http://localhost:8000/health' -TimeoutSec 10
        if ($r.status -eq 'ok') { $ok = $true }
    } catch {
        # Tolerate; counted as a fail
    }

    if ($ok) {
        if ($consecutive_fails -gt 0) {
            Log-Line "health recovered (was $consecutive_fails consecutive fails)" 'Green'
        }
        $consecutive_fails = 0
    } else {
        $consecutive_fails++
        Log-Line "health check failed ($consecutive_fails / $fails_before_restart)" 'Yellow'

        if ($consecutive_fails -ge $fails_before_restart) {
            Log-Line "RESTARTING engine (consecutive fails = $consecutive_fails)" 'Red'

            # Kill whatever is listening on port 8000
            try {
                $port = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue
                foreach ($p in ($port.OwningProcess | Sort-Object -Unique)) {
                    Log-Line "  stopping stale process PID $p on port 8000" 'Yellow'
                    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
                }
            } catch {}
            Start-Sleep -Seconds 2

            # Restart the engine. Primary path: the Concordance-API scheduled
            # task (if it exists). Fallback: launch start_server.ps1 directly
            # via Start-Process - this works even when the task was never
            # registered, so the watchdog never depends on the task existing.
            $restarted = $false
            $apiTask = Get-ScheduledTask -TaskName 'Concordance-API' -ErrorAction SilentlyContinue
            if ($apiTask) {
                try {
                    Start-ScheduledTask -TaskName 'Concordance-API'
                    Log-Line "  restarted via scheduled task 'Concordance-API'" 'Cyan'
                    $restarted = $true
                } catch {
                    Log-Line "  task start failed: $_" 'Yellow'
                }
            }
            if (-not $restarted) {
                $starter = 'C:\Concordance\start_server.ps1'
                if (Test-Path $starter) {
                    try {
                        Start-Process -FilePath 'powershell.exe' `
                            -ArgumentList '-NonInteractive','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-File',$starter `
                            -WindowStyle Hidden
                        Log-Line "  restarted directly via Start-Process $starter" 'Cyan'
                        $restarted = $true
                    } catch {
                        Log-Line "  ERROR: Start-Process failed: $_" 'Red'
                    }
                } else {
                    Log-Line "  ERROR: no Concordance-API task AND no $starter - cannot restart" 'Red'
                }
            }

            # Wait extra long for cold-start before re-checking (avoid restart thrash)
            $consecutive_fails = 0
            Start-Sleep -Seconds 180
            continue
        }
    }

    Start-Sleep -Seconds $check_interval_sec
}
