# LT8304 isolated dual-secondary flyback

Open **Model.asc** in LTspice, press Run, and load **Model.plt**. Keep all files in this model folder together.

## Selected source

`Draft1.asc` from the uploaded Pheonixs.zip. The original is retained unchanged under `source/`.

## Working-copy notes

- Uses Draft1.asc, whose saved log completed, rather than the interrupted DC2393A or floating-driver variants.
- 48 V input, 20 uH primary, 11 uH and 1.2 uH secondaries and 200 ohm output loads are retained.
- Output labels were added at the actual capacitor pins; rail voltages are not asserted from the filename.

The retained historical RAW ends at 100 ms, whereas this source/working copy requests 10 ms. Treat it as an earlier run snapshot. New output labels attach to C2 and C5 positive pins; voltages are not asserted from the component ratios. Verify startup, output regulation, switch stress and both rail loads in a fresh LTspice run.

## Plot expressions

- `V(IN)`
- `V(VOUT_MAIN)`
- `V(VOUT_AUX)`
- `I(L1)`

## Status

Local declared dependencies and stated structural checks pass. Fresh native LTspice execution and plot import were not performed here. These are circuit simulations/models, not bench measurements or production qualification.
