# Set A Ngspice low-pass filter bundle

## Included cases
- `SetA_Base_30dB.cir`: Set A base limits (≤1.5 dB loss at 1 kHz; ≥30 dB attenuation at 10 kHz).
- `SetA_G2_45dB.cir`: same Set A conditions with the added G2 target (≥45 dB at 10 kHz).
- `*_reference.csv` and `reference_response.png`: analytical response for the buffered RC cascade, normalized to its 10 Hz gain. These are reference predictions, not Ngspice run logs.
- `first_order_sanity.txt`: single-pole calculation showing why changing only R/C cannot meet the stopband target.

## Run
From this folder, run `ngspice -b SetA_Base_30dB.cir` and `ngspice -b SetA_G2_45dB.cir`. Each run writes its own `*_ac.csv` AC sweep file.

## Circuit assumptions
Both files use Rs=1 kΩ, RL=100 kΩ, 0–3.3 V signal range, and a 3.3 V supply. Each RC section is 10 kΩ and 3.3 nF, with a buffer between sections. Five sections target the 30 dB base case; seven sections target the 45 dB G2 case. The included generic rail-clamped op-amp macro-model has 10 MHz gain-bandwidth and 10 Ω output resistance; it is for educational simulation, not a substitute for a supplied manufacturer model when one is required.

The reference calculation predicts approximately 0.96 dB passband loss and 36 dB stopband attenuation for the base case; the G2 case predicts approximately 1.33 dB and 51 dB, respectively. Confirm with the Ngspice output before relying on these results.
