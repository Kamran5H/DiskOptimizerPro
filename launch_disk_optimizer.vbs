' Disk Optimizer Pro — Silent UAC-Elevated Launcher
Option Explicit
Dim WshShell, fso, q, appDir, pyw, script, candidates, cand
q = Chr(34)
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

appDir = fso.GetParentFolderName(WScript.ScriptFullName)
If Not fso.FileExists(appDir & "\launcher.pyw") Then
    candidates = Array( _
        "C:\Users\chkam\OneDrive\Desktop\02_Projects & Development\DiskOptimizerPro", _
        "C:\Users\chkam\OneDrive\Desktop\DiskOptimizerPro", _
        "C:\Users\chkam\Desktop\02_Projects & Development\DiskOptimizerPro", _
        "C:\Users\chkam\Desktop\DiskOptimizerPro" _
    )
    For Each cand In candidates
        If fso.FileExists(cand & "\launcher.pyw") Then
            appDir = cand
            Exit For
        End If
    Next
End If

Dim localAppData, pyFolder, subFolder
WshShell.CurrentDirectory = appDir
script = appDir & "\launcher.pyw"

' Dynamically discover pythonw.exe
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
    If fso.FileExists("C:\Python314\pythonw.exe") Then
        pyw = "C:\Python314\pythonw.exe"
    ElseIf fso.FileExists("C:\Python312\pythonw.exe") Then
        pyw = "C:\Python312\pythonw.exe"
    Else
        pyw = "pythonw.exe"
    End If
End If

WshShell.Run q & pyw & q & " " & q & script & q, 0, False
