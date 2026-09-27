# Starts the OmniRoute gateway if it isn't already running. Idempotent and hidden.
# Called by the autostart scheduled task, or run manually to launch the gateway.
$ErrorActionPreference = "SilentlyContinue"

$Port = 20128
$Log  = Join-Path $HOME ".claude\omniroute.log"

# OmniRoute ships as a Next.js DEV server, so every route compiles on its first
# request after a restart. Measured cold on Windows: /api/monitoring/health over
# 90s, /v1/models about 10s, both under 0.1s once warm. Whichever client calls
# first pays that bill, times out, and reports the gateway "down" even though it
# is up and compiling. So pay it here, at boot, where nobody is waiting.
function Warm-Routes {
    param([int]$Port, [int]$TimeoutSec = 240)

    # The CLI prints "Ready" as soon as it binds, well before it can serve, so
    # wait on the listener rather than trusting startup output. Write-Host, not
    # Write-Output: Write-Output would join these strings onto the function's
    # return value and turn the boolean into an array.
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $up = $false
    while ((Get-Date) -lt $deadline) {
        if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) { $up = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $up) {
        Write-Host "OmniRoute never listened on port $Port within ${TimeoutSec}s. See $Log and $Log.err"
        return $false
    }

    # 127.0.0.1, not localhost: the server binds 0.0.0.0 (IPv4 only) and ::1 is refused.
    $paths  = @("/api/monitoring/health", "/v1/models")
    $warmed = 0
    foreach ($path in $paths) {
        # Two attempts. A cold compile can outlast TimeoutSec, in which case the
        # request gives up while the server keeps compiling; the retry then lands
        # on the now-warm route. Without it the starter exits non-zero on a
        # gateway that is actually fine, and a false alarm here teaches you to
        # ignore the real ones.
        for ($attempt = 1; $attempt -le 2; $attempt++) {
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:$Port$path" -TimeoutSec $TimeoutSec -UseBasicParsing | Out-Null
                $warmed++
                break
            } catch {
                # An HTTP error response (e.g. 401 from /v1/models, which needs a
                # Bearer key) still means the route compiled. Only a transport-level
                # failure with no response at all counts as not warmed.
                if ($_.Exception.Response) { $warmed++; break }
                if ($attempt -eq 2) { Write-Host "Warm request to $path failed twice: $($_.Exception.Message)" }
            }
        }
    }
    Write-Host "Warmed $warmed/$($paths.Count) OmniRoute routes on port $Port"
    return ($warmed -eq $paths.Count)
}

# Already listening? Still warm it. The CLI's supervisor restarts the child on
# crash, which leaves the port held by a freshly-cold server.
$listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Output "OmniRoute already running on port $Port"
    if (Warm-Routes -Port $Port) { exit 0 } else { exit 1 }
}

# Resolve a directly-launchable command. Get-Command 'omniroute' returns the
# PowerShell shim (.ps1), which Start-Process cannot execute: it silently
# no-ops, which is why autostart appeared to "succeed" (task result 0) while no
# gateway ever came up. Prefer the .cmd shim, which Start-Process can launch.
# The npx fallback re-extracts the package and discards Next's .next build cache
# on every launch, which is what makes the cold compile so brutal; a global
# install (npm i -g omniroute) keeps that cache and is strongly preferred.
$cmd = Get-Command omniroute.cmd -ErrorAction SilentlyContinue
if ($cmd) {
    $exe     = $cmd.Source
    $cmdArgs = @()
} else {
    $exe     = "cmd.exe"
    $cmdArgs = @("/c", "npx", "--yes", "omniroute")
}

# Launch hidden, logging stdout/stderr. Splatted, and ArgumentList is omitted
# when empty: PowerShell 5.1 refuses to bind an empty array to -ArgumentList,
# and with $ErrorActionPreference = SilentlyContinue that error is swallowed, so
# the global-shim branch silently launched nothing at all. Do not use $args as
# the variable name here either; it is a PowerShell automatic variable.
$spawn = @{
    FilePath               = $exe
    WindowStyle            = "Hidden"
    RedirectStandardOutput = $Log
    RedirectStandardError  = "$Log.err"
}
if ($cmdArgs.Count) { $spawn.ArgumentList = $cmdArgs }
Start-Process @spawn
Write-Output "Launched OmniRoute via '$exe' (log: $Log)"

if (-not (Warm-Routes -Port $Port)) { exit 1 }
