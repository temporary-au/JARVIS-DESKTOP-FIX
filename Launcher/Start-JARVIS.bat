@echo off
setlocal
cd /d "%~dp0.."
if exist "JARVIS.exe" (
  start "" "%CD%\JARVIS.exe"
) else (
  echo JARVIS.exe has not been built yet.
  echo Build it from the included GitHub Actions desktop workflow.
  pause
)
endlocal
