# Buck waveform CSV

UTF-8 CSV with a unique header. All required fields must be finite numbers.
At least three rows; time is nonnegative and strictly increasing.

| Column | Unit | Meaning |
| --- | --- | --- |
| time_s | s | Common measurement timebase |
| vin_v | V | Input voltage, positive |
| vout_v | V | Output voltage, nonnegative |
| inductor_a | A | Signed inductor current |
| load_a | A | Load current, nonnegative |
| duty | fraction 0–1 | Applied duty |

The default test step occurs at 0.020 s. Override it with --step-time when
analyzing an imported record. Current checks require 2 ms pre-step, 20 ms
post-step and a maximum 50 us sample gap.

Steady regulation and load power use the final 10 ms plateau with a
time-weighted trapezoidal average. Settling must reach the 2% band within
20 ms of the step and remain in band for at least 5 ms.

The analyzer reports low-frequency plateau variation. It cannot establish
true switching ripple from an averaged simulation or insufficient-bandwidth
measurement. The separate steady-state model estimates switching ripple.

The original input SHA-256 is written into analysis JSON. Unknown column names
are not silently treated as equivalent units; explicitly export or map the
required columns before import.
