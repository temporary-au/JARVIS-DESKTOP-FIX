@echo off
setlocal
cd /d "%~dp0.."
if not exist "JARVIS.exe" (
  echo JARVIS.exe was not found. Build the Windows desktop package first.
  pause
  exit /b 1
)
start "JARVIS Desktop Web Companion" /min "%~dp0..\JARVIS.exe" --web
timeout /t 3 /nobreak >nul
endlocal
