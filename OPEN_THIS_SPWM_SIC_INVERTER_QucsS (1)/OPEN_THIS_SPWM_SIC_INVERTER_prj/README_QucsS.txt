SPWM SIC CLEAN QUCS-S PROJECT
=============================

MAIN SCHEMATIC
  SPWM_SIC_CLEAN.sch

MODEL LIBRARY
  SPWM_SIC_QucsS_Models.lib

CUSTOM SYMBOL FOLDER
  SPWM_SIC_QucsS_Models\
    SPWM_3PH_QS.sym
    SIC_DUAL_GATE_DRIVER.sym
    UF3C120040K4S_QS.sym

SIMULATOR
  ngspice

OPEN AND RUN
  1. Extract the complete project folder.
  2. Keep the .sch, .lib and symbol folder together.
  3. Put the complete _prj folder inside QucsWorkspace.
  4. Open SPWM_SIC_CLEAN.sch.
  5. Select ngspice.
  6. Press F2.

SCHEMATIC SECTIONS
  1. SPWM controller
  2. Three isolated dual gate drivers
  3. 750 V DC link and three SiC half bridges
  4. Three identical LC filters and star-connected loads

CONNECTION METHOD
  Repeated net labels are used instead of long crossing wires.

  PWM_AH/PWM_AL -> phase-A driver
  PWM_BH/PWM_BL -> phase-B driver
  PWM_CH/PWM_CL -> phase-C driver

  GH_A/SH_A/GL_A/SL_A -> phase-A SiC leg
  GH_B/SH_B/GL_B/SL_B -> phase-B SiC leg
  GH_C/SH_C/GL_C/SL_C -> phase-C SiC leg

  VPOLE_A/VPOLE_B/VPOLE_C -> output inductors
  VA_FILT/VB_FILT/VC_FILT -> filtered outputs
  N_FLOAT -> star-point neutral

IMPORTANT
  The original QSPICE schematic referenced an external Level2010.txt
  device model that was not embedded in the uploaded file. This bundle
  includes a functional ngspice-compatible SiC switch surrogate. Replace
  UF3C120040K4S_QS with the manufacturer's full model when required.
