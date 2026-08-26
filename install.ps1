# Installs the `delegate` launcher into ~/.claude/bin and seeds config (Windows).
# Run from PowerShell:  ./install.ps1
$ErrorActionPreference = "Stop"

$RepoDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir = Join-Path $HOME ".claude"
$BinDir    = Join-Path $ClaudeDir "bin"
$Config    = Join-Path $ClaudeDir "delegate.config.json"

# Find a Python 3 interpreter.
$Py = $null
foreach ($c in @("python", "python3", "py")) {
    $cmd = Get-Command $c -ErrorAction SilentlyContinue
    if ($cmd) {
        $ok = & $c -c "import sys; print(sys.version_info[0])" 2>$null
        if ($ok -eq "3") { $Py = $c; break }
    }
}
if (-not $Py) { Write-Error "No Python 3 found on PATH. Install Python 3.8+ first."; exit 1 }

New-Item -ItemType Directory -Force -Path $BinDir | Out-Null

# Bash launcher (the Claude Code Bash tool uses Git Bash, so this is the one it calls).
$RepoPosix = ($RepoDir -replace '\\','/')
$Launcher  = Join-Path $BinDir "delegate"
$bash = "#!/usr/bin/env bash`nexec `"$Py`" `"$RepoPosix/delegate.py`" `"`$@`"`n"
Set-Content -Path $Launcher -Value $bash -Encoding utf8 -NoNewline

# Convenience wrappers for calling from PowerShell / cmd directly.
$Ps1 = Join-Path $BinDir "delegate.ps1"
Set-Content -Path $Ps1 -Value "& `"$Py`" `"$RepoDir\delegate.py`" `$args`n" -Encoding utf8
$Cmd = Join-Path $BinDir "delegate.cmd"
Set-Content -Path $Cmd -Value "@echo off`r`n`"$Py`" `"$RepoDir\delegate.py`" %*`r`n" -Encoding utf8

Write-Host "installed launcher -> $Launcher (+ .ps1 / .cmd)"

if (-not (Test-Path $Config)) {
    Copy-Item (Join-Path $RepoDir "config.example.json") $Config
    Write-Host "seeded config      -> $Config"
} else {
    Write-Host "config exists      -> $Config (left unchanged)"
}

Write-Host ""
Write-Host "Done. Test it:"
Write-Host "  & `"$Cmd`" free `"list the files here and summarize the project`""
Write-Host ""
Write-Host "For deepseek/kimi, set keys (env vars or edit $Config):"
Write-Host '  setx DEEPSEEK_API_KEY sk-...'
Write-Host '  setx MOONSHOT_API_KEY sk-...'
Write-Host "For the free backend, run OmniRoute in another terminal:  npx omniroute"
