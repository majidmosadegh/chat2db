# Prepare chat2db for a safer public release.
# Run from a Windows PowerShell terminal with Git, git-filter-repo >= 2.47,
# and Gitleaks installed. This script rewrites Git history and force-pushes refs.
# It intentionally DOES NOT change repository visibility to Public.

$ErrorActionPreference = "Stop"
$RepositoryUrl = "https://github.com/majidmosadegh/chat2db.git"
$WorkRoot = Join-Path $env:TEMP ("chat2db-public-release-" + [guid]::NewGuid().ToString("N"))
$RepoPath = Join-Path $WorkRoot "chat2db"
$BackupPath = Join-Path $WorkRoot "preserved-current-files"

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. Install it and rerun."
    }
}

Require-Command "git"
Require-Command "git-filter-repo"
Require-Command "gitleaks"

$filterVersion = (& git-filter-repo --version 2>&1 | Out-String).Trim()
Write-Host "git-filter-repo: $filterVersion"
Write-Host "A fresh clone will be created at: $RepoPath"
Write-Host "A backup of the current clean source files will be kept at: $BackupPath"

New-Item -ItemType Directory -Path $BackupPath -Force | Out-Null
git clone --no-single-branch $RepositoryUrl $RepoPath
if ($LASTEXITCODE -ne 0) { throw "Clone failed. Check GitHub authentication and network access." }

git -C $RepoPath fetch --all --tags --prune
if ($LASTEXITCODE -ne 0) { throw "Fetching all branches and tags failed." }

$branchNames = @(git -C $RepoPath branch --format "%(refname:short)")
if ($LASTEXITCODE -ne 0) { throw "Could not list local branches." }
if ($branchNames -notcontains "master") { throw "Expected application branch 'master' was not found. No rewrite was performed." }

git -C $RepoPath checkout master
if ($LASTEXITCODE -ne 0) { throw "Could not check out master." }

# Preserve the currently corrected versions before removing their entire old
# histories. This removes historical hard-coded credentials/keys without
# embedding the secret values in this script.
$preserve = @(
    "backend/db/security.py",
    "backend/api/database.py"
)
foreach ($relative in $preserve) {
    $source = Join-Path $RepoPath $relative
    if (-not (Test-Path $source -PathType Leaf)) {
        throw "Expected corrected source file '$relative' is missing. No rewrite was pushed."
    }
    $destination = Join-Path $BackupPath $relative
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item $source $destination -Force
}

# Keep a private copy of the fetched refs in the temporary clone. The paths
# below are removed from every branch/tag history, then the current safe source
# files are re-added in a new commit.
$filterArgs = @(
    "--force",
    "--invert-paths",
    "--path", "backend/api/encryption_key.txt",
    "--path", "backend/db/security.py",
    "--path", "backend/api/database.py",
    "--path", "frontend/.env.production"
)
& git-filter-repo @filterArgs
if ($LASTEXITCODE -ne 0) { throw "History rewrite failed. Do not push; inspect the clone and backup." }

# git-filter-repo removes the origin remote by design.
git -C $RepoPath remote add origin $RepositoryUrl
if ($LASTEXITCODE -ne 0) { throw "Could not restore the origin remote." }

foreach ($relative in $preserve) {
    $source = Join-Path $BackupPath $relative
    $destination = Join-Path $RepoPath $relative
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item $source $destination -Force
}

$forbiddenPath = Join-Path $RepoPath "backend/api/encryption_key.txt"
if (Test-Path $forbiddenPath) {
    throw "The committed encryption-key file unexpectedly remains in the working tree."
}
$productionEnv = Join-Path $RepoPath "frontend/.env.production"
if (Test-Path $productionEnv) {
    Remove-Item $productionEnv -Force
}

git -C $RepoPath add -- "backend/db/security.py" "backend/api/database.py"
if ($LASTEXITCODE -ne 0) { throw "Could not stage corrected security files." }
git -C $RepoPath commit -m "security: restore fail-closed credential handling after history cleanup"
if ($LASTEXITCODE -ne 0) { throw "Could not commit restored security files." }

# main was previously an unrelated docs-only history. Make it point to the
# reviewed application tree so a fresh GitHub visitor lands on the actual app.
git -C $RepoPath branch -f main master
if ($LASTEXITCODE -ne 0) { throw "Could not align main with master." }

# Scan reachable Git history before publishing rewritten refs. If Gitleaks
# reports findings, stop before pushing and investigate them first.
Push-Location $RepoPath
try {
    & gitleaks git . --redact
    if ($LASTEXITCODE -ne 0) {
        throw "Gitleaks found potential secrets or failed. No refs have been pushed. Review findings before continuing."
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "Pre-push checks passed. This will replace branch/tag history on GitHub."
$confirmation = Read-Host "Type REWRITE-CHAT2DB-HISTORY to force-push the cleaned refs"
if ($confirmation -cne "REWRITE-CHAT2DB-HISTORY") {
    throw "Confirmation did not match. Nothing was pushed. The cleaned clone and backup remain at $WorkRoot"
}

git -C $RepoPath push --force --all origin
if ($LASTEXITCODE -ne 0) { throw "Branch push failed. Keep the repository private and inspect remote refs." }
git -C $RepoPath push --force --tags origin
if ($LASTEXITCODE -ne 0) { throw "Tag push failed. Keep the repository private and inspect remote tags." }

Write-Host ""
Write-Host "History cleanup was pushed. The repository is still PRIVATE."
Write-Host "Next: inspect all Gitleaks output/results, run clean-clone tests, review license ownership, then change GitHub default branch to main if needed and only then set visibility to Public."
Write-Host "Temporary backup location: $WorkRoot"
