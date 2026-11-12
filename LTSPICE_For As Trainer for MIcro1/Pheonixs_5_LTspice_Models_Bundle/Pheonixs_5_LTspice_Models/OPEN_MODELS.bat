@echo off
setlocal
cd /d "%~dp0"
:menu
cls
echo PHEONIXS - FIVE LTSPICE MODELS
echo.
echo 1. LT8584 active cell balancer
echo 2. LTC3300-1 six-cell bidirectional balancer
echo 3. LT8304 isolated dual-secondary flyback
echo 4. LTC7851 four-phase VRM load transient
echo 5. 12-bit sample-and-hold / quantizer model
echo 0. Exit
echo.
choice /c 123450 /n /m "Select a model: "
if errorlevel 6 exit /b 0
if errorlevel 5 goto model5
if errorlevel 4 goto model4
if errorlevel 3 goto model3
if errorlevel 2 goto model2
if errorlevel 1 goto model1
:model1
start "" "models\01_LT8584_Cell_Balancer\Model.asc"
goto menu
:model2
start "" "models\02_LTC3300_6Cell_Balancer\Model.asc"
goto menu
:model3
start "" "models\03_LT8304_Isolated_Flyback\Model.asc"
goto menu
:model4
start "" "models\04_LTC7851_4Phase_VRM\Model.asc"
goto menu
:model5
start "" "models\05_12bit_ADC_Sampling\Model.asc"
goto menu
