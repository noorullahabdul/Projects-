<Qucs Schematic 1.0.0>
<Properties>
  <View=0,0,1900,1020,0.78,0,0>
  <Grid=10,10,1>
  <DataSet=gel_charger_transient_labeled_final.dat>
  <DataDisplay=gel_charger_transient_labeled_final.dpl>
  <OpenDisplay=0>
  <Script=gel_charger_transient_labeled_final.m>
  <RunScript=0>
  <showFrame=0>
  <FrameText0=LM317T Gel Battery Charger - Fully Labeled Transient Verification>
  <FrameText1=Qucs-S 26.1 / ngspice>
  <FrameText2=One native transient analysis with labeled nodes and current probes>
  <FrameText3=Behavioral LM317 and gel-battery profiles>
</Properties>
<Symbol>
</Symbol>
<Components>
  <SpLib XVIN 1 130 200 -30 -54 0 0 "LM317_Gel_Charger_Transient_Models.lib" 0 "VIN_PROFILE" 1 "auto" 0 "" 0 "" 0>
  <GND * 1 100 270 0 0 0 0>
  <C C1 1 210 220 17 -26 0 1 "100 nF" 1 "" 0 "neutral" 0>
  <GND * 1 210 280 0 0 0 0>
  <R R1 1 250 350 -26 15 0 0 "1 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <DIODE_SPICE D1 1 350 350 20 -18 0 0 "LED_GREEN_D" 1 "" 0 "" 0 "" 0 "" 0 "2" 1 "D" 1>
  <GND * 1 410 380 0 0 0 0>
  <SpLib XU1 1 500 200 -31 -66 0 0 "LM317_Gel_Charger_Transient_Models.lib" 0 "LM317T_QS" 1 "auto" 0 "VREF=1.25 IADJ=50u VDROP=1.0 ROUT=0.03" 0 "" 0>
  <R R4 1 630 240 15 -26 0 1 "470 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <R R_POT 1 630 350 15 -26 0 1 "2.43 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <R R3 1 630 440 15 -26 0 1 "2.2 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <C C2 1 770 335 17 -26 0 1 "100 nF" 1 "" 0 "neutral" 0>
  <SpLib XBAT 1 920 260 -30 -54 0 0 "LM317_Gel_Charger_Transient_Models.lib" 0 "GEL_BAT_PROFILE" 1 "auto" 0 "" 0 "" 0>
  <DIODE_SPICE D2 1 850 420 20 -18 0 0 "LED_RED_D" 1 "" 0 "" 0 "" 0 "" 0 "2" 1 "D" 1>
  <IProbe PR_RED 1 920 420 -10 -60 0 0>
  <R R_RED 1 1000 420 -26 15 0 0 "1 kOhm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <BJT_SPICE Q1 1 1070 450 8 -26 0 0 "3" 1 "npn" 1 "Q" 1 "Q2N2222A_NPN" 1 "" 0 "" 0 "" 0 "" 0>
  <GND * 1 1070 650 0 0 0 0>
  <IProbe PR_CHG 1 900 540 -10 -60 0 0>
  <R R_SENSE 1 950 590 15 -26 0 1 "1 Ohm" 1 "26.85" 0 "0.0" 0 "0.0" 0 "26.85" 0 "european" 0>
  <GND * 1 950 650 0 0 0 0>
  <.TR TR1 1 90 680 0 71 0 0 "lin" 1 "0" 1 "8 ms" 1 "4001" 0 "Trapezoidal" 0 "2" 0 "2 us" 0 "1e-16" 0 "150" 0 "0.001" 0 "1 pA" 0 "1 uV" 0 "27" 0 "1e-3" 0 "1e-6" 0 "1" 0 "CroutLU" 0 "no" 0 "yes" 1 "0" 0>
</Components>
<Wires>
  <100 200 100 270 "" 0 0 0 "">
  <160 200 160 160 "" 0 0 0 "">
  <160 160 470 160 "vin_in" 250 130 0 "">
  <470 160 470 170 "" 0 0 0 "">
  <210 190 210 160 "" 0 0 0 "">
  <210 160 470 160 "" 0 0 0 "">
  <210 250 210 280 "" 0 0 0 "">
  <200 160 200 350 "" 0 0 0 "">
  <200 350 220 350 "" 0 0 0 "">
  <280 350 320 350 "green_led_anode" 275 320 0 "">
  <380 350 410 350 "" 0 0 0 "">
  <410 350 410 380 "" 0 0 0 "">
  <530 170 890 170 "vout_bat_pos" 680 140 0 "">
  <630 170 630 210 "" 0 0 0 "">
  <470 230 470 300 "" 0 0 0 "">
  <470 300 820 300 "adj_ctrl" 610 275 0 "">
  <630 270 630 320 "" 0 0 0 "">
  <630 300 630 320 "" 0 0 0 "">
  <630 380 630 410 "pot_r3_junction" 650 390 0 "">
  <630 470 630 500 "" 0 0 0 "">
  <630 500 1040 500 "bat_return" 770 530 0 "">
  <770 170 770 305 "" 0 0 0 "">
  <770 365 770 500 "" 0 0 0 "">
  <890 170 890 260 "" 0 0 0 "">
  <950 260 950 500 "" 0 0 0 "">
  <820 300 820 420 "" 0 0 0 "">
  <880 420 890 420 "red_led_cathode" 810 390 0 "">
  <950 420 970 420 "red_probe_out" 915 390 0 "">
  <1030 420 1070 420 "lim_collector" 1010 390 0 "">
  <1040 450 1040 500 "" 0 0 0 "">
  <1070 480 1070 650 "" 0 0 0 "">
  <870 500 870 540 "" 0 0 0 "">
  <930 540 950 540 "sense_res_top" 930 515 0 "">
  <950 540 950 560 "" 0 0 0 "">
  <950 620 950 650 "" 0 0 0 "">
</Wires>
<Diagrams>
  <Rect 1160 80 600 230 3 #c0c0c0 1 00 1 0 0.001 0.008 1 10 1 19 1 -1 0.5 1 315 0 225 0 0 0 "Time (s)" "Voltage (V)" "Input and charger output">
    <"ngspice/tran.v(vin_in)" #0000ff 0 3 0 0 0>
    <"ngspice/tran.v(vout_bat_pos)" #ff0000 0 3 0 0 0>
  </Rect>
  <Rect 1160 340 600 230 3 #c0c0c0 1 00 1 0 0.001 0.008 1 0 1 14 1 -1 0.5 1 315 0 225 0 0 0 "Time (s)" "Voltage (V)" "LM317 adjustment and current-sense return">
    <"ngspice/tran.v(adj_ctrl)" #0000ff 0 3 0 0 0>
    <"ngspice/tran.v(bat_return)" #ff0000 0 3 0 0 0>
  </Rect>
  <Rect 1160 600 600 230 3 #c0c0c0 1 00 1 0 0.001 0.008 1 0 0.1 1.2 1 -1 0.5 1 315 0 225 0 0 0 "Time (s)" "Current (A)" "Battery charge current - PR_CHG">
    <"ngspice/tran.i(pr_chg)" #0000ff 0 3 0 0 0>
  </Rect>
  <Rect 520 700 540 180 3 #c0c0c0 1 00 1 0 0.001 0.008 1 0 0.05 0.8 1 -1 0.5 1 315 0 225 0 0 0 "Time (s)" "Current (A)" "Red LED / limiter branch current - PR_RED">
    <"ngspice/tran.i(pr_red)" #ff0000 0 3 0 0 0>
  </Rect>
</Diagrams>
<Paintings>
  <Text 70 35 18 #000080 0 "LM317T GEL BATTERY CHARGER - FULLY LABELED TRANSIENT FINAL">
  <Text 70 67 11 #000000 0 "Use ngspice. Keep this schematic and LM317_Gel_Charger_Transient_Models.lib in the same folder.">
  <Text 70 92 11 #000000 0 "All plotted points are actual electrical net labels; PR_CHG and PR_RED are dedicated current probes.">
  <Text 430 115 11 #000080 0 "LM317 pins: IN = vin_in | OUT = vout_bat_pos | ADJ = adj_ctrl">
  <Text 815 215 11 #000080 0 "Battery pins: POS = vout_bat_pos | NEG = bat_return">
  <Text 975 350 11 #800000 0 "Q1 pins: C = lim_collector | B = bat_return | E = GND(0)">
  <Text 785 455 11 #800000 0 "Limiter path: adj_ctrl -> D2 -> PR_RED -> R_RED -> Q1 collector">
  <Text 760 565 11 #000080 0 "Charge return: bat_return -> PR_CHG -> sense_res_top -> R_SENSE -> GND(0)">
  <Text 70 760 11 #000000 0 "Transient events: battery drops at 1 ms, VIN steps 15 V to 18 V at 3 ms, battery recovers at 5 ms.">
  <Text 70 790 11 #000000 0 "Net labels available in the dataset: vin_in, vout_bat_pos, adj_ctrl, bat_return, sense_res_top, lim_collector.">
  <Text 70 820 11 #000000 0 "Current vectors available in the dataset: i(pr_chg) and i(pr_red).">
  <Text 70 850 11 #800000 0 "Do not rename the schematic before the first run; the DataSet name matches this file.">
</Paintings>
