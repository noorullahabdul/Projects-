# Imported DC-link telemetry

UTF-8 CSV; UTF-8 with BOM is accepted. First line contains unique column names.
At least two rows; time must be nonnegative and strictly increasing. Required
measurements must be finite. No automatic unit conversion is performed.

| Column | Unit / value | Meaning |
| --- | --- | --- |
| time_s | seconds | Common monotonic timebase |
| vpack_v | V, positive | Battery voltage |
| vdc_v | V, nonnegative | Actual/reference DC-link voltage |
| pre_current_a | A, signed | Precharge-branch current |
| wake | 0 or 1 | Wake command |
| neg_aux | 0 or 1 | Negative main closed feedback |
| pos_aux | 0 or 1 | Positive main closed feedback |
| pre_aux | 0 or 1 | Precharge closed feedback |
| discharge_cmd | 0 or 1 | Active discharge command |
| torque_enable | 0 or 1 | Supervisor torque permission |
| fault | optional text | Observed diagnostic code |

Additional columns are preserved but not used for acceptance checks.
Simulation output includes state, sensed_vdc_v and shutdown for inspection.
The analyzer evaluates vdc_v; it does not substitute the biased sensor
channel for reference voltage.

A record with a missing startup/closure/discharge event cannot receive a
complete-cycle pass. A gap larger than 20 ms marks sampling evidence
incomplete. Discharge timing uses interpolation at the 60 V crossing.

Voltage/current acquisition bandwidth and sensor calibration must be supplied
separately for real logs. A coarse CSV cannot establish the true analog inrush
peak between samples.
