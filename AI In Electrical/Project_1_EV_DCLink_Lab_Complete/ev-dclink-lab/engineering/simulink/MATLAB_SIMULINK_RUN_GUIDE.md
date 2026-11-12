# MATLAB and Simulink Run Guide

## Standalone MATLAB verification

Run `dclink_gate2_analysis.m`. It evaluates all 27 precharge and 27 active-discharge corners, asserts the acceptance limits, writes CSV outputs and plots the nominal precharge waveform.

## Generate the Simulink logical model

Run `build_dclink_logic_model.m`. It creates `DCLINK_800V_LOGIC.slx` with the supervisory state machine, timeouts, DTCs, contactor commands, discharge control and torque-enable interlock. Keep `dclink_logic_function.txt` in the same directory.

## Generate the Simscape Electrical plant

Run `build_dclink_simscape_model.m`. It creates `DCLINK_800V_SIMSCAPE.slx` with the battery, source ESR, bus inductance, contactor/precharge elements, capacitor ESR/ESL, DC-link capacitor, active discharge, passive bleeder and voltage sensor.

Simscape library paths and some mask parameter names vary by MATLAB release. The builder checks block availability and reports the exact path requiring local adjustment. The model deliberately includes a visible note listing branch and physical-signal connections that must be confirmed locally before simulation.

The generated model is intentionally a reduced-order starting point. Before hardware correlation:

1. Replace ideal contactor elements with reviewed supplier or correlated custom models.
2. Connect logical model outputs through Simulink-PS converters to the Simscape contactor gates.
3. Add independent pack and DC-link sensors, quantization, delay, noise and fault injection.
4. Add contactor coil/auxiliary-contact timing and bounce.
5. Add active-discharge switch and thermal states.
6. Link the test harness to the DVP&R IDs.

## Verification status

The numerical equations and Python equivalent have been executed in this repository. The MATLAB and Simulink files require local execution because MATLAB is not installed in the build environment. Record the MATLAB release, solver configuration and generated model checksum when local validation is performed.

