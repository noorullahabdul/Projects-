LM317 GEL CHARGER - FULLY LABELED TRANSIENT FINAL
=================================================

1. Extract the package into a new empty folder.
2. Keep these files together:
   - gel_charger_transient_labeled_final.sch
   - LM317_Gel_Charger_Transient_Models.lib
3. Open the .sch file in Qucs-S 26.1.
4. Select ngspice and press F2.
5. Close the ngspice log after the run completes.
6. The four embedded Cartesian plots use only labeled nets or dedicated probes.

Do not rename the schematic before the first simulation because the internal
DataSet name is gel_charger_transient_labeled_final.dat.

If a plot is manually recreated, choose these vectors from the Dataset list:
- tran.v(vin_in)
- tran.v(vout_bat_pos)
- tran.v(adj_ctrl)
- tran.v(bat_return)
- tran.i(pr_chg)
- tran.i(pr_red)
