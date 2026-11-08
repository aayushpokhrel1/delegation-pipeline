# Registers a Scheduled Task that refreshes the README stats block weekly (Windows).
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\install-stats-task.ps1
$ErrorActionPreference = "Stop"

$TaskName = "Delegate Stats Refresh"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Refresher = Join-Path $ScriptDir "refresh-stats.ps1"

if (-not (Test-Path $Refresher)) { Write-Error "Missing $Refresher"; exit 1 }

# Launched through run-hidden.vbs, which gives the task no console window at all. A task
# registered under the logged-on user pops a real terminal on the desktop every time its
# action is powershell.exe or a .cmd, and -WindowStyle Hidden does not prevent it: the
# console exists before the style is applied, so it still flashes. See run-hidden.vbs for
# why this and not an S4U principal. The installed copy is used, not this checkout's, so
# moving the checkout does not break the launcher.
$Hidden = Join-Path $HOME ".local\bin\run-hidden.vbs"
New-Item -ItemType Directory -Force -Path (Split-Path $Hidden) | Out-Null
Copy-Item (Join-Path $ScriptDir "run-hidden.vbs") $Hidden -Force

$action = New-ScheduledTaskAction -Execute "wscript.exe" `
    -Argument ('"{0}" "powershell.exe" "-NoProfile" "-ExecutionPolicy" "Bypass" "-File" "{1}"' -f $Hidden, $Refresher)

# Weekly, Monday morning, so the README is fresh at the start of the week.
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9am

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' (runs weekly, Mondays at 9am)."
Write-Host "Start it now without waiting:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Log:  $env:USERPROFILE\.claude\delegate-stats-refresh.log"
Write-Host "Remove it later:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-stats-task.ps1"
