# EV High-Voltage Power-Up Inspector

Implement `/app/powerup/` so this command works:

```bash
python -m powerup.cli --index /app/input/index.json --out /app/result
```

The complete normative formulas, verdict rules, precedence, boundary behavior, examples, tolerances, and output mapping are in:

```text
/app/spec/diagnostic-rules.md
```

That file is authoritative. Use only case values from `index.json`; do not invent hidden constants, hard-code case IDs or filenames, inspect verifier files, modify inputs, or use the network.

## Required behavior

Evaluate every case's capture-local behavior independently first, then apply the optional cross-capture session rule exactly as documented in the rulebook. A malformed case must become `BAD_INPUT` without stopping other cases. Exit `0` after all readable cases, including invalid ones. Exit non-zero only for an invalid top-level index or unwritable output directory.

For capture data:

- resolve relative paths from the index directory;
- require finite analog values and digital values exactly `0` or `1`;
- sort by time;
- keep the physically last row for duplicate timestamps;
- require at least three unique timestamps;
- interpolate analog values linearly without extrapolation;
- compute tau baselines by interpolating `pack_v` and `link_v` at `precharge_start_ms`, not from the first row.
- keep a readable capture valid even when `pre_cmd` never rises; leave start-dependent metrics null and still evaluate every rule that does not require a precharge start;
- start the current/slew metric window at `precharge_start_ms`, exclude all pre-start disturbances, and honor interpolated analog window endpoints;
- evaluate positive and negative `WELDED_CONTACTOR` dwell independently; never pool or hand off dwell time between the two main channels.


### Continuous dwell-span convention

For every diagnostic expressed as a predicate that must remain true for `> X ms` (including `WELDED_CONTACTOR`, `SENSOR_BIAS`, and `AUX_TIMEOUT`), use retained-row span timing:

- the span starts at the timestamp of the first retained row where the predicate is true;
- that sampled predicate state continues until the next retained row; the span closes at the timestamp of the first later retained row where the predicate is false, not at the timestamp of the last true row;
- do not interpolate a separate true-to-false crossing for these dwell predicates;
- if the predicate is still true at the final retained row, close the span at the final retained timestamp;
- `duration_ms = span_end_ms - span_start_ms`, and the rule fires only when `duration_ms > configured_dwell_ms`. Equality does not fire.

When a strict dwell rule fires, its evidence `time_ms` is the threshold-expiry time `span_start_ms + configured_dwell_ms`, not the closing false-row timestamp. This applies to `WELDED_CONTACTOR` with `weld_dwell_ms`, `SENSOR_BIAS` with `sensor_bias_dwell_ms`, and `AUX_TIMEOUT` with `aux_delay_ms`. Example: with a `100 ms` threshold, a span beginning at `210 ms` and first closing false row at `315 ms` lasts `105 ms`, so the rule fires with evidence time `310 ms`; if the first false row is exactly `310 ms`, duration is exactly `100 ms` and the rule does not fire. No retained true sample is required at or after the threshold-expiry timestamp.

Evaluate every capture-local diagnostic rule over the full capture in documented precedence order. Then, for cases carrying the documented `session_id`/`attempt` pair, apply the session streak rule across cases before final serialization. The first final evidence code is the verdict. Continue preserving all remaining detected codes; every later code, including `LOW_ISOLATION` and any session code, must be added to `flags` in precedence order.

## Outputs

Treat the `--out` argument as a directory path that may not exist yet. Create that directory and any missing parents before writing results. A missing output directory is not an error by itself. If the path already exists as a directory, reuse it; if it exists as a non-directory or cannot be created or written, exit non-zero.

Create inside that directory:

```text
report.json
events.csv
```

For the required command above this means `/app/result/report.json` and `/app/result/events.csv`.

`report.json` must follow `/app/spec/report-schema.json`, use deterministic UTF-8 JSON with two-space indentation and a trailing newline, and report exact aggregate counts.

`events.csv` header:

```text
case_id,time_ms,event,channel,value,detail
```

Required literal values:

- transition rows: `event=rise` or `event=fall`;
- readiness rows: `event=ready`;
- verdict rows, including `BAD_INPUT`: `event=verdict`.

Every `time_ms` value in `events.csv`—including rise, fall, ready, verdict, and `BAD_INPUT` rows—must be a fixed six-decimal string matching `^-?\d+\.\d{6}$`.

Ready rows use `channel=link_v`; verdict rows use `channel=system`. Sort rows exactly as described in the rulebook.

On success print exactly:

```text
cases=<N> ok=<N> faults=<N> out=<absolute-output-directory>
```

Use installed packages only.
