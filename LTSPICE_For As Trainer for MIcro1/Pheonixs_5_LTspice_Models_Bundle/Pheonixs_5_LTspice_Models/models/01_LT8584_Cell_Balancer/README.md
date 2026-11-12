# LT8584 active cell balancer

Open **Model.asc** in LTspice, press Run, and load **Model.plt**. Keep all files in this model folder together.

## Selected source

`BMS/LT8584.asc` from the uploaded Pheonixs.zip. The original is retained unchanged under `source/`.

## Working-copy notes

- Native 4.2 V cell and 50 V pack source retained.
- Original saved LTspice log has no stop/error marker; its raw data is included as historical simulation evidence.

Historical evidence: the included RAW ends at 1.5 ms and its log has no error/user-stop marker. This does not verify the prepared local-library copy. Probe Vbatt, Vpack and transformer currents. Source models an individual active balancer, not a complete pack BMS.

## Plot expressions

- `V(Vbatt)`
- `V(Vpack)`
- `I(L1)`
- `I(L2)`

## Status

Local declared dependencies and stated structural checks pass. Fresh native LTspice execution and plot import were not performed here. These are circuit simulations/models, not bench measurements or production qualification.
