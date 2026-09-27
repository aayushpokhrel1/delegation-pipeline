# Registers a Scheduled Task that refreshes the README stats block weekly (Windows).
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\install-stats-task.ps1
$ErrorActionPreference = "Stop"

$TaskName = "Delegate Stats Refresh"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Refresher = Join-Path $ScriptDir "refresh-stats.ps1"

if (-not (Test-Path $Refresher)) { Write-Error "Missing $Refresher"; exit 1 }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Refresher`""

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
