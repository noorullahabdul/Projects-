# Power Electronics Lab

A runnable Python engineering workbench for converter design and validation:
48 V → 12 V / 1 kW buck, 30 kW OBC PFC/LLC, and 150 kW traction inverter.

The code extends Noorullah Abdul Khadar's independently recreated powertrain
studies with numerical simulation, imported waveform checks, explicit loss
accounting and honest operating-envelope screening, using ChatGPT assistance.

## Run immediately

Python 3.10 or later; no third-party packages are required for the application
or tests. Open a terminal inside this extracted folder:

    python -m powerlab demo --out outputs/demo
    python -m unittest discover -s tests -v

Windows: double-click RUN_DEMO.bat.
macOS/Linux: sh run_demo.sh.
Then open outputs/demo/report.html.

## Implemented modules

| Module | Capabilities |
| --- | --- |
| Synchronous buck | Duty with conduction drops; CCM ripple; switch/inductor/gate/deadtime/capacitor losses; thermal estimates |
| Buck dynamics | Averaged LC plant, capacitor ESR, PI control, anti-windup, RK4 integration, 50%→100% resistive load step |
| Buck diagnostics | Regulation, final load power, transient envelope, current peak, settling, input voltage, timestamp/coverage checks |
| Fault injection | Biased feedback and duty-drop waveforms checked by the same analyzer as normal data |
| Traction inverter | Torque/power envelope, thermal derating, dq voltage feasibility at id=0, motor/inverter losses, signed regeneration power |
| OBC | Three-phase input current, full-bridge LLC FHA impedance model, frequency root solving, gain/current/efficiency checks |
| Reporting | CSV maps, JSON evidence, self-contained HTML/SVG report, waveform SHA-256 |
| Native files | Generated ideal-switch buck .cir plus recovered OBC and inverter reference netlists |

## Terminal workflow

Evaluate the default buck:

    python -m powerlab buck-point

Generate and analyze a fault waveform:

    python -m powerlab simulate --fault sensor_bias --csv outputs/bias.csv
    python -m powerlab analyze outputs/bias.csv --out outputs/bias-summary.json

Export a configuration, edit it, and run a sweep:

    python -m powerlab default-config buck > buck.json
    python -m powerlab buck-sweep --spec buck.json --csv outputs/buck-sweep.csv

Generate system maps:

    python -m powerlab inverter-map --csv outputs/inverter.csv
    python -m powerlab obc-map --csv outputs/obc.csv

Export the separate fixed-PWM native switching deck:

    python -m powerlab export-spice --out outputs/buck.cir

Exit codes: 0 = evaluated conditions satisfied; 1 = evaluated design/validation
failure; 2 = invalid input or incomplete evidence. Maps intentionally include
infeasible points and exit 1 when any fail. The demo exits 0 when its nominal
buck validation and fault-detection experiment are verified; it reports map
failures separately.

## Expected example results

- 81 buck operating points evaluated; 81 pass the stated screening limits.
- 240 inverter points; 108 pass and 132 are flagged by the model.
- 27 OBC points; 15 pass and 12 are flagged.
- Nominal averaged buck transient passes seven checks.
- Both injected buck faults fail the waveform acceptance checks as expected.

Inverter voltage infeasibility is reported; field weakening is not implemented.
LLC inductive input impedance is not proof of ZVS, so ZVS evidence remains
NOT_EVALUATED. The averaged buck waveform does not contain switching ripple.
All device/thermal parameters are engineering assumptions, not measured
supplier-correlated models.

Current source is in powerlab. Recovered design references are in engineering.
Original archive data is in recovered_sources, ignored by Git. Reproducible
example outputs are under examples/verified-demo.

See docs/MODELS.md, docs/CSV_SCHEMA.md and docs/GITHUB_SETUP.md.
