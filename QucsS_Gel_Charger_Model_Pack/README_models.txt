Model pack for the Qucs-S LM317T gel-battery charger task.

Files:
- LM317T_QucsS_DC.lib
  Original functional DC model intended for operating-point and DC-sweep validation.
- 2N2222A_ONsemi.lib
  Manufacturer-provided ON Semiconductor SPICE device model.
- GelBattery_Thevenin.lib
  Original two-terminal battery Thevenin subcircuit.
- QucsS_symbol_mapping.txt
  Exact symbol and pin mapping instructions.

Important:
The LM317T model is deliberately a functional DC model rather than a thermal,
transient, or production-accuracy regulator model. Its default 1.0 V dropout
parameter permits the task's required 15 V input / 13.8 V output verification.
Repeat the nominal test with VDROP=2.0 to document realistic headroom sensitivity.
