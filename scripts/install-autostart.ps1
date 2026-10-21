# Registers a Scheduled Task that keeps the OmniRoute gateway up (Windows).
# Run once:  powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1
#
# WHY THIS IS NOT JUST A LOGON TRIGGER. It was, and the gateway died on
# 2026-10-15 with LastTaskResult 0xC000013A (process terminated) and stayed dead
# for six days, because a logon task that has already run will not run again.
# Nothing noticed: the free -> deepseek escalation absorbed every failure, so the
# only symptom was 18 of 19 free attempts failing, ~744s burned on retries, and
# 16 runs quietly billed to the paid tier. A fallback good enough to hide an
# outage needs something that notices the outage.
#
# start-omniroute.ps1 exits early when the port is already listening, so
# re-running it on a schedule costs a port check and is the cheapest thing that
# actually brings a dead gateway back.
$ErrorActionPreference = "Stop"

$TaskName = "OmniRoute Gateway"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Starter  = Join-Path $ScriptDir "start-omniroute.ps1"

if (-not (Test-Path $Starter)) { Write-Error "Missing $Starter"; exit 1 }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Starter`""

# Two triggers. At logon, plus a short delay so the network is up...
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$logonTrigger.Delay = "PT15S"

# ...and every 15 minutes forever, which is the one that heals a gateway that
# died mid-session. A logon trigger alone cannot: it has already fired.
# Repetition is expressed as a -Once trigger with an interval, because adding a
# Repetition pattern to a logon trigger is not supported by this cmdlet.
$repeatTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 15)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action `
    -Trigger @($logonTrigger, $repeatTrigger) `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host "Registered scheduled task '$TaskName' (at logon, then every 15 min)."
Write-Host "The 15-minute check is a no-op while the gateway is listening; it exists so a"
Write-Host "gateway that dies mid-session comes back without you noticing it was gone."
Write-Host "Start it now without rebooting:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "Remove it later:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1"
