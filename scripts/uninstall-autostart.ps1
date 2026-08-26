# Removes the OmniRoute autostart scheduled task.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-autostart.ps1
$ErrorActionPreference = "Stop"
$TaskName = "OmniRoute Gateway"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
} else {
    Write-Host "No scheduled task named '$TaskName' found."
}
