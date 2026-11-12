# LTC3300-1 six-cell bidirectional balancer

Open **Model.asc** in LTspice, press Run, and load **Model.plt**. Keep all files in this model folder together.

## Selected source

`BMS/3300-1.asc` from the uploaded Pheonixs.zip. The original is retained unchanged under `source/`.

## Working-copy notes

- Six 3.6 V cell sources and 43.2 V stack supply retained.
- Vendor default commands are 0,1,2,3,0,1 for cells 1..6; this is not a full BMS or SOC controller.
- Serial interface, watchdog and single-transformer behavior are not represented by this model, as stated in the original schematic.

The vendor symbol commands cells 1..6 with Bal_Act values 0,1,2,3,0,1: off, nonsynchronous discharge, synchronous discharge, charge, off, nonsynchronous discharge. The six cell sources remain 3.6 V each; the stack supply remains 43.2 V. Those independent sources are a model testbench, not an SOC/energy-storage plant. Serial interface and watchdog behavior are explicitly not modeled. There is no saved historical run for this schematic.

## Plot expressions

- `V(CELL1P)`
- `V(CELL6P,CELL6N)`
- `I(L1)`
- `I(L2)`

## Status

Local declared dependencies and stated structural checks pass. Fresh native LTspice execution and plot import were not performed here. These are circuit simulations/models, not bench measurements or production qualification.
