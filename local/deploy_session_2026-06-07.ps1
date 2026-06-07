# ============================================================================
# Narrow Highway - consolidated session deploy (2026-06-07)
# Ships the Codex work built this session (commits 114e01c..bf8070b):
#   - api/codex.py: the Codex compiler + index API (scripture / themes /
#     connections) + the signed-artifact (Face 2) seal + verify
#   - api/app.py: mounts the codex router
#   - site/codex-*.html: cross-reference, theme, seal, and connection pages
#   - data/codex/index/*.json: the compiled indexes (scripture / themes /
#     connections) - built from the deployed substrate, so safe to ship as-is
#   - data/codex/*.md: STRUCTURE / README / AUTHORITY_SPINE (Codex spec)
#
# Review before running. Tailscale SSH + git push are yours.
# ASCII-only on purpose (Windows PowerShell 5.1 cannot parse a UTF-8 file
# containing non-ASCII characters).
# ============================================================================

$srv = "nh@nh-engine-1"
$r   = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"

function Guard($label) {
  if ($LASTEXITCODE -ne 0) {
    Write-Host "  [FAIL] $label (exit $LASTEXITCODE) - stopping so the server is not left half-updated." -ForegroundColor Red
    exit 1
  }
}

Write-Host "1/7  Push to GitHub (backup)..." -ForegroundColor Cyan
Set-Location $r
git push origin main
Guard "git push"

Write-Host "2/7  Backend  -> ~/Lighthouse/api/" -ForegroundColor Cyan
scp "$r\api\codex.py" "$r\api\app.py" "$r\api\original_language.py" "$r\api\funnel.py" "$r\api\offices.py" "$srv`:~/Lighthouse/api/"
Guard "scp api"

Write-Host "2b/7 Engine    -> ~/Lighthouse/src/concordance_engine/agent/ (floor: dispatch + gate)" -ForegroundColor Cyan
scp "$r\src\concordance_engine\agent\dispatch.py" "$r\src\concordance_engine\agent\poly_agent.py" "$srv`:~/Lighthouse/src/concordance_engine/agent/"
Guard "scp dispatch + poly_agent"

Write-Host "3/7  Site     -> ~/Lighthouse/site/" -ForegroundColor Cyan
scp "$r\site\codex.html" "$r\site\codex-xref.html" "$r\site\codex-themes.html" "$r\site\codex-seal.html" "$r\site\codex-connections.html" "$r\site\cards-dev.html" "$r\site\atlas-map.html" "$r\site\funnel.html" "$r\site\you.html" "$r\site\deposit.html" "$r\site\sw.js" "$srv`:~/Lighthouse/site/"
Guard "scp site"

Write-Host "4/7  Ensure data/codex dirs exist on the server..." -ForegroundColor Cyan
ssh $srv "mkdir -p ~/Lighthouse/data/codex/index ~/Lighthouse/data/codex/compiled"
Guard "mkdir codex dirs"

Write-Host "5/7  Indexes  -> ~/Lighthouse/data/codex/" -ForegroundColor Cyan
scp "$r\data\codex\index\scripture.json" "$r\data\codex\index\themes.json" "$r\data\codex\index\connections.json" "$r\data\codex\index\cards_dev.json" "$srv`:~/Lighthouse/data/codex/index/"
Guard "scp indexes"
scp "$r\data\codex\STRUCTURE.md" "$r\data\codex\README.md" "$r\data\codex\AUTHORITY_SPINE.md" "$srv`:~/Lighthouse/data/codex/"
Guard "scp codex docs"

Write-Host "5b/7 Engine-generated verified connections + the generator..." -ForegroundColor Cyan
ssh $srv "mkdir -p ~/Lighthouse/tools"
Guard "mkdir tools"
scp "$r\data\almanac\generated_verified.jsonl" "$srv`:~/Lighthouse/data/almanac/"
Guard "scp generated_verified"
scp "$r\tools\grow_verified.py" "$srv`:~/Lighthouse/tools/"
Guard "scp grow_verified"

Write-Host "5c/7 Offices: NO bootstrap needed - prod is ALREADY trained." -ForegroundColor Cyan
Write-Host "     Verified 2026-06-07: prod has trained office models (shepherd/scribe/steward.json)" -ForegroundColor DarkGray
Write-Host "     on ~1890/1580/1433 examples; predictions fire at conf 0.95-1.00. The new offices.py" -ForegroundColor DarkGray
Write-Host "     uses these existing models immediately (office-model tier). Do NOT re-run the" -ForegroundColor DarkGray
Write-Host "     teacher-distill - it would re-spend to regenerate data that already exists." -ForegroundColor DarkGray
Write-Host "     The FREE loop is live after deploy: POST /offices/retrain folds live oracle" -ForegroundColor DarkGray
Write-Host "     decisions into the train set + retrains (no oracle cost); GET /offices/stats reads" -ForegroundColor DarkGray
Write-Host "     the oracle-dependence. tools/ + models already on prod; nothing to scp here." -ForegroundColor DarkGray

Write-Host "6/7  Restart the engine..." -ForegroundColor Cyan
ssh $srv "sudo systemctl restart nh-engine"
Guard "engine restart"

Write-Host "7/7  Seal the Codex on prod (Face 2) - OPTIONAL, non-fatal." -ForegroundColor Cyan
Write-Host "     This signs the manifest with the PROD identity key. If your engine" -ForegroundColor DarkGray
Write-Host "     runs in a venv, adjust the python path. Skipping is fine - the four" -ForegroundColor DarkGray
Write-Host "     surfaces work unsealed; /codex/verify just reports 'not sealed yet'." -ForegroundColor DarkGray
ssh $srv "cd ~/Lighthouse && python3 -m api.codex seal"
if ($LASTEXITCODE -ne 0) {
  Write-Host "  [WARN] seal step did not run (likely python env path) - deploy still succeeded." -ForegroundColor Yellow
  Write-Host "         To seal later: ssh $srv, cd ~/Lighthouse, run 'python -m api.codex seal' in the engine's env." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Deployed. Verify:" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/codex.html              (callouts to all four surfaces)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/codex-xref.html         (scripture cross-references, witnessed)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/codex-themes.html       (the theme index)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/codex-connections.html  (verified cross-domain + scripture + candidates)" -ForegroundColor Green
Write-Host "  https://narrowhighway.com/codex-seal.html         (the signed manuscript - after the seal step)" -ForegroundColor Green
Write-Host "  curl https://narrowhighway.com/codex/connections  (81 verified-structural, 139 hubs, 1269 candidates)" -ForegroundColor Green
Write-Host ""
Write-Host "After this deploy, purge the Cloudflare cache (HTML + the new pages)." -ForegroundColor DarkGray
