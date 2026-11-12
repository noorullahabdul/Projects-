# LTC7851 four-phase VRM load transient

Open **Model.asc** in LTspice, press Run, and load **Model.plt**. Keep all files in this model folder together.

## Selected source

`vrm_transient_core.asc` from the uploaded Pheonixs.zip. The original is retained unchanged under `source/`.

## Working-copy notes

- 12 V input and the existing four-phase power stage retained.
- Removed the separate Iload Vout 0 directive; the connected I1 source still steps from 10 A to 100 A.
- Replaced ambiguous capacitor multiplier X15 with an explicit 1500u value.
- Measurement windows exclude startup; native LTspice rerun remains required.

The source log reports a floating Vout node and failed recovery measurement. Its old scalar numbers are retained as failures, not acceptance. The prepared copy keeps only connected I1 on OUT, explicitly sets 15 x 100 uF = 1500 uF, and measures pre-step average, post-step min/max and final average. VPRE-VMIN is a voltage droop, not a settled-recovery time. Verify ripple, phase sharing, stability and stress after the native rerun.

## Plot expressions

- `V(OUT)`
- `I(L1)`
- `I(L2)`
- `I(L3)`
- `I(L4)`
- `I(I1)`

## Status

Local declared dependencies and stated structural checks pass. Fresh native LTspice execution and plot import were not performed here. These are circuit simulations/models, not bench measurements or production qualification.

The retained ideal current load draws 10 A from startup, so it can pull an initially unpowered rail below zero. The post-startup measurement windows avoid interpreting that artifact as load-step droop. Add a voltage-dependent load-enable policy before using this setup to predict physical startup. The 1500 uF bank is a scalar assumption with the original 1 mΩ ESR / 1 nH ESL retained; correlate it to an actual capacitor BOM.
