@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0TopElevenManager.ps1"
endlocal
