Set WshShell = CreateObject("WScript.Shell")
Dim scriptDir
scriptDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
WshShell.Run "pythonw """ & scriptDir & "pdf_extractor_ui_v2.py""", 0, False
