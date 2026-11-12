> This file is visible inside the task container and is authoritative for all formulas, thresholds, precedence, boundary behavior, and output mapping.

# Normative EV High-Voltage Diagnostic Rules

Implement `/app/powerup/`:

```bash
python -m powerup.cli --index /app/input/index.json --out /app/result
```

Use case values and the normative `/app/spec/diagnostic-rules.md`. Evaluate capture-local rules independently first, then apply the documented optional session rule across validated cases. Exit `0` after readable cases; non-zero only for a bad index/top level or unwritable output. Do not modify inputs or use the network.

## Input

Index: `format:"hv-powerup/1"` and `cases`. Each case has `case_id`, `capture`, positive finite `capacitance_uf`, `precharge_ohm`, and:

`ready_ratio,max_precharge_ms,aux_delay_ms,weld_dwell_ms,bounce_interval_ms,open_check_ms,open_min_rise_ratio,short_tau_factor,isolation_min_kohm,residual_abs_v,residual_ratio,safe_close_ratio,sensor_bias_abs_v,sensor_bias_ratio,sensor_bias_dwell_ms`

Limits are positive except `open_min_rise_ratio`, which may be zero; ratios are in `(0,1)`.

A case may also contain the optional pair `session_id` and `attempt`. They must be provided together. `session_id` is a non-empty string and `attempt` is a JSON integer `>=1` (booleans and floating-point substitutes are invalid). Cases without both fields are standalone. Duplicate attempt numbers are allowed and are ordered deterministically as described under the session rule.

Capture columns:

`t_ms,pack_v,link_v,pack_a,pre_cmd,pre_aux,pos_cmd,pos_aux,neg_cmd,neg_aux,iso_kohm,crash`

Values are finite; digital values exactly `0|1`. Resolve captures from the index directory. Sort by time, keep the last duplicate, require three unique times, and isolate invalid cases. Missing ID: `invalid_case_<NNNN>` by 1-based input position; the first case is `invalid_case_0001`. Digital channels start at `0`; first retained `1` is a rise. Interpolate linearly without extrapolation.

## Metrics

Use six-decimal numbers or JSON `null`.

- `precharge_start_ms`: first `pre_cmd` rise. A readable capture with no `pre_cmd` rise remains a valid case; in that situation `precharge_start_ms`, `ready_at_ms`, `ready_delay_ms`, `ready_link_v`, `peak_abs_pack_a`, `max_link_slew_v_per_ms`, and `tau_ms` are JSON `null`, while non-start-dependent metrics and diagnostic rules still evaluate.
- `ready_at_ms`: first interpolated time at/after start with `link_v >= ready_ratio*pack_v`; also `ready_delay_ms=ready_at_ms-precharge_start_ms` and interpolated `ready_link_v`.
- `final_link_ratio=final_link_v/final_pack_v`.
- The current/slew metric window begins at `precharge_start_ms` and ends at the earliest of readiness, `precharge_start_ms+max_precharge_ms`, or the final sample. Exclude every pre-start sample. For `peak_abs_pack_a`, include linearly interpolated `pack_a` at both window endpoints before taking the maximum absolute value. `max_link_slew_v_per_ms` is the maximum positive consecutive `Δlink_v/Δt` over segments overlapping that window (`0.0` if no positive slope is present).
- `tau_ms`: interpolate `pack_start` and `link_start` at `precharge_start_ms`; find the first crossing of `link_start+0.6321205588*(pack_start-link_start)` and subtract start.
- `aux_delay_ms`: keys `neg,pos,pre`; first auxiliary rise at/after its command rise minus command time. Ignore earlier rises.
- `aux_edges`: keys `neg,pos,pre`; total rises plus falls.

`expected_tau_ms=precharge_ohm*capacitance_uf/1000`

`expected_ready_ms=-ln(1-ready_ratio)*expected_tau_ms`

## Continuous dwell-span convention

For all rules stated as a predicate holding for `> X ms`, dwell timing is based on retained-row state spans. A span begins at the first retained row where the predicate is true. The sampled predicate state is treated as continuing until the next retained row; the span ends at the timestamp of the first later retained row where the predicate is false. Therefore use `first_false_row.t_ms - first_true_row.t_ms`, not `last_true_row.t_ms - first_true_row.t_ms`. Do not interpolate a separate true-to-false crossing for these dwell predicates. If the predicate remains true through the capture, the final retained timestamp closes the span.

The comparison is strict: a span fires the rule only when `span_end_ms - span_start_ms > X`; a duration exactly equal to `X` is accepted and does not fire.

For every strict dwell rule that fires, evidence is recorded at threshold expiry, not at span closure:

- `WELDED_CONTACTOR`: `time_ms = span_start_ms + weld_dwell_ms`.
- `SENSOR_BIAS`: `time_ms = span_start_ms + sensor_bias_dwell_ms`.
- `AUX_TIMEOUT`: `time_ms = span_start_ms + aux_delay_ms`.

The evidence timestamp does not require a retained true sample at that exact time; the completed retained-row span only has to prove that the strict `> X ms` condition was satisfied.

Worked example: with a `100 ms` dwell, predicate true beginning at `210 ms`, last observed true at `280 ms`, and first false retained row at `315 ms`, the span is `105 ms`, so the rule fires and its evidence time is `310 ms`. If the first false retained row were exactly `310 ms`, the span would be exactly `100 ms` and the rule would not fire.

Example: `R=50 Ω`, `C=2000 µF`, `ready_ratio=.95`, `pack_start=800 V`, `link_start=8 V` gives tau `100 ms`, tau crossing `508.639483 V`, readiness threshold `760 V`, readiness `299.573227 ms`.

## Verdicts

Evaluate every rule over the full capture in this order. First detected code is `verdict`; every later code, including `LOW_ISOLATION`, becomes a flag. Do not stop after selecting a verdict:

`WELDED_CONTACTOR,UNSAFE_CLOSE,LOW_ISOLATION,REPEATED_PRECHARGE_FAILURE,BYPASS_OR_SHORT,OPEN_PRECHARGE,PRECHARGE_TIMEOUT,SENSOR_BIAS,RESIDUAL_LINK,CONTACT_BOUNCE,AUX_TIMEOUT,OK`

- `WELDED_CONTACTOR`: evaluate the positive pair (`pos_cmd`,`pos_aux`) and negative pair (`neg_cmd`,`neg_aux`) independently. A pair fires when its auxiliary is `1` while its own command is `0` for `> weld_dwell_ms`. Never merge or hand off dwell time between the positive and negative pairs.
- `UNSAFE_CLOSE`: evaluate the full capture. At any retained row where `pos_aux=1` and `neg_aux=1`, detect this code when **any one** of these four independent OR conditions is true: (1) readiness has not occurred yet at that row; (2) `link_v < safe_close_ratio*pack_v`; (3) `iso_kohm < isolation_min_kohm`; or (4) `crash=1`. Conditions (2), (3), and (4) apply both before and after readiness; do not stop scanning at `ready_at_ms`.
  Example: readiness occurs at `300 ms`; both main auxiliaries are `1` at `325 ms`; `link_v/pack_v=0.80` and `safe_close_ratio=0.85`. This is `UNSAFE_CLOSE` even though the closure is post-readiness. Post-readiness `iso_kohm=250` with `isolation_min_kohm=500` also triggers it.
- `LOW_ISOLATION`: isolation below limit while any HV command/auxiliary is active.
- `BYPASS_OR_SHORT`: tau or ready delay `<= short_tau_factor` times expected.
- `OPEN_PRECHARGE`: at `start+open_check_ms`, `pre_aux=1`, initial ratio below readiness, and ratio rise `<= open_min_rise_ratio`.
- `PRECHARGE_TIMEOUT`: no readiness by `start+max_precharge_ms`; equality is accepted. Suppress if open precharge is detected.
- `SENSOR_BIAS`: after readiness with both mains closed, `abs(pack_v-link_v) > max(sensor_bias_abs_v,sensor_bias_ratio*abs(pack_v))` for `> sensor_bias_dwell_ms`.
- `RESIDUAL_LINK`: before any command with both mains open, both `link_v > residual_abs_v` and `link_v > residual_ratio*pack_v`.
- `CONTACT_BOUNCE`: evaluate `neg_aux`, `pos_aux`, and `pre_aux` independently. It is detected when any one auxiliary channel has two consecutive transitions on that same channel separated by `< bounce_interval_ms`. Do not pool or interleave transitions from different auxiliary channels.
- `AUX_TIMEOUT`: command and auxiliary unequal for `> aux_delay_ms`.
- `OK`: no capture-local fault.

### Cross-capture session rule

Apply this rule only after every case has completed the capture-local evaluation above. The session rule never changes metrics and it must inspect the complete **capture-local evidence list**, not only the capture-local verdict.

- Only `input_state="valid"` cases with both validated `session_id` and `attempt` participate. Standalone or invalid cases are omitted from session processing and neither increment nor reset a streak.
- Group participating cases by exact `session_id`. Within each session order cases by `(attempt, case_id, original index position)`. This makes duplicate attempt numbers deterministic.
- A participating case is a **precharge-path failure** when its capture-local evidence contains at least one of `BYPASS_OR_SHORT`, `OPEN_PRECHARGE`, or `PRECHARGE_TIMEOUT`, whether that source code is the verdict or a flag.
- Maintain a consecutive-failure streak in the ordered session. A participating case with none of those three source codes resets the streak to zero. A precharge-path failure increments it.
- On the third and every later consecutive precharge-path failure, add `REPEATED_PRECHARGE_FAILURE` to the current case. Its evidence time is the earliest non-null `time_ms` among the current case's source-code evidence entries and its detail is `three or more consecutive precharge-path failures in the same session`.
- Re-sort the current case evidence by the global precedence list after inserting the session code, then recompute `verdict` and `flags`. Do not remove the original source fault(s). If a higher-priority capture-local code such as `LOW_ISOLATION` is present, it remains the verdict and `REPEATED_PRECHARGE_FAILURE` appears as a flag.
- The case still emits exactly one verdict event. If the session rule changes the primary verdict, update that row's time/value/detail to the final primary evidence. Do not emit a separate CSV row for a flag.

Example: attempts 1 and 2 in session `S` have capture-local `OPEN_PRECHARGE` and `PRECHARGE_TIMEOUT`. Attempt 3 has capture-local evidence `[LOW_ISOLATION, OPEN_PRECHARGE]`. Attempt 3 becomes `verdict=LOW_ISOLATION`, `flags=[REPEATED_PRECHARGE_FAILURE,OPEN_PRECHARGE]` because the source failure is counted even though it was already a flag.

Equality triggers readiness, short/bypass, and open-precharge; it does not trigger weld, timeout, sensor-bias, bounce, or auxiliary-timeout.

Invalid cases: `input_state="invalid"`, verdict `BAD_INPUT`, no flags, null scalar/delay metrics, zero edges, one evidence. Valid cases use `input_state="valid"`.

## Outputs

The `--out` argument names an output directory and that directory may be absent when the CLI starts. Recursively create the requested directory and any missing parents before writing artifacts. A non-existent output directory is therefore valid. If the path already exists as a directory, reuse it. If it exists as a non-directory, or the directory cannot be created or written, exit non-zero and do not treat that as a case-local `BAD_INPUT`.

Write `<out>/report.json` per `/app/spec/report-schema.json`. For the required command, `<out>` is `/app/result`. Top keys: `format,cases,aggregate`. `ok_count` counts only `OK`; `fault_count=case_count-ok_count`, including `BAD_INPUT`. Sort cases by ID, flags by precedence, messages and histogram keys lexically. Evidence codes equal `[verdict,*flags]`. Use UTF-8, two-space indentation, deterministic keys, trailing newline.

Write `<out>/events.csv`:

`case_id,time_ms,event,channel,value,detail`

Details are non-empty. Emit transition rows for every retained rise or fall on all seven digital channels: `pre_cmd`, `pre_aux`, `pos_cmd`, `pos_aux`, `neg_cmd`, `neg_aux`, and `crash`. Transitions use `event=rise|fall`, the source channel, `value=1|0`, and `detail=digital transition`. Ready: `event=ready`, `channel=link_v`, six-decimal `ready_link_v`, `detail=readiness threshold crossed`. Verdict: `event=verdict`, `channel=system`, verdict code, first evidence detail/time or `0.000000`. Invalid cases emit one `event=verdict` row with `BAD_INPUT`. Sort by case ID, time, event, channel, value.

Every `time_ms` value in `events.csv`—including rise, fall, ready, verdict, and `BAD_INPUT` rows—must be a fixed six-decimal string matching `^-?\d+\.\d{6}$`.

Success stdout:

`cases=<N> ok=<N> faults=<N> out=<absolute-output-directory>`

Tolerances: ±5 ms time/delay, ±1 V, ±0.5 A, ±0.002 ratio, ±5% tau, and ±3% or ±0.05 V/ms slew. Schemas, verdicts, flags, precedence, ordering, counts, and event rows are exact.

Use installed packages only. Do not hard-code IDs/filenames or inspect verifier files.
