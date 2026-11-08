' Launches a command with no console window at all, for scheduled tasks that run in
' an interactive session. cmd.exe and powershell.exe both create a real console when
' the Task Scheduler starts them as the logged-on user, which pops a terminal on the
' desktop every time the task fires; powershell's own -WindowStyle Hidden is applied
' only AFTER the console exists, so it still flashes. WScript.Shell.Run with window
' style 0 creates the process with no window in the first place.
'
' The windowless alternative is registering the task with an S4U principal ("run
' whether user is logged on or not"), which runs it in session 0. That needs
' elevation, and it also loses access to DPAPI-protected user secrets, so anything
' using Windows Credential Manager (a git push over HTTPS, say) breaks there. This
' wrapper keeps the task in the user session and only hides the window.
'
' This file is the tracked source. install-autostart.ps1 and install-stats-task.ps1 copy it
' to %USERPROFILE%\.local\bin\run-hidden.vbs and register their tasks against that path, so
' the launcher survives moving this checkout and other machine-level tasks can share it (the
' whereami repo's "wipboard push" task uses the same copy). Edit it here, then re-run an
' installer; editing the installed copy loses the change.
'
' Usage: wscript.exe run-hidden.vbs "<exe>" "<arg1>" "<arg2>" ...
' Each argument is re-quoted, so paths with spaces survive.
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count = 0 Then WScript.Quit 2
cmd = """" & WScript.Arguments(0) & """"
For i = 1 To WScript.Arguments.Count - 1
  cmd = cmd & " """ & WScript.Arguments(i) & """"
Next
WScript.Quit sh.Run(cmd, 0, True)
