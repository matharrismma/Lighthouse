# refresh_channel.ps1 -- widen the Narrow Highway FAST channel.
#
# Regenerates the concat list from everything the encoder has finished, then,
# only if there is genuinely more content (or the push is down), restarts the
# YouTube push so it picks the new content up. A clean no-op (no stream blip)
# when nothing changed. Registered to run every few hours by
# setup_channel_refresh.ps1; safe to run by hand any time.
#
# It only ever touches the push (fast_channel_youtube_live.py and its rtmp
# ffmpeg). The encoder (fast_channel_encode.py) is never disturbed.

$ErrorActionPreference = "Continue"
$repo   = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"
$py     = "C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe"
$concat = Join-Path $repo "data\channels\narrow-highway\cache_concat.txt"
$log    = Join-Path $repo "data\live\refresh.log"

function Log($m) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m
    $line | Out-File -FilePath $log -Append -Encoding utf8
}

if (-not (Test-Path $py)) { $py = "python" }
Set-Location $repo
Log "=== refresh start ==="

# how many items before
$before = 0
if (Test-Path $concat) { $before = (Get-Content $concat | Measure-Object -Line).Lines }

# regenerate the concat list from the encoded cache
$concatOut = (& $py "tools\fast_channel_cache_concat.py" | Out-String)
foreach ($cl in ($concatOut -split "`n")) {
    $t = $cl.Trim()
    if ($t) { Log ("  | " + $t) }
}
$after = 0
if (Test-Path $concat) { $after = (Get-Content $concat | Measure-Object -Line).Lines }
Log ("concat items: {0} to {1}" -f $before, $after)

# is a push already running?
$pushProcs = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match 'fast_channel_youtube_live\.py' })
$pushRunning = $pushProcs.Count -gt 0

if (($after -le $before) -and $pushRunning) {
    Log "no new content and push is healthy -- no restart"
    Log "=== refresh done (no-op) ==="
    return
}

# stop the old push: supervisor python plus its rtmp ffmpeg child.
# The encoder is matched by a different script name and is never touched.
foreach ($p in $pushProcs) {
    Log ("stopping push supervisor PID {0}" -f $p.ProcessId)
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
$pushFf = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like 'ffmpeg*' -and $_.CommandLine -match 'rtmp://' })
foreach ($f in $pushFf) {
    Log ("stopping push ffmpeg PID {0}" -f $f.ProcessId)
    Stop-Process -Id $f.ProcessId -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 3

# start a fresh supervised push from the regenerated list
Start-Process -FilePath $py -WorkingDirectory $repo -WindowStyle Hidden -ArgumentList @(
    "tools\fast_channel_youtube_live.py",
    "--channel", "narrow-highway",
    "--concat", $concat,
    "--supervise"
)
Log ("started fresh push, {0} items" -f $after)
Log "=== refresh done ==="
