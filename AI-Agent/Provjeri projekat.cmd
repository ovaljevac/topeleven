@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Provjeri projekat.ps1"
set "result=%errorlevel%"
echo.
if not "%result%"=="0" echo Provjera projekta nije prosla.
pause
exit /b %result%
