@echo off
setlocal
cd /d "%~dp0"
set "PYTHON=python"
where py >nul 2>nul
if not errorlevel 1 set "PYTHON=py -3"
%PYTHON% tools\inspect_models.py
if errorlevel 1 goto failed
%PYTHON% tools\test_helpers.py
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Validation failed. See above.
pause
exit /b 1
