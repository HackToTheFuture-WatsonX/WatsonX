'' Launch.vbs
'' Starts the Background Check Report Automation app using pythonw.exe
'' so no console / terminal window appears alongside the Tkinter UI.
''
'' Double-click this file to open the app without a black command window.

Dim shell
Set shell = CreateObject("WScript.Shell")

'' Resolve the folder containing this script
Dim scriptDir
scriptDir = Left(WScript.ScriptFullName, _
            Len(WScript.ScriptFullName) - Len(WScript.ScriptName))

'' Run pythonw (windowless Python) — the empty "" as second arg is the window
'' style (unused for pythonw); False = do not wait for the process to finish.
shell.Run "pythonw """ & scriptDir & "pdf_extractor_ui.py""", 0, False

Set shell = Nothing
