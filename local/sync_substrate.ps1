# ============================================================================
# Narrow Highway - content substrate sync (2026-06-09)
# ============================================================================
# ROOT-CAUSE FIX for a gap that bit three times in one session: the prod box's
# CONTENT substrate (the text the live surfaces read) is NOT shipped by the code
# deploy script, so prod silently ran thinner than local until a surface was
# noticed returning empty:
#   - the WELL had zero Scripture/patristics (only almanac+protocol)  -> Iter 10/11
#   - the EASTON Bible dictionary 404'd for everything                -> Iter 11
#   - the APOTHECARY compound was missing the mind + parable ingredients -> Iter 21
#
# These are small PD text dirs (a few MB total); the box has ~61 GB free. This
# script scp's the content substrate the prod LIVE SURFACES need, then restarts
# the engine so the mtime-cached loaders pick it up. Run it after adding any new
# packet source, or to bring a fresh/rebuilt box up to parity with local.
#
# It is SEPARATE from the code deploy on purpose: this data changes rarely, so it
# should not slow every code push. ASCII-only (Windows PowerShell 5.1).
# ============================================================================

$srv = "nh@nh-engine-1"
$r   = "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse\data"

# The WELL's wisdom corpus (well_retriever + the narrowing's free-text fallback):
$wisdom = @(
  "augustine_confessions","aurelius","pilgrim","ecclesiastes","psalms",
  "imitation_christ","james","pirkei_avot","clement1","boethius_consolation",
  "didache","polycarp","proverbs","barnabas","martyrdom_polycarp","sermon_on_mount",
  "ignatius_eph","ignatius_mag","ignatius_tra","ignatius_rom","ignatius_phild",
  "ignatius_smy","ignatius_polyc","fieldkit","sermons"
)

# The Easton Bible dictionary (/easton/{slug}) + places/geography (atlas):
$reference = @("easton","places")

# The Apothecary's compound ingredients (mind practice / parable / body / philosopher):
$ingredients = @("mind","parables","aesop","body","larochefoucauld")

$dirs = $wisdom + $reference + $ingredients

Write-Host "1/2  Sync content substrate ($($dirs.Count) dirs) -> ~/Lighthouse/data/" -ForegroundColor Cyan
$paths = $dirs | ForEach-Object { Join-Path $r $_ } | Where-Object { Test-Path $_ }
$missing = $dirs | Where-Object { -not (Test-Path (Join-Path $r $_)) }
if ($missing.Count -gt 0) {
  Write-Host "  [WARN] not present locally (skipped): $($missing -join ', ')" -ForegroundColor Yellow
}
scp -r @paths "$srv`:~/Lighthouse/data/"
if ($LASTEXITCODE -ne 0) {
  Write-Host "  [FAIL] scp content substrate (exit $LASTEXITCODE)" -ForegroundColor Red
  exit 1
}

Write-Host "2/2  Restart the engine (refresh mtime-cached loaders)..." -ForegroundColor Cyan
ssh $srv "sudo systemctl restart nh-engine"
if ($LASTEXITCODE -ne 0) {
  Write-Host "  [FAIL] engine restart (exit $LASTEXITCODE)" -ForegroundColor Red
  exit 1
}

Write-Host ""
Write-Host "Synced. Verify on prod:" -ForegroundColor Green
Write-Host "  curl 'https://narrowhighway.com/apothecary?condition=I%20cannot%20forgive%20my%20brother'  (8 ingredients)" -ForegroundColor Green
Write-Host "  curl https://narrowhighway.com/easton/moses                                                (200)" -ForegroundColor Green
Write-Host "  POST /narrow {text:'anxious and alone'}  -> well surfaces Augustine/Polycarp/Pilgrim" -ForegroundColor Green
