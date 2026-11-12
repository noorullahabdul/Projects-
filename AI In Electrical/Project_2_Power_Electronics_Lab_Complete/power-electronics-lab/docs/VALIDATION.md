# Validation record — 10 November 2026

Environment: Python 3.12.14, Linux.

| Check | Result |
| --- | --- |
| Current unit/regression suite | 33 tests passed |
| Nominal averaged buck transient | PASS, seven checks |
| Sensor-bias and duty-drop waveforms | Both fail acceptance as expected |
| Buck operating-point sweep | 81/81 pass |
| Inverter map | 108/240 feasible; 132 flagged |
| OBC map | 15/27 pass; 12 flagged |
| Imported nominal CSV CLI analysis | Exit 0 |
| Imported biased CSV CLI analysis | Exit 1 |
| Python wheel packaging | Built successfully |
| HTML/SVG structural checks | Tables present, finite plotted data, no external scripts |

Tests exercise electrical power balance, DC volt-second balance, ripple/loss
frequency tradeoffs, thermal/current limits, CCM validity, RK4 convergence,
fault detection, signed regeneration accounting, constant-power torque
limiting, voltage feasibility, LLC resonance and frequency solving, input
current/power consistency, malformed inputs and timestamp integrity.

No native SPICE or hardware run was performed. Windows scripts and GitHub CI
were not executed here. Browser rendering could not be exercised in the
environment; report HTML/SVG structure was checked.

Reproduce:

    python -m unittest discover -s tests -v
    python -m powerlab demo --out outputs/demo
