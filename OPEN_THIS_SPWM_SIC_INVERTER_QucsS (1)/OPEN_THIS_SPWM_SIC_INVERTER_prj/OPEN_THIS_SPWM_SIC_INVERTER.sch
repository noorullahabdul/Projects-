<Qucs Schematic 0.0.24>
<Properties>
 <View=0,0,2300,1120,0.72,0,0>
 <Grid=10,10,1>
 <DataSet=SPWM_SIC_CLEAN.dat>
 <DataDisplay=SPWM_SIC_CLEAN.dpl>
 <OpenDisplay=0>
 <Script=SPWM_SIC_CLEAN.m>
 <RunScript=0>
 <showFrame=0>
 <FrameText0=Three-Phase SPWM SiC Inverter>
 <FrameText1=750 V DC link, 40 kHz SPWM, 50 Hz output>
 <FrameText2=Qucs-S / ngspice>
 <FrameText3=Clean labeled schematic>
</Properties>
<Symbol>
</Symbol>
<Components>

 <SpLib XSPWM 1 230 250 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "SPWM_3PH_QS" 1 "auto" 0 "FOUT=50 FSW=40k MA=0.85 ACAR=1 VLOGIC=5 TDEAD=500n ROUT=10" 0 "" 0>

 <Vdc VEN 1 220 500 -64 -26 0 1 "5 V" 1>

 <SpLib XDRV_A 1 570 200 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "SIC_DUAL_GATE_DRIVER" 1 "auto" 0 "VON=18 VOFF=-3.5 VINTH=2.5 ENTH=2.5 RG_H=5 RG_L=5 RGS=10k TPD=80n" 0 "" 0>
 <SpLib XDRV_B 1 570 390 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "SIC_DUAL_GATE_DRIVER" 1 "auto" 0 "VON=18 VOFF=-3.5 VINTH=2.5 ENTH=2.5 RG_H=5 RG_L=5 RGS=10k TPD=80n" 0 "" 0>
 <SpLib XDRV_C 1 570 580 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "SIC_DUAL_GATE_DRIVER" 1 "auto" 0 "VON=18 VOFF=-3.5 VINTH=2.5 ENTH=2.5 RG_H=5 RG_L=5 RGS=10k TPD=80n" 0 "" 0>

 <Vdc VDC 1 970 260 -64 -26 0 1 "750 V" 1>
 <C CDC 1 1070 260 17 -26 0 1 "2200 uF" 1 "" 0 "neutral" 0>

 <SpLib QAH 1 1290 230 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>
 <SpLib QAL 1 1290 410 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>

 <SpLib QBH 1 1510 230 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>
 <SpLib QBL 1 1510 410 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>

 <SpLib QCH 1 1730 230 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>
 <SpLib QCL 1 1730 410 -31 -66 0 0 "SPWM_SIC_QucsS_Models.lib" 0 "UF3C120040K4S_QS" 1 "auto" 0 "" 0 "" 0>

 <L LA 1 1160 700 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLA 1 1260 790 15 -26 0 1 "20 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <R RDA 1 1360 760 15 -26 0 1 "2 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <C CFA 1 1360 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>

 <L LB 1 1530 700 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLB 1 1630 790 15 -26 0 1 "20 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <R RDB 1 1730 760 15 -26 0 1 "2 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <C CFB 1 1730 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>

 <L LC 1 1900 700 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLC 1 2000 790 15 -26 0 1 "20 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <R RDC 1 2100 760 15 -26 0 1 "2 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
 <C CFC 1 2100 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>

 <R RNEUT 1 2200 930 15 -26 0 1 "100 MOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>

 <GND * 1 230 365 0 0 0 0>
 <GND * 1 220 560 0 0 0 0>
 <GND * 1 570 675 0 0 0 0>
 <GND * 1 970 470 0 0 0 0>
 <GND * 1 1070 470 0 0 0 0>
 <GND * 1 2200 1000 0 0 0 0>

 <.TR TR1 1 80 860 0 77 0 0 "lin" 1 "0" 1 "60 ms" 1 "300001" 0 "Gear" 0 "2" 0 "200 ns" 0 "1e-16" 0 "150" 0 "0.0001" 0 "1 pA" 0 "1 uV" 0 "27" 0 "1e-3" 0 "1e-6" 0 "1" 0 "CroutLU" 0 "no" 0 "yes" 0 "0" 0>

</Components>
<Wires>

 <230 340 230 365 "" 0 0 0 "">

 <350 200 405 200 "PWM_AH" 365 170 0 "">
 <350 220 405 220 "PWM_AL" 365 245 0 "">
 <350 240 405 240 "PWM_BH" 365 210 0 "">
 <350 260 405 260 "PWM_BL" 365 285 0 "">
 <350 280 405 280 "PWM_CH" 365 250 0 "">
 <350 300 405 300 "PWM_CL" 365 325 0 "">

 <110 215 70 215 "VREF_A" 65 185 0 "">
 <110 245 70 245 "VREF_B" 65 235 0 "">
 <110 275 70 275 "VREF_C" 65 285 0 "">
 <110 305 70 305 "VCARRIER" 65 325 0 "">

 <220 470 220 440 "ENABLE_5V" 235 445 0 "">
 <220 530 220 560 "" 0 0 0 "">

 <485 165 445 165 "PWM_AH" 445 135 0 "">
 <485 190 445 190 "PWM_AL" 445 215 0 "">
 <485 220 445 220 "ENABLE_5V" 435 245 0 "">
 <570 275 570 300 "" 0 0 0 "">
 <570 300 570 675 "DC_NEG" 580 615 0 "">
 <655 165 705 165 "GH_A" 660 135 0 "">
 <655 190 705 190 "SH_A" 660 215 0 "">
 <655 215 705 215 "GL_A" 660 185 0 "">
 <655 240 705 240 "SL_A" 660 265 0 "">

 <485 355 445 355 "PWM_BH" 445 325 0 "">
 <485 380 445 380 "PWM_BL" 445 405 0 "">
 <485 410 445 410 "ENABLE_5V" 435 435 0 "">
 <570 465 570 490 "" 0 0 0 "">
 <570 490 570 675 "DC_NEG" 580 615 0 "">
 <655 355 705 355 "GH_B" 660 325 0 "">
 <655 380 705 380 "SH_B" 660 405 0 "">
 <655 405 705 405 "GL_B" 660 375 0 "">
 <655 430 705 430 "SL_B" 660 455 0 "">

 <485 545 445 545 "PWM_CH" 445 515 0 "">
 <485 570 445 570 "PWM_CL" 445 595 0 "">
 <485 600 445 600 "ENABLE_5V" 435 625 0 "">
 <570 655 570 675 "" 0 0 0 "">
 <655 545 705 545 "GH_C" 660 515 0 "">
 <655 570 705 570 "SH_C" 660 595 0 "">
 <655 595 705 595 "GL_C" 660 565 0 "">
 <655 620 705 620 "SL_C" 660 645 0 "">

 <970 230 970 150 "DC_POS" 980 170 0 "">
 <970 290 970 470 "DC_NEG" 980 440 0 "">
 <1070 230 1070 150 "DC_POS" 1080 170 0 "">
 <1070 290 1070 470 "DC_NEG" 1080 440 0 "">
 <970 150 1730 150 "DC_POS" 1320 120 0 "">
 <970 470 1730 470 "DC_NEG" 1320 500 0 "">

 <1290 175 1290 150 "" 0 0 0 "">
 <1290 285 1290 320 "VPOLE_A" 1300 300 0 "">
 <1290 355 1290 320 "" 0 0 0 "">
 <1290 465 1290 470 "" 0 0 0 "">
 <1235 230 1190 230 "GH_A" 1190 200 0 "">
 <1235 260 1190 260 "SH_A" 1190 285 0 "">
 <1235 410 1190 410 "GL_A" 1190 380 0 "">
 <1235 440 1190 440 "SL_A" 1190 465 0 "">

 <1510 175 1510 150 "" 0 0 0 "">
 <1510 285 1510 320 "VPOLE_B" 1520 300 0 "">
 <1510 355 1510 320 "" 0 0 0 "">
 <1510 465 1510 470 "" 0 0 0 "">
 <1455 230 1410 230 "GH_B" 1410 200 0 "">
 <1455 260 1410 260 "SH_B" 1410 285 0 "">
 <1455 410 1410 410 "GL_B" 1410 380 0 "">
 <1455 440 1410 440 "SL_B" 1410 465 0 "">

 <1730 175 1730 150 "" 0 0 0 "">
 <1730 285 1730 320 "VPOLE_C" 1740 300 0 "">
 <1730 355 1730 320 "" 0 0 0 "">
 <1730 465 1730 470 "" 0 0 0 "">
 <1675 230 1630 230 "GH_C" 1630 200 0 "">
 <1675 260 1630 260 "SH_C" 1630 285 0 "">
 <1675 410 1630 410 "GL_C" 1630 380 0 "">
 <1675 440 1630 440 "SL_C" 1630 465 0 "">

 <1105 700 1060 700 "VPOLE_A" 1060 670 0 "">
 <1190 700 1260 700 "VA_FILT" 1210 670 0 "">
 <1260 700 1260 760 "" 0 0 0 "">
 <1260 820 1260 900 "N_FLOAT" 1270 875 0 "">
 <1260 700 1360 700 "" 0 0 0 "">
 <1360 700 1360 730 "" 0 0 0 "">
 <1360 790 1360 820 "" 0 0 0 "">
 <1360 880 1360 900 "N_FLOAT" 1370 875 0 "">

 <1475 700 1430 700 "VPOLE_B" 1430 670 0 "">
 <1560 700 1630 700 "VB_FILT" 1580 670 0 "">
 <1630 700 1630 760 "" 0 0 0 "">
 <1630 820 1630 900 "N_FLOAT" 1640 875 0 "">
 <1630 700 1730 700 "" 0 0 0 "">
 <1730 700 1730 730 "" 0 0 0 "">
 <1730 790 1730 820 "" 0 0 0 "">
 <1730 880 1730 900 "N_FLOAT" 1740 875 0 "">

 <1845 700 1800 700 "VPOLE_C" 1800 670 0 "">
 <1930 700 2000 700 "VC_FILT" 1950 670 0 "">
 <2000 700 2000 760 "" 0 0 0 "">
 <2000 820 2000 900 "N_FLOAT" 2010 875 0 "">
 <2000 700 2100 700 "" 0 0 0 "">
 <2100 700 2100 730 "" 0 0 0 "">
 <2100 790 2100 820 "" 0 0 0 "">
 <2100 880 2100 900 "N_FLOAT" 2110 875 0 "">

 <2200 900 2200 900 "N_FLOAT" 2170 875 0 "">
 <2200 960 2200 1000 "" 0 0 0 "">

</Wires>
<Diagrams>
</Diagrams>
<Paintings>
 <Text 45 30 18 #000080 0 "THREE-PHASE SPWM SIC INVERTER - CLEAN QUCS-S SCHEMATIC">
 <Text 45 65 11 #000000 0 "750 VDC | 40 kHz SPWM | 50 Hz | MA=0.85 | 500 ns deadtime | 18 V / -3.5 V gate drive">
 <Text 45 105 12 #000080 0 "1. SPWM AND CONTROL">
 <Text 445 105 12 #000080 0 "2. ISOLATED DUAL GATE DRIVERS">
 <Text 930 105 12 #000080 0 "3. DC LINK AND THREE-PHASE SIC BRIDGE">
 <Text 1010 625 12 #000080 0 "4. SYMMETRICAL LC FILTER AND STAR LOAD">
 <Text 85 790 11 #000000 0 "Transient: 0 to 60 ms; max step 200 ns. Select ngspice and press F2.">
 <Text 85 940 10 #000000 0 "Repeated net labels make electrical connections without long crossing wires. All three output phases use identical 2 mH, 10 uF, 2 Ohm damping and 20 Ohm load branches.">
 <Text 85 975 10 #000000 0 "The bundled SiC model is a functional surrogate because the original external Level2010.txt manufacturer model was not embedded in the uploaded QSPICE file.">
</Paintings>
