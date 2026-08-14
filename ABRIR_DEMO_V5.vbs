Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
shell.Run Chr(34) & fso.BuildPath(root, "ABRIR_DEMO_V5.bat") & Chr(34), 0, False
