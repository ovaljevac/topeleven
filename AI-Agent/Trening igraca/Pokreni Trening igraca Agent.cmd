@echo off
setlocal
cd /d "%~dp0.."
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\TopElevenAgent.ps1" -Mode TreningIgraca
endlocal
