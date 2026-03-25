Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c """ & WScript.Arguments(0) & """", 0, False
