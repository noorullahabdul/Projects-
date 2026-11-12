<Qucs Schematic 1.0.0>
<Properties>
 <View=0,0,2180,1120,0.78,0,0>
 <Grid=10,10,1>
 <DataSet=SPWM_SIC_V4_RUN_FIRST.dat>
 <DataDisplay=SPWM_SIC_V4_RUN_FIRST.dpl>
 <OpenDisplay=0>
 <Script=SPWM_SIC_V4_RUN_FIRST.m>
 <RunScript=0>
 <showFrame=0>
 <FrameText0=Three-Phase SPWM SiC Inverter>
 <FrameText1=Robust Switch Model>
 <FrameText2=ngspice>
 <FrameText3=V4>
</Properties>
<Symbol>
</Symbol>
<Components>
 <SpLib XSPWM 1 300 260 -31 -66 0 0 "SPWM_SIC_V4_MODELS.lib" 0 "SPWM_CORE" 1 "auto" 0 "FOUT=50 FSW=40k MA=0.85 ACAR=1 VLOGIC=5 DEADBAND=0.04 ROUT=10" 0 "" 0>
 <Vdc VDC 1 690 300 18 -26 0 1 "750 V" 1>
 <R RDC_ESR 1 790 220 -26 15 0 0 "50 mOhm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <C CDC 1 850 300 17 -26 0 1 "2200 uF" 1 "" 0 "neutral" 0>
 <SpLib XLEGA 1 1020 300 -31 -66 0 0 "SPWM_SIC_V4_MODELS.lib" 0 "SIC_PHASE_LEG" 1 "auto" 0 "" 0 "" 0>
 <SpLib XLEGB 1 1270 300 -31 -66 0 0 "SPWM_SIC_V4_MODELS.lib" 0 "SIC_PHASE_LEG" 1 "auto" 0 "" 0 "" 0>
 <SpLib XLEGC 1 1520 300 -31 -66 0 0 "SPWM_SIC_V4_MODELS.lib" 0 "SIC_PHASE_LEG" 1 "auto" 0 "" 0 "" 0>
 <L LA 1 1110 650 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLA 1 1210 790 15 -26 0 1 "20 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <R RDA 1 1300 730 15 -26 0 1 "2 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <C CFA 1 1300 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>
 <L LB 1 1450 650 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLB 1 1550 790 15 -26 0 1 "20 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <R RDB 1 1640 730 15 -26 0 1 "2 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <C CFB 1 1640 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>
 <L LC 1 1790 650 -26 10 0 0 "2 mH" 1 "" 0>
 <R RLC 1 1890 790 15 -26 0 1 "20 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <R RDC 1 1980 730 15 -26 0 1 "2 Ohm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <C CFC 1 1980 850 17 -26 0 1 "10 uF" 1 "" 0 "neutral" 0>
 <R RNEUT 1 2070 1010 15 -26 0 1 "1 MOhm" 1 "27" 0 "0.0" 0 "0.0" 0 "27" 0 "european" 0>
 <GND * 1 300 390 0 0 0 0>
 <GND * 1 690 420 0 0 0 0>
 <GND * 1 850 420 0 0 0 0>
 <GND * 1 2070 1070 0 0 0 0>
 <.TR TR1 1 100 650 0 71 0 0 "lin" 1 "0" 1 "5 ms" 1 "25001" 0 "Gear" 0 "2" 0 "200 ns" 0 "1e-16" 0 "150" 0 "0.001" 0 "1 pA" 0 "1 uV" 0 "27" 0 "1e-3" 0 "1e-6" 0 "1" 0 "CroutLU" 0 "no" 0 "yes" 0 "0" 0>
</Components>
<Wires>
 <300 350 300 390 "" 0 0 0 "">
 <180 210 130 210 "VREF_A" 135 185 0 "">
 <180 240 130 240 "VREF_B" 135 215 0 "">
 <180 270 130 270 "VREF_C" 135 245 0 "">
 <180 300 130 300 "VCARRIER" 135 275 0 "">
 <420 210 480 210 "PWM_AH" 430 185 0 "">
 <420 230 480 230 "PWM_AL" 430 205 0 "">
 <420 250 480 250 "PWM_BH" 430 225 0 "">
 <420 270 480 270 "PWM_BL" 430 245 0 "">
 <420 290 480 290 "PWM_CH" 430 265 0 "">
 <420 310 480 310 "PWM_CL" 430 285 0 "">
 <690 270 690 220 "DC_POS" 700 195 0 "">
 <690 220 760 220 "" 0 0 0 "">
 <820 220 1520 220 "" 0 0 0 "">
 <850 270 850 220 "" 0 0 0 "">
 <690 330 690 390 "DC_NEG" 700 365 0 "">
 <690 390 1520 390 "" 0 0 0 "">
 <850 330 850 390 "" 0 0 0 "">
 <690 390 690 420 "" 0 0 0 "">
 <850 390 850 420 "" 0 0 0 "">
 <1020 200 1020 220 "" 0 0 0 "">
 <1020 400 1020 390 "" 0 0 0 "">
 <1270 200 1270 220 "" 0 0 0 "">
 <1270 400 1270 390 "" 0 0 0 "">
 <1520 200 1520 220 "" 0 0 0 "">
 <1520 400 1520 390 "" 0 0 0 "">
 <945 265 900 265 "PWM_AH" 902 240 0 "">
 <945 335 900 335 "PWM_AL" 902 310 0 "">
 <1195 265 1150 265 "PWM_BH" 1152 240 0 "">
 <1195 335 1150 335 "PWM_BL" 1152 310 0 "">
 <1445 265 1400 265 "PWM_CH" 1402 240 0 "">
 <1445 335 1400 335 "PWM_CL" 1402 310 0 "">
 <1105 265 1155 265 "VGS_AH" 1110 240 0 "">
 <1105 335 1155 335 "VGS_AL" 1110 360 0 "">
 <1355 265 1405 265 "VGS_BH" 1360 240 0 "">
 <1355 335 1405 335 "VGS_BL" 1360 360 0 "">
 <1605 265 1655 265 "VGS_CH" 1610 240 0 "">
 <1605 335 1655 335 "VGS_CL" 1610 360 0 "">
 <1105 300 1105 650 "VPOLE_A" 1115 430 0 "">
 <1080 650 1105 650 "" 0 0 0 "">
 <1140 650 1300 650 "VA_FILT" 1160 625 0 "">
 <1210 650 1210 760 "" 0 0 0 "">
 <1210 820 1210 950 "" 0 0 0 "">
 <1300 650 1300 700 "" 0 0 0 "">
 <1300 760 1300 820 "" 0 0 0 "">
 <1300 880 1300 950 "" 0 0 0 "">
 <1355 300 1355 650 "VPOLE_B" 1365 430 0 "">
 <1355 650 1420 650 "" 0 0 0 "">
 <1480 650 1640 650 "VB_FILT" 1500 625 0 "">
 <1550 650 1550 760 "" 0 0 0 "">
 <1550 820 1550 950 "" 0 0 0 "">
 <1640 650 1640 700 "" 0 0 0 "">
 <1640 760 1640 820 "" 0 0 0 "">
 <1640 880 1640 950 "" 0 0 0 "">
 <1605 300 1605 650 "VPOLE_C" 1615 430 0 "">
 <1605 650 1760 650 "" 0 0 0 "">
 <1820 650 1980 650 "VC_FILT" 1840 625 0 "">
 <1890 650 1890 760 "" 0 0 0 "">
 <1890 820 1890 950 "" 0 0 0 "">
 <1980 650 1980 700 "" 0 0 0 "">
 <1980 760 1980 820 "" 0 0 0 "">
 <1980 880 1980 950 "" 0 0 0 "">
 <1210 950 2070 950 "N_FLOAT" 1580 980 0 "">
 <2070 950 2070 980 "" 0 0 0 "">
 <2070 1040 2070 1070 "" 0 0 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
 <Text 40 25 18 #000080 0 "THREE-PHASE SPWM SIC INVERTER - V4 ROBUST SWITCH MODEL">
 <Text 40 58 11 #000000 0 "750 VDC | 40 kHz SPWM | 50 Hz | standard ngspice S-switches and body diodes">
 <Text 75 115 12 #000080 0 "1. BEHAVIOURAL SPWM CORE">
 <Text 610 115 12 #000080 0 "2. DC LINK WITH 50 mOhm ESR">
 <Text 930 115 12 #000080 0 "3. THREE IDENTICAL SIC PHASE LEGS">
 <Text 1030 580 12 #000080 0 "4. PHYSICAL POLE-TO-FILTER CONNECTIONS AND STAR LOAD">
 <Text 75 610 11 #000000 0 "RUN-FIRST: 5 ms, max step 200 ns. Select ngspice and press F2.">
 <Text 75 750 10 #000000 0 "The bridge no longer uses nonlinear behavioural current sources. Each leg uses two standard S devices plus two body diodes.">
 <Text 75 780 10 #000000 0 "All DC-link, pole, filter and neutral connections are physical wires; net labels are used only for short control connections and plotting.">
</Paintings>
