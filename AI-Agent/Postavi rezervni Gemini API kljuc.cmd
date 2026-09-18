@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Postavi Gemini API kljuc.ps1" -Slot 2
