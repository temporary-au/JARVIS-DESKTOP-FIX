@echo off
setlocal
 title JARVIS USB Preparation
cd /d "%~dp0"
echo ========================================
echo        JARVIS USB PREPARATION
echo ========================================
echo.
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows PowerShell could not be found.
  pause
  exit /b 1
)
if not exist "%~dp0Prepare-USB.ps1" (
  echo ERROR: Prepare-USB.ps1 is missing.
  echo Put Setup-USB.bat and Prepare-USB.ps1 in the same JARVIS_USB folder.
  pause
  exit /b 1
)
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0Prepare-USB.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Setup ended with error code %RESULT%.
if "%RESULT%"=="0" echo Setup finished.
echo.
pause
exit /b %RESULT%
