@echo off
title Text2Audio
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Text2Audio is not installed yet.
  echo Please double-click "Install Text2Audio.bat" first.
  echo.
  pause
  exit /b 1
)
if exist "C:\Program Files\eSpeak NG\libespeak-ng.dll" set "PHONEMIZER_ESPEAK_LIBRARY=C:\Program Files\eSpeak NG\libespeak-ng.dll"
if exist "C:\Program Files\eSpeak NG\espeak-ng.exe" set "PHONEMIZER_ESPEAK_PATH=C:\Program Files\eSpeak NG\espeak-ng.exe"
echo Starting Text2Audio... your browser will open in a moment.
echo Keep this window open while you use the app. Close it to stop.
".venv\Scripts\python.exe" server.py
pause
