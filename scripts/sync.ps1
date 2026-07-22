<#
.SYNOPSIS
    Safe one-command sync: commit local work and push it to GitHub without
    ever rewriting history.

.DESCRIPTION
    Run this on the desktop instead of a manual add/commit/push. It:
      1. fetches origin,
      2. stages and commits any local changes (if there are any),
      3. rebases onto the latest origin so local and remote never diverge,
      4. pushes with --force-with-lease NEVER used — a plain, fast-forward push.

    This is the routine that keeps GitHub from drifting behind your live /
    desktop code. Pair it with the pre-push hook (see docs/SYNC.md) which
    hard-blocks any accidental history rewrite.

.PARAMETER Message
    Commit message for local changes. Defaults to a timestamped "sync".

.EXAMPLE
    ./scripts/sync.ps1
.EXAMPLE
    ./scripts/sync.ps1 -Message "wire up new verifier"
#>
param(
    [string]$Message = "sync: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
)

$ErrorActionPreference = "Stop"

# Move to the repo root regardless of where this was launched from.
$repoRoot = (git rev-parse --show-toplevel)
Set-Location $repoRoot

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
Write-Host "== syncing '$branch' with origin ==" -ForegroundColor Cyan

# Make sure the force-blocking hook is active on this machine.
$hooksPath = (git config core.hooksPath)
if ($hooksPath -ne "scripts/hooks") {
    Write-Host "Activating pre-push guard (core.hooksPath = scripts/hooks)..." -ForegroundColor Yellow
    git config core.hooksPath scripts/hooks
}

git fetch origin

# Stage + commit local work only if there is something to commit.
git add -A
if (git status --porcelain) {
    git commit -m $Message
    Write-Host "Committed local changes: $Message" -ForegroundColor Green
} else {
    Write-Host "No local changes to commit." -ForegroundColor DarkGray
}

# Rebase onto the remote tip so the push is always a clean fast-forward.
Write-Host "Rebasing onto origin/$branch..." -ForegroundColor Cyan
git pull --rebase origin $branch

# Plain push. The pre-push hook will refuse it if it would rewrite history.
Write-Host "Pushing..." -ForegroundColor Cyan
git push origin $branch

Write-Host "== done. GitHub is up to date with '$branch'. ==" -ForegroundColor Green
