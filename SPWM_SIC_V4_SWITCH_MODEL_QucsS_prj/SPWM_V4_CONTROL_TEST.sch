<Qucs Schematic 1.0.0>
<Properties>
 <View=0,0,900,650,0.95,0,0>
 <Grid=10,10,1>
 <DataSet=SPWM_V4_CONTROL_TEST.dat>
 <DataDisplay=SPWM_V4_CONTROL_TEST.dpl>
 <OpenDisplay=0>
 <Script=SPWM_V4_CONTROL_TEST.m>
 <RunScript=0>
 <showFrame=0>
 <FrameText0=SPWM V4 Control Test>
 <FrameText1=ngspice>
 <FrameText2=40 kHz / 50 Hz>
 <FrameText3=V4>
</Properties>
<Symbol>
</Symbol>
<Components>
 <SpLib XSPWM 1 350 280 -31 -66 0 0 "SPWM_SIC_V4_MODELS.lib" 0 "SPWM_CORE" 1 "auto" 0 "FOUT=50 FSW=40k MA=0.85 ACAR=1 VLOGIC=5 DEADBAND=0.04 ROUT=10" 0 "" 0>
 <GND * 1 350 410 0 0 0 0>
 <.TR TR1 1 100 500 0 71 0 0 "lin" 1 "0" 1 "2 ms" 1 "10001" 0 "Gear" 0 "2" 0 "200 ns" 0 "1e-16" 0 "150" 0 "0.001" 0 "1 pA" 0 "1 uV" 0 "27" 0 "1e-3" 0 "1e-6" 0 "1" 0 "CroutLU" 0 "no" 0 "yes" 0 "0" 0>
</Components>
<Wires>
 <350 370 350 410 "" 0 0 0 "">
 <470 230 540 230 "PWM_AH" 480 205 0 "">
 <470 250 540 250 "PWM_AL" 480 275 0 "">
 <470 270 540 270 "PWM_BH" 480 245 0 "">
 <470 290 540 290 "PWM_BL" 480 315 0 "">
 <470 310 540 310 "PWM_CH" 480 285 0 "">
 <470 330 540 330 "PWM_CL" 480 355 0 "">
 <230 230 170 230 "VREF_A" 175 205 0 "">
 <230 260 170 260 "VREF_B" 175 250 0 "">
 <230 290 170 290 "VREF_C" 175 315 0 "">
 <230 320 170 320 "VCARRIER" 175 345 0 "">
</Wires>
<Diagrams>
</Diagrams>
<Paintings>
 <Text 40 25 18 #000080 0 "SPWM V4 CONTROL-ONLY TEST">
 <Text 40 60 11 #000000 0 "Run this first to verify reference, carrier and six PWM outputs.">
</Paintings>
