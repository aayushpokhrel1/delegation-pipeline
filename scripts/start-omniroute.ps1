# Starts the OmniRoute gateway if it isn't already running. Idempotent and hidden.
# Called by the autostart scheduled task, or run manually to launch the gateway.
$ErrorActionPreference = "SilentlyContinue"

$Port = 20128
$Log  = Join-Path $HOME ".claude\omniroute.log"

# Already listening? Nothing to do.
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) { Write-Output "OmniRoute already running on port $Port"; exit 0 }

# Prefer a global `omniroute` on PATH; fall back to npx (uses the cached package).
$omni = Get-Command omniroute -ErrorAction SilentlyContinue
if ($omni) {
    $exe  = $omni.Source
    $args = @()
} else {
    $exe  = "npx"
    $args = @("--yes", "omniroute")
}

# Launch hidden, appending stdout/stderr to the log.
Start-Process -FilePath $exe -ArgumentList $args `
    -WindowStyle Hidden `
    -RedirectStandardOutput $Log -RedirectStandardError "$Log.err"
Write-Output "Launched OmniRoute via '$exe' (log: $Log)"
