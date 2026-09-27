# Removes the weekly README stats refresh scheduled task.
# Run:  powershell -ExecutionPolicy Bypass -File scripts\uninstall-stats-task.ps1
$ErrorActionPreference = "Stop"
$TaskName = "Delegate Stats Refresh"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task '$TaskName'."
} else {
    Write-Host "No scheduled task named '$TaskName' found."
}
