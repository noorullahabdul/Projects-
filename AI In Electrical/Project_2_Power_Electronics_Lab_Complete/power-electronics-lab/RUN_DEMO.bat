@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  set "PROJECT_PYTHON=python"
) else (
  set "PROJECT_PYTHON=py -3"
)
%PROJECT_PYTHON% -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10 or later is required'"
if errorlevel 1 goto failed
%PROJECT_PYTHON% -m powerlab demo --out outputs/demo
if errorlevel 1 goto failed
start "" "%~dp0outputs\demo\report.html"
echo Demo complete. The report lists design findings separately.
pause
exit /b 0
:failed
echo The demo did not complete. Read the error above.
pause
exit /b 1
