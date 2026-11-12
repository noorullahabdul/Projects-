Complete the missing implementation in `/app/buckvalidate/__init__.py`, `/app/buckvalidate/raw.py`, `/app/buckvalidate/metrics.py`, and `/app/buckvalidate/cli.py`. The command `/app/run_validation.sh` must successfully process ngspice ASCII transient data described in `/app/spec/RAW_FORMAT.md`.

The CLI is:

`python3 -m buckvalidate.cli --manifest <csv> --requirements <json> --output-dir <dir>`

It must process every manifest row independently so that one invalid trace does not stop the remaining cases. Relative `raw_path` values are resolved relative to the manifest directory. Signal names are case-insensitive. When timestamps repeat, retain the final record for that timestamp and sort the resulting unique timestamps. Every signal named by `time_var`, `vout_var`, `gate_var`, `inductor_current_var`, and `load_current_var` is required; a missing required signal makes that case invalid.

Select the final transient plot in each raw file. Detect gate rising edges only inside the closed analysis interval from `analysis_start_s` through `analysis_end_s`. Compute the 5th and 95th percentiles from the gate values in that clipped interval, including linearly interpolated values at the two interval boundaries. For a percentile `q`, sort the `N` values, use position `q*(N-1)`, and linearly interpolate between the adjacent ranked values. The gate threshold is exactly the midpoint of those two percentiles. A rising edge occurs when consecutive clipped values satisfy `previous < threshold <= current`; interpolate the threshold-crossing time linearly. Calculate `fsw_hz` as the reciprocal of the median of **all** consecutive rising-edge intervals. There is no fixed minimum edge count beyond what is needed to form at least one interval and the requested steady-state window.

Use the final `steady_cycles` complete switching cycles as the steady-state window. The window starts at rising edge `-(steady_cycles + 1)` and ends at the final rising edge. Calculate `vout_avg_v` only over this steady-state window using a trapezoidal time-weighted average. Calculate `ripple_v_pp` only over this same steady-state window as maximum minus minimum output voltage, including linearly interpolated values at both window boundaries. Calculate `peak_inductor_current_a` as the maximum absolute inductor-current magnitude, `max(abs(I_L))`, over the complete closed analysis interval from `analysis_start_s` through `analysis_end_s`, including linearly interpolated values at both boundaries.

For a `startup` case, calculate `settling_time_s` from `analysis_start_s` to the first retained/interpolated point following the final excursion outside the steady-state average multiplied by `1 ± band_fraction`. The band is inclusive at both limits. The output must then remain inside that band through the beginning of the steady-state window. The clipped `analysis_start_s` boundary is an eligible point, so if the waveform never leaves the band then `settling_time_s` is `0`. If the final point at the beginning of the steady-state window is outside the band, or no following point exists, the case cannot be evaluated and must be reported as `invalid`.

For a `step` case, calculate `min_vout_v` and `max_vout_v` from `event_time_s` through the earlier of `analysis_end_s` or `post_step_observation_cycles` switching periods. Calculate `recovery_time_s` from candidate points consisting of the clipped `event_time_s` boundary followed by retained sample times. The first candidate whose waveform remains inside the inclusive final steady-state band `average * (1 ± band_fraction)` for `hold_periods` complete switching periods is the recovery point; therefore recovery may be exactly `0`. Interpolate the observation endpoint and each hold-interval endpoint linearly, but do not invent an interpolated band-entry candidate between retained samples. If no candidate leaves enough time for the complete hold interval before `analysis_end_s`, the case cannot be evaluated and must be reported as `invalid`.

Evaluate each valid case against the supplied requirements JSON. The `checks` object must use these exact Boolean keys:

- Every valid case: `switching_frequency`, `steady_state_vout`, `steady_state_ripple`, `peak_inductor_current`
- Startup cases additionally: `startup_settling`
- Step cases additionally: `step_min_vout`, `step_max_vout`, `step_recovery`

Requirement bounds are inclusive: a metric exactly equal to a configured `min` or `max` passes that bound. Set `case_pass` to true only when every applicable check is true.

For every successfully parsed and evaluated case, set `status` to `ok`, whether the electrical checks pass or fail. Use `status` equal to `invalid` only when the case cannot be parsed or evaluated.

For an invalid case, use an empty `checks` object, set `status` to `invalid`, set `case_pass` to false, leave all numeric CSV fields blank, and provide a nonempty error message.

Create `/app/output/measurements.csv` with exactly these columns in this order:

`case_id,case_type,status,case_pass,fsw_hz,vout_avg_v,ripple_v_pp,settling_time_s,min_vout_v,max_vout_v,recovery_time_s,peak_inductor_current_a,errors`

CSV Boolean values must be lowercase `true` or `false`.

Create `/app/output/validation_report.json` with exactly these top-level members:

- `schema_version` equal to 1
- `overall_pass`
- `summary` containing exactly `total_cases`, `valid_cases`, and `passed_cases`
- `cases`, containing one object per manifest row in manifest order

Each object in `cases` must contain every CSV field plus the applicable `checks` object. JSON Boolean values must be actual Booleans, blank or non-applicable numeric CSV fields must be JSON `null`, and all numeric values reported in both files must agree.

Set `overall_pass` to true only when every manifest case passes.

The supplied public sample waveforms are synthetic. The supplied run uses `/app/data/cases.csv` and `/app/data/requirements.json`. The verifier may use alternate inputs at `/app/cases.csv` and `/app/requirements.json`. Treat all four paths as input files and do not overwrite them.

After processing the manifest and writing both output files, the CLI must exit with status code 0, even when `overall_pass` is false or one or more cases are invalid or fail their requirements.

Run the supplied manifest and generate both required files under `/app/output` before finishing.
