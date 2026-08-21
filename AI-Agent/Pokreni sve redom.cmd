@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TopElevenAgent.ps1" -Mode Sve
endlocal
