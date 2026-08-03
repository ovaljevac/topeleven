@echo off
setlocal

echo Izaberi skriptu:
echo.
echo   1. Uzmi 25 zelenih
echo   2. Odmori ekipu
echo   3. Test od DMC-a (OG.ps1)
echo.
choice /c 123 /n /m "Pritisni 1, 2 ili 3: "

if errorlevel 3 goto testdmc
if errorlevel 2 goto odmori
if errorlevel 1 goto zeleni

:zeleni
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0TopElevenAgent.ps1" -Mode Zeleni
goto kraj

:odmori
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OdmoriEkipu.ps1"
goto kraj

:testdmc
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0OG.ps1" -Mode OdmoriEkipu

:kraj
if errorlevel 1 pause
