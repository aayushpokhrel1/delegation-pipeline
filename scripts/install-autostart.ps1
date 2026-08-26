# Registers a Scheduled Task that launches OmniRoute at every logon (Windows).
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
$ErrorActionPreference = "Stop"

$TaskName = "OmniRoute Gateway"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Starter  = Join-Path $ScriptDir "start-omniroute.ps1"

if (-not (Test-Path $Starter)) { Write-Error "Missing $Starter"; exit 1 }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Starter`""

# At logon of the current user, plus a short delay so the network is up.
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT15S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' (runs at logon)."
Write-Host "Start it now without rebooting:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it later:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1"
