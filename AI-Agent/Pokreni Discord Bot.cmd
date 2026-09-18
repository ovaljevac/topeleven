@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0discord_config.json" goto :find_python
echo Discord bot jos nije konfigurisan. Otvaram postavljanje...
powershell.exe -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0Postavi Discord Bot.ps1"
if errorlevel 1 goto :pause

:find_python
py.exe -3 --version >nul 2>&1
if not errorlevel 1 (
  py.exe -3 "%~dp0discord_bot.py"
  goto :finished
)
python.exe --version >nul 2>&1
if not errorlevel 1 (
  python.exe "%~dp0discord_bot.py"
  goto :finished
)
echo Python 3 nije instaliran ili nije dostupan u PATH-u.
echo Instaliraj Python 3 sa python.org i oznaci "Add Python to PATH".
goto :pause

:finished
if not errorlevel 1 goto :eof
echo.
echo Discord bot se nije mogao pokrenuti. Procitaj poruku iznad.

:pause
pause
endlocal
