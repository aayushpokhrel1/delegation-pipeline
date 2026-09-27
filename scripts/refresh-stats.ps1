# Refreshes the README stats block from the delegate usage ledger, then commits
# README.md if it changed. Run by the weekly scheduled task, or by hand:
#   powershell -ExecutionPolicy Bypass -File scripts\refresh-stats.ps1
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Log = Join-Path $env:USERPROFILE ".claude\delegate-stats-refresh.log"

function Write-Log($Message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message"
    Add-Content -Path $Log -Value $line -Encoding utf8
    Write-Host $line
}

try {
    Set-Location $RepoRoot

    # No 2>&1 here: in PowerShell 5.1 redirecting a native command's stderr while
    # $ErrorActionPreference is "Stop" turns any stderr line into a terminating
    # NativeCommandError, which would fail the task on a harmless log line.
    $output = & python delegate.py --stats --readme
    foreach ($line in $output) { Write-Log $line }
    if ($LASTEXITCODE -ne 0) {
        Write-Log "delegate.py --stats --readme exited $LASTEXITCODE"
        exit 1
    }

    # Only README.md matters here; unrelated work in the tree must stay untouched.
    $status = & git status --porcelain -- README.md
    if (-not $status) {
        Write-Log "README unchanged, nothing to commit"
        exit 0
    }

    & git add -- README.md
    if ($LASTEXITCODE -ne 0) {
        Write-Log "git add -- README.md failed"
        exit 1
    }
    & git commit -m "chore: refresh delegation stats" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "git commit failed"
        exit 1
    }
    $sha = (& git rev-parse --short HEAD).Trim()
    Write-Log "committed README.md as $sha"
} catch {
    Write-Log "error: $($_.Exception.Message)"
    exit 1
}
