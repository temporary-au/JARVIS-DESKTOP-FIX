@echo off
setlocal
cd /d "%~dp0.."
if not exist "JARVIS.exe" (
  echo JARVIS.exe was not found. Build the Windows USB package first.
  pause
  exit /b 1
)
start "JARVIS HTML Core" /min "%~dp0..\JARVIS.exe" --web
 timeout /t 3 /nobreak >nul
endlocal
