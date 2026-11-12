# EV DC-Link Lab

A runnable Python engineering application for an 800 V DC-link: design
calculations, component and sensor corners, contactor sequencing, fault
injection, imported telemetry diagnostics, and reproducible reports.

Built from Noorullah Abdul Khadar's independent powertrain design studies,
with a new tested software core and ChatGPT assistance. This is a technical
software project for continuing development, not a tutorial or a hardware release.

## Run in two commands

Requires Python 3.10 or later. The application and tests use only the standard library.
Open a terminal inside this extracted project folder:

    python -m dclink_lab demo --out outputs/demo
    python -m unittest discover -s tests -v

On Windows, double-click RUN_DEMO.bat. On macOS/Linux, run sh run_demo.sh.
Open outputs/demo/report.html in a browser after the command finishes.

## What is implemented

| Capability | Current implementation |
| --- | --- |
| Design baseline | 600–850 V, 800 V nominal, 92 ohm precharge, 1 mF DC-link, 1 kohm discharge |
| Design calculations | RC charging, energy, current, discharge, and 108 deterministic sensor/component corners |
| Supervisor | OFF, self-test, negative close, precharge, positive close, run, opening, discharge, safe, latched fault |
| Contactor plant | Pickup/release delay, open/weld faults, first-order electrical response |
| Fault tests | Ten injected scenarios with observed diagnostic codes and isolation/torque checks |
| Telemetry | Strict CSV parsing, missing-data detection, voltage/current/interlock checks, interpolated discharge timing |
| Evidence | JSON, CSV, standalone HTML/SVG report, source hashes, SQLite run history |
| Native engineering files | Recovered LTspice .asc/.cir/.lib/.inc models, MATLAB/Simulink generation scripts, requirements, DFMEA, BOM and HIL plans |

## Use the terminal tools

Generate a waveform:

    python -m dclink_lab simulate --fault sensor_bias --csv outputs/bias.csv

Analyze a nominal or imported waveform:

    python -m dclink_lab analyze outputs/demo/nominal.csv --out outputs/recheck

Export a baseline configuration, edit it, and sweep it:

    python -m dclink_lab default-design > design.json
    python -m dclink_lab --design design.json sweep --out outputs/corners

Read the local run ledger:

    python -m dclink_lab history outputs/demo/runs.sqlite3

Command exits: 0 = satisfied checks; 1 = an evaluated requirement or expected
experiment failed; 2 = malformed input or incomplete evidence. The demo's exit
code concerns its nominal cycle and injected diagnostics. It also reports
analytical corner failures separately. The sweep command exits 1 when any
corner fails.

## A real open engineering finding

The 92 ohm baseline passes its nominal cycle. Six of 108 analytical corners
exceed the 350 ms startup budget when independent voltage-sensor gain errors,
component tolerances, and 30 ms contactor/sequence allocation are combined.
The tool reports these failures instead of converting them to a pass.

An 88 ohm analytical alternative is supplied in examples/design_88ohm.json;
it meets this simplified sweep's limits, including the 10 A inrush allocation.
That result is not a part selection or a hardware qualification.

## Project layout

- dclink_lab: current application source.
- tests: regression, numerical, input-integrity and fault tests.
- examples/verified-demo: generated, reproducible sample outputs.
- engineering: recovered engineering input/reference files.
- recovered_sources: original technical archives, included for private recovery and ignored by Git.
- docs: equations, CSV schema, decisions, limitations and continuation tasks.
- BUNDLE_MANIFEST.json: file checksums, verified by tools/verify_bundle.py.

Only dclink_lab and its tests define the current software behavior. Native
SPICE models have their own parameter baselines. No LTspice, MATLAB, Simulink,
HIL or hardware execution is claimed by the Python test results.

See docs/GITHUB_SETUP.md to create your own repository and
docs/PROJECT_SUBMISSION.md for an accurate project description.
