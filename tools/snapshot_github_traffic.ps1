# Snapshot GitHub repo traffic into data/github_traffic.jsonl
# GitHub only retains 14 days of traffic data, owner-only. Run this daily to
# accumulate history. Requires `gh` on PATH, authenticated as the repo owner.
#   powershell -NoProfile -File tools\snapshot_github_traffic.ps1
$ErrorActionPreference = 'Stop'
$repo = 'matharrismma/Lighthouse'
$out  = Join-Path $PSScriptRoot '..\data\github_traffic.jsonl'

function CF($path) { gh api "repos/$repo/$path" | ConvertFrom-Json }

$views  = CF 'traffic/views'
$clones = CF 'traffic/clones'
$refs   = CF 'traffic/popular/referrers'
$paths  = CF 'traffic/popular/paths'
$meta   = gh api "repos/$repo" | ConvertFrom-Json

$snap = [ordered]@{
  snapshot_utc   = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  views_14d      = $views.count
  views_uniq_14d = $views.uniques
  clones_14d     = $clones.count
  clones_uniq_14d= $clones.uniques
  stars          = $meta.stargazers_count
  forks          = $meta.forks_count
  watchers       = $meta.subscribers_count
  views_daily    = $views.views
  clones_daily   = $clones.clones
  referrers      = $refs
  top_paths      = $paths
}
$line = $snap | ConvertTo-Json -Depth 6 -Compress
Add-Content -Path $out -Value $line -Encoding utf8
Write-Output ("snapshot appended: views={0}/{1} clones={2}/{3} stars={4}" -f $views.count,$views.uniques,$clones.count,$clones.uniques,$meta.stargazers_count)
