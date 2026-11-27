@echo off
setlocal
cd /d "%~dp0.."
if exist "%~dp0..\JARVIS.exe" (
  start "" "%~dp0..\JARVIS.exe"
) else (
  echo JARVIS.exe has not been built yet.
  echo Build it using the included GitHub Actions workflow, or run from source.
  pause
)
endlocal
