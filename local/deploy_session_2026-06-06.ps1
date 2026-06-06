# ============================================================================
# Narrow Highway - consolidated session deploy (2026-06-06)
# Ships everything built this session (commits 35780a2..HEAD):
#   - homepage declutter + hero-reaches-everything + retrieval-by-narrowing
#   - the floor + Didache grounding on the front door + one shared airlock
#   - docs: THE_GUIDE (map), HORIZONS (lever test), MARKETPLACE_V1 spec
#   - Christian Marketplace v1, organized by ZIP (free, no cut)
#   - oracle-dependence scoreboard (/innovation) + recorder
#   - 7 build-queue gap closes + moon-landing reclassified to declined
#   - findability: new pages added to the sitemap
#   - two front doors: narrowhighway.tv (family) + narrowhighway.org (innovation)
#
# Review before running. Tailscale SSH + git push are yours.
# Note: earlier floor modules (calibre.py, nested_control.py) shipped in a
# prior cycle and are not re-sent here. ASCII-only on purpose (Windows
# PowerShell 5.1 cannot parse a UTF-8 file containing non-ASCII characters).
# ============================================================================

$srv = "nh@nh-engine-1"
$r   = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"

function Guard($label) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] $label (exit $LASTEXITCODE) - stopping so the server is not left half-updated." -ForegroundColor Red
    exit 1
  }
}

Write-Host "1/6  Push to GitHub (backup)..." -ForegroundColor Cyan
Set-Location $r
git push origin main
Guard "git push"

Write-Host "2/6  Backend  -> ~/Lighthouse/api/" -ForegroundColor Cyan
scp "$r\api\app.py" "$r\api\didache.py" "$r\api\floor.py" "$r\api\market.py" "$srv`:~/Lighthouse/api/"
Guard "scp api"

Write-Host "3/6  Engine   -> ~/Lighthouse/src/concordance_engine/" -ForegroundColor Cyan
scp "$r\src\concordance_engine\agent\dispatch_stats.py" "$r\src\concordance_engine\agent\poly_agent.py" "$srv`:~/Lighthouse/src/concordance_engine/agent/"
Guard "scp agent"
scp "$r\src\concordance_engine\verifiers\economics.py" "$r\src\concordance_engine\verifiers\periodic_table.py" "$r\src\concordance_engine\verifiers\scripture.py" "$r\src\concordance_engine\verifiers\thermodynamics.py" "$srv`:~/Lighthouse/src/concordance_engine/verifiers/"
Guard "scp verifiers"

Write-Host "4/6  Data     -> ~/Lighthouse/data/build_queue/" -ForegroundColor Cyan
scp "$r\data\build_queue\queue.jsonl" "$srv`:~/Lighthouse/data/build_queue/"
Guard "scp queue"

Write-Host "5/6  Site     -> ~/Lighthouse/site/" -ForegroundColor Cyan
scp "$r\site\index.html" "$r\site\nh-shell.js" "$r\site\marketplace.html" "$r\site\innovation.html" "$r\site\gaps.html" "$r\site\workspace.html" "$r\site\family.html" "$r\site\learn-deep.html" "$r\site\codex-deep.html" "$r\site\take-part.html" "$r\site\door-tv.html" "$r\site\door-org.html" "$r\site\odysseus.html" "$r\site\sitemap.xml" "$r\site\sitemap_index.xml" "$srv`:~/Lighthouse/site/"
Guard "scp site"

Write-Host "6/6  Restart the engine..." -ForegroundColor Cyan
ssh $srv "sudo systemctl restart nh-engine"
Guard "engine restart"

Write-Host ""
Write-Host "Deployed. Verify:" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/marketplace.html   (Marketplace, by ZIP)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/innovation.html    (oracle-dependence scoreboard)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/gaps.html          (7 closed; moon-landing now declined)" -ForegroundColor Green
Write-Host "  Weigh a teaching on the homepage: the gates now show Scripture + the Didache." -ForegroundColor Green
Write-Host "(After a big deploy, purge the Cloudflare cache. .tv/.org doors go live once DNS points at the server.)" -ForegroundColor DarkGray
