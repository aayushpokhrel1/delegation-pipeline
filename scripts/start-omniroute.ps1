# Starts the OmniRoute gateway if it isn't already running. Idempotent and hidden.
# Called by the autostart scheduled task, or run manually to launch the gateway.
$ErrorActionPreference = "SilentlyContinue"

$Port = 20128
$Log  = Join-Path $HOME ".claude\omniroute.log"

# Already listening? Nothing to do.
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) { Write-Output "OmniRoute already running on port $Port"; exit 0 }

# Resolve a directly-launchable command. Get-Command 'omniroute' returns the
# PowerShell shim (.ps1), which Start-Process cannot execute: it silently
# no-ops, which is why autostart appeared to "succeed" (task result 0) while no
# gateway ever came up. Prefer the .cmd shim, which Start-Process can launch.
$cmd = Get-Command omniroute.cmd -ErrorAction SilentlyContinue
if ($cmd) {
    $exe  = $cmd.Source
    $args = @()
} else {
    $exe  = "cmd.exe"
    $args = @("/c", "npx", "--yes", "omniroute")
}

# Launch hidden, appending stdout/stderr to the log.
Start-Process -FilePath $exe -ArgumentList $args `
    -WindowStyle Hidden `
    -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
Write-Output "Launched OmniRoute via '$exe' (log: $Log)"
