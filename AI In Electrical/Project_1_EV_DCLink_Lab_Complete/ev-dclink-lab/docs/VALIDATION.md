# Validation record — 10 November 2026

Environment: Python 3.12.14, Linux.

| Check | Result |
| --- | --- |
| Current unit/regression suite | 26 tests passed |
| Nominal waveform analysis | PASS, seven checks |
| Injected controller faults | 10 expected diagnostic outcomes observed |
| Baseline corner sweep | 102/108 pass; six reported timing failures |
| 88 ohm alternative sweep | 108/108 pass in analytical model |
| CLI analyze of nominal CSV | Exit 0 |
| CLI sweep of baseline | Exit 1, as required for failing corners |
| CLI sweep of 88 ohm alternative | Exit 0 |
| Physical LTspice package static validator | Passed |
| Alternate native model static validator | Passed |
| Python wheel packaging | Built successfully |
| HTML/SVG structural checks | Tables present, finite plotted data, no external scripts |

Tests cover latching, interrupted startup, welded-feedback discharge blocking,
feedback loss, link collapse, invalid/nonfinite inputs, malformed CSV, missing
events, sampling gaps, sensor disagreement, time-step convergence, RC inverse
relations and special-character run-database paths.

No native LTspice/MATLAB/Simulink or hardware run was performed. Windows scripts
and GitHub CI were not executed in this Linux environment. Browser rendering
could not be exercised in the environment; report HTML/SVG structure was checked.

Reproduce:

    python -m unittest discover -s tests -v
    python -m dclink_lab demo --out outputs/demo
    python engineering/ltspice_physical/validate_physical_package.py
    python engineering/ltspice_complete/validate_ltspice_package.py
