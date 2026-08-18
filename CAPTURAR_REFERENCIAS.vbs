Option Explicit

Dim shell, fileSystem, root, python, command
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")
root = fileSystem.GetParentFolderName(WScript.ScriptFullName)
python = fileSystem.BuildPath(root, ".venv\Scripts\pythonw.exe")

If Not fileSystem.FileExists(python) Then
    MsgBox "La V4 todavía no está instalada. Ejecuta INSTALAR_V4.bat una vez.", vbExclamation, "Inspección Visual V4"
    WScript.Quit 1
End If

shell.Environment("Process")("PYTHONPATH") = fileSystem.BuildPath(root, "src")
command = Quote(python) & " -m inspection_v4.capture_app --root " & Quote(root)
shell.Run command, 0, False

Function Quote(value)
    Quote = Chr(34) & value & Chr(34)
End Function
