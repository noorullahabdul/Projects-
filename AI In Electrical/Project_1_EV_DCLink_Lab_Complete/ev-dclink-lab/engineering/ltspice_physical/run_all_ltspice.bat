@echo off
setlocal

rem Update this path if LTspice is installed elsewhere.
set "LTSPICE_EXE=C:\Program Files\ADI\LTspice\LTspice.exe"

if not exist "%LTSPICE_EXE%" (
  echo ERROR: LTspice executable not found at:
  echo %LTSPICE_EXE%
  echo Edit LTSPICE_EXE in this batch file and retry.
  exit /b 2
)

pushd "%~dp0"
echo Running nominal deck...
"%LTSPICE_EXE%" -b -run DCLINK_PHYSICAL_NOMINAL.cir
if errorlevel 1 goto :failed

echo Running targeted corner deck...
"%LTSPICE_EXE%" -b -run DCLINK_PHYSICAL_CORNERS.cir
if errorlevel 1 goto :failed

echo Running fault deck...
"%LTSPICE_EXE%" -b -run DCLINK_PHYSICAL_FAULTS.cir
if errorlevel 1 goto :failed

echo Completed. Review all LOG files before accepting any result.
popd
exit /b 0

:failed
echo ERROR: LTspice returned a non-zero status.
popd
exit /b 1

