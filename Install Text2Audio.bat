@echo off
title Text2Audio Installer
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1"
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" (
  echo Setup did not finish. Please read the message above.
  echo You can copy it and send it to john@jmsdevlab.com if you need help.
) else (
  echo Setup finished.
)
echo.
echo Press any key to close this window.
pause >nul
exit /b %RC%
