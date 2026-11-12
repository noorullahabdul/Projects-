@echo off
setlocal
set "LTEXE=%ProgramFiles%\ADI\LTspice\LTspice.exe"
if not exist "%LTEXE%" set "LTEXE=%LocalAppData%\Programs\ADI\LTspice\LTspice.exe"
if not exist "%LTEXE%" set "LTEXE=%ProgramFiles%\LTC\LTspiceXVII\XVIIx64.exe"
if not exist "%LTEXE%" (
  echo LTspice executable not found.
  echo Edit LTEXE in this file to match your installation.
  exit /b 1
)
echo Running nominal model...
"%LTEXE%" -b "DCLINK_CR004_NOMINAL.cir"
if errorlevel 1 exit /b 1
echo Running 972 deterministic corners...
"%LTEXE%" -b "DCLINK_CR004_CORNERS.cir"
if errorlevel 1 exit /b 1
echo Running fault campaign...
"%LTEXE%" -b "DCLINK_CR004_FAULTS.cir"
if errorlevel 1 exit /b 1
echo Completed. Review all .log files and retain the .raw files.
endlocal
