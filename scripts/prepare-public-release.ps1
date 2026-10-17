# Prepare chat2db for a safer public release.
# Run from a Windows PowerShell terminal with Git, git-filter-repo (with
# --sensitive-data-removal), and Gitleaks installed.
#
# This script rewrites Git history. It intentionally DOES NOT change repository
# visibility to Public and DOES NOT push until interactive confirmation.

$ErrorActionPreference = "Stop"
$RepositoryUrl = "https://github.com/majidmosadegh/chat2db.git"
$WorkRoot = Join-Path $env:TEMP ("chat2db-public-release-" + [guid]::NewGuid().ToString("N"))
$RepoPath = Join-Path $WorkRoot "chat2db"
$BackupPath = Join-Path $WorkRoot "preserved-current-files"
$RefsBackupPath = Join-Path $WorkRoot "original-refs.txt"
$OriginalIdsPath = Join-Path $WorkRoot "original-commit-ids.txt"

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

git -C $RepoPath show-ref | Out-File -FilePath $RefsBackupPath -Encoding utf8
git -C $RepoPath rev-list --all | Out-File -FilePath $OriginalIdsPath -Encoding utf8
Write-Host "Saved original refs to $RefsBackupPath"

# Materialize every remote branch as a local branch so the history-rewrite tool
# processes all branch histories, not just the default branch and master.
$remoteBranches = @(git -C $RepoPath for-each-ref --format="%(refname:strip=3)" refs/remotes/origin)
if ($LASTEXITCODE -ne 0) { throw "Could not enumerate remote branches." }
$localBranches = @(git -C $RepoPath branch --format "%(refname:short)")
if ($LASTEXITCODE -ne 0) { throw "Could not list local branches." }
foreach ($remoteBranch in $remoteBranches) {
    if ([string]::IsNullOrWhiteSpace($remoteBranch) -or $remoteBranch -eq "HEAD") { continue }
    if ($localBranches -notcontains $remoteBranch) {
        git -C $RepoPath branch $remoteBranch ("origin/" + $remoteBranch)
        if ($LASTEXITCODE -ne 0) { throw "Could not materialize remote branch '$remoteBranch'." }
    }
}

$branchNames = @(git -C $RepoPath branch --format "%(refname:short)")
if ($LASTEXITCODE -ne 0) { throw "Could not list local branches." }
if ($branchNames -contains "master") {
    git -C $RepoPath checkout master
} else {
    git -C $RepoPath checkout -b master origin/master
}
if ($LASTEXITCODE -ne 0) { throw "Expected application branch 'master' was not found or could not be checked out. No rewrite was pushed." }

# Preserve the currently corrected versions before removing their entire old
# histories. This removes historical hard-coded credentials/keys without
# embedding the secret values in this script.
$preserve = @(
    "backend/db/security.py",
    "backend/api/database.py",
    "backend/services/db_connector.py"
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

Push-Location $RepoPath
try {
    $filterArgs = @(
        "--force",
        "--sensitive-data-removal",
        "--invert-paths",
        "--path", "backend/api/encryption_key.txt",
        "--path", "backend/db/security.py",
        "--path", "backend/api/database.py",
        "--path", "frontend/.env.production"
    )
    & git-filter-repo @filterArgs
    if ($LASTEXITCODE -ne 0) { throw "History rewrite failed. Do not push; inspect the clone and backup." }
} finally {
    Pop-Location
}

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

git -C $RepoPath add -- @preserve
if ($LASTEXITCODE -ne 0) { throw "Could not stage corrected security files." }
git -C $RepoPath commit -m "security: restore fail-closed credential handling after history cleanup"
if ($LASTEXITCODE -ne 0) { throw "Could not commit restored security files." }

# main was previously an unrelated docs-only history. Make it point to the
# reviewed application tree so a fresh GitHub visitor lands on the actual app.
git -C $RepoPath branch -f main master
if ($LASTEXITCODE -ne 0) { throw "Could not align main with master." }

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
Write-Host "Backup of original refs: $RefsBackupPath"
Write-Host "Work root: $WorkRoot"
$confirmation = Read-Host "Type REWRITE-CHAT2DB-HISTORY to force-push the cleaned refs"
if ($confirmation -cne "REWRITE-CHAT2DB-HISTORY") {
    throw "Confirmation did not match. Nothing was pushed. The cleaned clone and backup remain at $WorkRoot"
}

git -C $RepoPath push --force-with-lease origin main
if ($LASTEXITCODE -ne 0) { throw "main push failed. Keep the repository private and inspect remote refs." }
git -C $RepoPath push --force-with-lease origin master
if ($LASTEXITCODE -ne 0) { throw "master push failed. Keep the repository private and inspect remote refs." }

$tags = @(git -C $RepoPath tag)
if ($tags.Count -gt 0) {
    git -C $RepoPath push --force-with-lease --tags origin
    if ($LASTEXITCODE -ne 0) { throw "Tag push failed. Keep the repository private and inspect remote tags." }
}

Write-Host ""
Write-Host "History cleanup was pushed. The repository is still PRIVATE."
Write-Host "Next: run clean-clone tests, set GitHub default branch to main if needed, then set visibility to Public only after final verification."
Write-Host "Temporary backup location: $WorkRoot"
