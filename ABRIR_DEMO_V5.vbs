Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
pythonw = fso.BuildPath(root, ".venv\Scripts\pythonw.exe")
If Not fso.FileExists(pythonw) Then
    MsgBox "No se encontró el entorno V5 en .venv\Scripts\pythonw.exe", 16, "Inspección Visual V5"
    WScript.Quit 2
End If
shell.CurrentDirectory = root
command = Chr(34) & pythonw & Chr(34) & " -m inspection_v5.qt_app --root " & Chr(34) & root & Chr(34) & " --camera -1 --fullscreen"
shell.Run command, 0, False
