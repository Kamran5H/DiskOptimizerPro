' Disk Optimizer Pro portable launcher
Option Explicit
Dim WshShell, fso, q, appDir, pyw, script, portableExe
q = Chr(34)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
portableExe = appDir & "\DiskOptimizerPro.exe"
WshShell.CurrentDirectory = appDir
If fso.FileExists(portableExe) Then
    WshShell.Run q & portableExe & q, 1, False
    WScript.Quit
End If

script = appDir & "\launcher.pyw"
If Not fso.FileExists(script) Then
    MsgBox "Disk Optimizer Pro files were not found next to this launcher.", vbExclamation, "Disk Optimizer Pro"
    WScript.Quit 1
End If

' Dynamically discover pythonw.exe
Dim localAppData, pyFolder, subFolder
pyw = ""
localAppData = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
If fso.FolderExists(localAppData & "\Programs\Python") Then
    Set pyFolder = fso.GetFolder(localAppData & "\Programs\Python")
    For Each subFolder In pyFolder.SubFolders
        If fso.FileExists(subFolder.Path & "\pythonw.exe") Then
            pyw = subFolder.Path & "\pythonw.exe"
        End If
    Next
End If

If pyw = "" Or Not fso.FileExists(pyw) Then
    pyw = "pythonw.exe"
End If

On Error Resume Next
WshShell.Run q & pyw & q & " " & q & script & q, 0, False
If Err.Number <> 0 Then
    MsgBox "No Python runtime was found. Use the packaged DiskOptimizerPro.exe or install Python and the app requirements.", vbExclamation, "Disk Optimizer Pro"
End If
